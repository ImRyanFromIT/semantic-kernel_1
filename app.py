'''
FastAPI Web Interface for AI Concierge

Web-based interface for the AI assistant.
'''

import asyncio
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from semantic_kernel.processes.kernel_process import KernelProcessEvent
from semantic_kernel.processes.local_runtime.local_kernel_process import start

from src.utils.kernel_builder import create_kernel
from src.utils.telemetry import TelemetryLogger
from src.utils.store_factory import create_vector_store
from src.utils.debug_config import debug_print
from src.data.data_loader import SRMDataLoader
from src.processes.srm_discovery_process import SRMDiscoveryProcess
from src.processes.hostname_lookup_process import HostnameLookupProcess


# FastAPI app
app = FastAPI(title="AI Concierge")

# Mount static files
app.mount("/static", StaticFiles(directory="web"), name="static")


class QueryRequest(BaseModel):
    '''Request model for query endpoint.'''
    query: str


class QueryResponse(BaseModel):
    '''Response model for query endpoint.'''
    response: str
    session_id: str


class HostnameRequest(BaseModel):
    '''Request model for hostname lookup endpoint.'''
    hostname: str


class HostnameResponse(BaseModel):
    '''Response model for hostname lookup endpoint.'''
    response: str
    session_id: str


@app.on_event("startup")
async def startup_event():
    '''
    Initialize the kernel, vector store, build processes, and load SRM data on startup.
    '''
    import os
    
    print("[*] Initializing AI Concierge...")
    
    # Create kernel with chat and embedding services
    app.state.kernel = create_kernel()
    print("[+] Kernel initialized")
    
    # Get embedding service
    embedding_service = app.state.kernel.get_service("embedding")
    
    # Create vector store using factory
    app.state.vector_store = create_vector_store(embedding_service)
    print("[+] Vector store created")
    
    # Load data based on store type
    store_type = os.getenv('VECTOR_STORE_TYPE', 'azure_search').lower()
    
    if store_type == 'in_memory':
        # Load SRM catalog from CSV for in-memory store
        print("[*] Loading SRM catalog from CSV...")
        data_loader = SRMDataLoader(app.state.vector_store)
        num_records = await data_loader.load_and_index("data/srm_catalog.csv")
        print(f"[+] Loaded and indexed {num_records} SRM records")
    else:
        # Azure AI Search - data already exists in the index
        print("[+] Using existing Azure AI Search index")
        await app.state.vector_store.ensure_collection_exists()
    
    # Build process definitions once (they will be reused for all requests)
    print("[*] Building process definitions...")
    srm_process_builder = SRMDiscoveryProcess.create_process()
    app.state.srm_process = srm_process_builder.build()
    
    hostname_process_builder = HostnameLookupProcess.create_process()
    app.state.hostname_process = hostname_process_builder.build()
    print("[+] Process definitions built")
    
    # Initialize telemetry
    app.state.telemetry = TelemetryLogger()
    
    print("[+] AI Concierge ready!")


async def run_query(
    kernel,
    vector_store,
    srm_process,
    telemetry,
    user_query: str,
    session_id: str
) -> str:
    '''
    Run a single query through the discovery process.
    
    Args:
        kernel: Semantic Kernel instance
        vector_store: Vector store with SRM data
        srm_process: Pre-built process definition
        telemetry: Telemetry logger
        user_query: The user's query
        session_id: Session identifier
        
    Returns:
        The final answer or clarification question
    '''
    # Create initial event data with user_query, vector_store, session_id, and kernel
    # Note: SK ProcessBuilder requires passing dependencies through events, not constructors
    # result_container will be populated by steps with the final output
    result_container = {}
    initial_data = {
        "user_query": user_query,
        "vector_store": vector_store,
        "session_id": session_id,
        "kernel": kernel,
        "result_container": result_container,
    }
    
    # Start process
    telemetry.log_process_state_change(
        session_id=session_id,
        process="SRMDiscoveryProcess",
        from_state="init",
        to_state="running"
    )
    
    try:
        # Use pre-built process definition (reused for all requests)
        async with await start(
            process=srm_process,
            kernel=kernel,
            initial_event=KernelProcessEvent(
                id=SRMDiscoveryProcess.ProcessEvents.StartProcess.value,
                data=initial_data
            ),
            max_supersteps=50,
        ) as process_context:
            # Get final state
            final_state = await process_context.get_state()
            
            # Debug: print state info
            debug_print(f"DEBUG: Process completed. State: {type(final_state)}")
            if hasattr(final_state, 'name'):
                debug_print(f"DEBUG: Process name: {final_state.name}")
            
            # Result was populated by steps via result_container
            result_data = result_container
            debug_print(f"DEBUG: Retrieved result for session {session_id}: {result_data}")
            
            if result_data:
                if 'rejection_message' in result_data:
                    return f"[!] {result_data['rejection_message']}"
                elif 'clarification' in result_data:
                    return f"[?] {result_data['clarification']}"
                elif 'final_answer' in result_data:
                    # Log telemetry
                    telemetry.log_answer_published(
                        session_id=session_id,
                        selected_id=result_data.get('selected_id'),
                        confidence=result_data.get('confidence', 0.0)
                    )
                    return result_data['final_answer']
            
            return "Process completed but no result was generated."
    
    except Exception as e:
        telemetry.log_error(
            session_id=session_id,
            error_code="PROCESS_ERROR",
            error_message=str(e)
        )
        return f"[!] An error occurred: {str(e)}"


async def run_hostname_query(
    kernel,
    hostname_process,
    telemetry,
    hostname_query: str,
    session_id: str
) -> str:
    '''
    Run a hostname lookup query.
    
    Args:
        kernel: Semantic Kernel instance
        hostname_process: Pre-built process definition
        telemetry: Telemetry logger
        hostname_query: The hostname to look up
        session_id: Session identifier
        
    Returns:
        The formatted hostname information
    '''
    # Create initial event data with user_query, session_id, and kernel
    # Note: SK ProcessBuilder requires passing dependencies through events, not constructors
    # result_container will be populated by steps with the final output
    result_container = {}
    initial_data = {
        "user_query": hostname_query,
        "session_id": session_id,
        "kernel": kernel,
        "result_container": result_container,
    }
    
    # Start process
    telemetry.log_process_state_change(
        session_id=session_id,
        process="HostnameLookupProcess",
        from_state="init",
        to_state="running"
    )
    
    try:
        # Use pre-built process definition (reused for all requests)
        async with await start(
            process=hostname_process,
            kernel=kernel,
            initial_event=KernelProcessEvent(
                id=HostnameLookupProcess.ProcessEvents.StartProcess.value,
                data=initial_data
            ),
            max_supersteps=50,
        ) as process_context:
            # Get final state
            final_state = await process_context.get_state()
            
            # Debug: print state info
            debug_print(f"DEBUG: Process completed. State: {type(final_state)}")
            if hasattr(final_state, 'name'):
                debug_print(f"DEBUG: Process name: {final_state.name}")
            
            # Result was populated by steps via result_container
            result_data = result_container
            debug_print(f"DEBUG: Retrieved result for session {session_id}: {result_data}")
            
            if result_data:
                if 'rejection_message' in result_data:
                    return f"[!] {result_data['rejection_message']}"
                elif 'answer' in result_data:
                    # Log telemetry
                    telemetry.log_process_state_change(
                        session_id=session_id,
                        process="HostnameLookupProcess",
                        from_state="running",
                        to_state="completed"
                    )
                    return result_data['answer']
            
            return "Process completed but no result was generated."
    
    except Exception as e:
        telemetry.log_error(
            session_id=session_id,
            error_code="PROCESS_ERROR",
            error_message=str(e)
        )
        return f"[!] An error occurred: {str(e)}"


@app.post("/api/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    '''
    Process a user query and return the response.
    
    Args:
        request: QueryRequest containing the user's query
        
    Returns:
        QueryResponse with the response and session_id
    '''
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    # Generate unique session ID for this request
    session_id = str(uuid.uuid4())[:8]
    
    try:
        # Run the query through the process
        response = await run_query(
            kernel=app.state.kernel,
            vector_store=app.state.vector_store,
            srm_process=app.state.srm_process,
            telemetry=app.state.telemetry,
            user_query=request.query.strip(),
            session_id=session_id
        )
        
        return QueryResponse(
            response=response,
            session_id=session_id
        )
    
    except Exception as e:
        print(f"[!] Error processing query: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


@app.post("/api/hostname", response_model=HostnameResponse)
async def hostname_endpoint(request: HostnameRequest):
    '''
    Look up hostname details and return the information.
    
    Args:
        request: HostnameRequest containing the hostname to look up
        
    Returns:
        HostnameResponse with the hostname details and session_id
    '''
    if not request.hostname or not request.hostname.strip():
        raise HTTPException(status_code=400, detail="Hostname cannot be empty")
    
    # Generate unique session ID for this request
    session_id = str(uuid.uuid4())[:8]
    
    try:
        # Run the hostname lookup
        response = await run_hostname_query(
            kernel=app.state.kernel,
            hostname_process=app.state.hostname_process,
            telemetry=app.state.telemetry,
            hostname_query=request.hostname.strip(),
            session_id=session_id
        )
        
        return HostnameResponse(
            response=response,
            session_id=session_id
        )
    
    except Exception as e:
        print(f"[!] Error processing hostname lookup: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing hostname lookup: {str(e)}")


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    '''
    Serve the main HTML page.
    '''
    html_path = Path(__file__).parent / "web" / "index.html"
    
    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


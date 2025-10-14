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
from src.utils.result_store import store_result, get_result, clear_result
from src.utils.store_factory import create_vector_store
from src.utils.debug_config import debug_print
from src.data.data_loader import SRMDataLoader
from src.processes.srm_discovery_process import SRMDiscoveryProcess


# Global state - initialized at startup
kernel = None
vector_store = None
telemetry = None

# FastAPI app
app = FastAPI(title="AI Concierge")


class QueryRequest(BaseModel):
    '''Request model for query endpoint.'''
    query: str


class QueryResponse(BaseModel):
    '''Response model for query endpoint.'''
    response: str
    session_id: str


@app.on_event("startup")
async def startup_event():
    '''
    Initialize the kernel, vector store, and load SRM data on startup.
    '''
    global kernel, vector_store, telemetry
    
    import os
    
    print("[*] Initializing AI Concierge...")
    
    # Create kernel with chat and embedding services
    kernel = create_kernel()
    print("[+] Kernel initialized")
    
    # Get embedding service
    embedding_service = kernel.get_service("embedding")
    
    # Create vector store using factory
    vector_store = create_vector_store(embedding_service)
    print("[+] Vector store created")
    
    # Load data based on store type
    store_type = os.getenv('VECTOR_STORE_TYPE', 'azure_search').lower()
    
    if store_type == 'in_memory':
        # Load SRM catalog from CSV for in-memory store
        print("[*] Loading SRM catalog from CSV...")
        data_loader = SRMDataLoader(vector_store)
        num_records = await data_loader.load_and_index("data/srm_catalog.csv")
        print(f"[+] Loaded and indexed {num_records} SRM records")
    else:
        # Azure AI Search - data already exists in the index
        print("[+] Using existing Azure AI Search index")
        await vector_store.ensure_collection_exists()
    
    # Initialize telemetry
    telemetry = TelemetryLogger()
    
    print("[+] AI Concierge ready!")


async def run_query(user_query: str, session_id: str) -> str:
    '''
    Run a single query through the discovery process.
    
    Args:
        user_query: The user's query
        session_id: Session identifier
        
    Returns:
        The final answer or clarification question
    '''
    # Create process
    process_builder = SRMDiscoveryProcess.create_process(kernel, vector_store)
    kernel_process = process_builder.build()
    
    # Create initial event data with user_query, vector_store, and session_id
    initial_data = {
        "user_query": user_query,
        "vector_store": vector_store,
        "session_id": session_id,
    }
    
    # Start process
    telemetry.log_process_state_change(
        session_id=session_id,
        process="SRMDiscoveryProcess",
        from_state="init",
        to_state="running"
    )
    
    try:
        async with await start(
            process=kernel_process,
            kernel=kernel,
            initial_event=KernelProcessEvent(
                id=SRMDiscoveryProcess.ProcessEvents.StartProcess.value,
                data=initial_data
            ),
        ) as process_context:
            # Get final state
            final_state = await process_context.get_state()
            
            # Debug: print state info
            debug_print(f"DEBUG: Process completed. State: {type(final_state)}")
            if hasattr(final_state, 'name'):
                debug_print(f"DEBUG: Process name: {final_state.name}")
            
            # Retrieve result from global store
            result = get_result(session_id)
            clear_result(session_id)
            
            debug_print(f"DEBUG: Retrieved result for session {session_id}: {result}")
            
            if result:
                if 'rejection' in result:
                    return f"[!] {result['rejection']}"
                elif 'clarification' in result:
                    return f"[?] {result['clarification']}"
                elif 'answer' in result:
                    # Log telemetry
                    telemetry.log_answer_published(
                        session_id=session_id,
                        selected_id=result.get('selected_id'),
                        confidence=result.get('confidence', 0.0)
                    )
                    return result['answer']
            
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


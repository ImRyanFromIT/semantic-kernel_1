'''
FastAPI Web Interface for AI Concierge

Web-based interface for the AI assistant.
'''

import asyncio
import uuid
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from semantic_kernel.processes.kernel_process import KernelProcessEvent
from semantic_kernel.processes.local_runtime.local_kernel_process import start
from semantic_kernel.contents import ChatHistory

from src.utils.kernel_builder import create_kernel
from src.utils.telemetry import TelemetryLogger
from src.utils.store_factory import create_vector_store
from src.utils.debug_config import debug_print
from src.data.data_loader import SRMDataLoader
from src.processes.srm_discovery_process import SRMDiscoveryProcess
from src.processes.hostname_lookup_process import HostnameLookupProcess
from src.memory.feedback_store import FeedbackStore
from src.utils.feedback_processor import FeedbackProcessor
from src.models.feedback_record import FeedbackRecord, FeedbackType


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


class FeedbackRequest(BaseModel):
    '''Request model for feedback endpoint.'''
    session_id: str
    incorrect_srm_id: str | None = None
    incorrect_srm_name: str | None = None
    correct_srm_id: str | None = None
    correct_srm_name: str | None = None
    feedback_text: str | None = None
    feedback_type: str = "negative"  # positive, negative, correction
    user_id: str | None = None
    query: str = ""


class FeedbackResponse(BaseModel):
    '''Response model for feedback endpoint.'''
    success: bool
    message: str
    feedback_id: str | None = None


class SrmUpdateChatRequest(BaseModel):
    '''Request model for SRM update chat endpoint.'''
    session_id: str | None = None
    message: str


class SrmUpdateChatResponse(BaseModel):
    '''Response model for SRM update chat endpoint.'''
    session_id: str
    response: str
    status: str  # "active" | "completed" | "escalated"


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
    
    # Initialize feedback system
    print("[*] Initializing feedback system...")
    app.state.feedback_store = FeedbackStore()
    app.state.feedback_processor = FeedbackProcessor(
        feedback_store=app.state.feedback_store,
        vector_store=app.state.vector_store
    )
    print("[+] Feedback system initialized")
    
    # Initialize SRM Archivist Agent for chat-based updates
    print("[*] Initializing SRM Archivist Agent for chat...")
    from agent.main import SrmArchivistAgent
    
    # Initialize agent in chat-only mode (no email monitoring)
    app.state.agent = SrmArchivistAgent(
        config_file="agent/agent_config.yaml",
        test_mode=False,
        chat_mode=True
    )
    
    # Initialize agent (but don't start the run loop)
    agent_initialized = await app.state.agent.initialize()
    if agent_initialized:
        print("[+] SRM Archivist Agent initialized for chat-based updates")
    else:
        print("[!] Warning: SRM Archivist Agent failed to initialize")
    
    # Initialize session storage for multi-turn conversations
    app.state.chat_sessions: Dict[str, Dict[str, Any]] = {}
    print("[+] Chat session management initialized")
    
    # Start background task for session cleanup
    asyncio.create_task(_cleanup_old_sessions())
    
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
    # Create initial event data with user_query, vector_store, session_id, kernel, and feedback_processor
    # Note: SK ProcessBuilder requires passing dependencies through events, not constructors
    # result_container will be populated by steps with the final output
    result_container = {}
    initial_data = {
        "user_query": user_query,
        "vector_store": vector_store,
        "session_id": session_id,
        "kernel": kernel,
        "result_container": result_container,
        "feedback_processor": app.state.feedback_processor,
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


@app.post("/api/feedback", response_model=FeedbackResponse)
async def feedback_endpoint(request: FeedbackRequest):
    '''
    Handle user feedback on SRM recommendations.
    
    Args:
        request: FeedbackRequest containing feedback details
        
    Returns:
        FeedbackResponse with success status and feedback ID
    '''
    try:
        # Determine feedback type
        if request.correct_srm_id:
            feedback_type = FeedbackType.CORRECTION
        elif request.feedback_type == "positive":
            feedback_type = FeedbackType.POSITIVE
        else:
            feedback_type = FeedbackType.NEGATIVE
        
        # Create feedback record
        feedback = FeedbackRecord(
            session_id=request.session_id,
            user_id=request.user_id,
            query=request.query,
            incorrect_srm_id=request.incorrect_srm_id,
            incorrect_srm_name=request.incorrect_srm_name,
            correct_srm_id=request.correct_srm_id,
            correct_srm_name=request.correct_srm_name,
            feedback_text=request.feedback_text,
            feedback_type=feedback_type,
        )
        
        # Store feedback
        app.state.feedback_store.add_feedback(feedback)
        
        # Log telemetry
        app.state.telemetry.log_feedback_submitted(
            session_id=request.session_id,
            feedback_id=feedback.id,
            feedback_type=feedback_type.value,
            incorrect_srm_id=request.incorrect_srm_id,
            correct_srm_id=request.correct_srm_id,
            user_id=request.user_id
        )
        
        # Process feedback asynchronously (don't wait)
        asyncio.create_task(
            _process_feedback_async(
                feedback=feedback,
                feedback_processor=app.state.feedback_processor,
                telemetry=app.state.telemetry
            )
        )
        
        return FeedbackResponse(
            success=True,
            message="Thank you for your feedback! We'll use this to improve future recommendations.",
            feedback_id=feedback.id
        )
    
    except Exception as e:
        print(f"[!] Error processing feedback: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing feedback: {str(e)}")


async def _process_feedback_async(
    feedback: FeedbackRecord,
    feedback_processor: FeedbackProcessor,
    telemetry: TelemetryLogger
):
    '''
    Process feedback asynchronously in the background.
    
    Args:
        feedback: FeedbackRecord to process
        feedback_processor: FeedbackProcessor instance
        telemetry: TelemetryLogger instance
    '''
    try:
        success = await feedback_processor.process_feedback(feedback)
        telemetry.log_feedback_processed(
            feedback_id=feedback.id,
            success=success
        )
    except Exception as e:
        telemetry.log_feedback_processed(
            feedback_id=feedback.id,
            success=False,
            error_message=str(e)
        )


async def _cleanup_old_sessions():
    '''
    Background task to clean up old chat sessions (>1 hour inactive).
    '''
    while True:
        try:
            await asyncio.sleep(300)  # Check every 5 minutes
            
            current_time = datetime.now()
            sessions_to_delete = []
            
            for session_id, session_data in app.state.chat_sessions.items():
                last_activity = session_data.get('last_activity', session_data.get('created_at'))
                if current_time - last_activity > timedelta(hours=1):
                    sessions_to_delete.append(session_id)
            
            for session_id in sessions_to_delete:
                del app.state.chat_sessions[session_id]
                print(f"[*] Cleaned up inactive chat session: {session_id}")
        
        except Exception as e:
            print(f"[!] Error in session cleanup: {e}")


@app.post("/api/srm-update-chat", response_model=SrmUpdateChatResponse)
async def srm_update_chat_endpoint(request: SrmUpdateChatRequest):
    '''
    Handle conversational SRM update requests.
    
    Args:
        request: SrmUpdateChatRequest with session_id and message
        
    Returns:
        SrmUpdateChatResponse with agent's response and session status
    '''
    if not request.message or not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    # Get or create session
    session_id = request.session_id or str(uuid.uuid4())
    
    if session_id not in app.state.chat_sessions:
        # Create new session
        app.state.chat_sessions[session_id] = {
            'session_id': session_id,
            'chat_history': ChatHistory(),
            'created_at': datetime.now(),
            'last_activity': datetime.now(),
            'context': {},
            'status': 'active'
        }
        
        # Add initial system message to guide the agent
        system_prompt = (
            "You are helping a user update an SRM document. Be conversational and concise.\n\n"
            "CRITICAL PROCESS:\n"
            "1. Ask which SRM to update, then call search_srm to find it\n"
            "2. Show the user what you found (name and SRM_ID)\n"
            "3. Ask what changes to make (owner_notes or hidden_notes)\n"
            "4. Ask why the change is needed\n"
            "5. Summarize the changes and ask for confirmation\n"
            "6. IMPORTANT: After user confirms, IMMEDIATELY call update_srm_document\n"
            "   - document_id = the SRM_ID you found (e.g., 'SRM-051')\n"
            "   - updates = JSON string like '{\"owner_notes\": \"text here\"}'\n"
            "7. SAVE the JSON response from update_srm_document - you'll need it for notifications\n"
            "8. Report the result, then ask: 'Would you like me to send a notification email about this change?'\n"
            "9. If user says yes, ask for email address(es) (only @greatvaluelab.com allowed)\n"
            "10. CRITICAL: When user provides email, DO NOT just say you'll send it\n"
            "    - STOP and IMMEDIATELY call send_update_notification(recipients=<email>, changes_json=<saved_json>, requester_name=\"User\")\n"
            "    - WAIT for function to return\n"
            "    - Report ONLY what the function actually returned\n"
            "    - WRONG: 'Notification sent successfully' (you didn't call the function - this is a lie!)\n"
            "    - RIGHT: Call the function, get result, report result\n\n"
            "REMEMBER: You have real functions - USE them, don't just describe using them!"
        )
        app.state.chat_sessions[session_id]['chat_history'].add_system_message(system_prompt)
        print(f"[*] Created new chat session: {session_id}")
    
    session = app.state.chat_sessions[session_id]
    session['last_activity'] = datetime.now()
    
    try:
        # Add user message to the session's chat history
        session['chat_history'].add_user_message(request.message)
        
        # Invoke agent with session-specific chat history
        from semantic_kernel.contents import ChatMessageContent
        
        response_text = ""
        last_message = None
        
        async for message in app.state.agent.agent.invoke(
            session['chat_history'],
            settings=app.state.agent.execution_settings
        ):
            # Message could be ChatMessageContent or streaming content
            if isinstance(message, ChatMessageContent):
                last_message = message
                response_text += str(message.content) if message.content else ""
            elif hasattr(message, 'content'):
                response_text += str(message.content)
            else:
                response_text += str(message)
        
        # Add the final assistant message to session's history
        if last_message:
            session['chat_history'].add_message(last_message)
        elif response_text:
            session['chat_history'].add_assistant_message(response_text)
        
        # Determine session status from response
        status = session['status']
        if "updated successfully" in response_text.lower() or "update completed" in response_text.lower():
            status = "completed"
            session['status'] = "completed"
        elif "escalat" in response_text.lower() or "forward" in response_text.lower():
            status = "escalated"
            session['status'] = "escalated"
        
        return SrmUpdateChatResponse(
            session_id=session_id,
            response=response_text,
            status=status
        )
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"[!] Error in SRM update chat: {e}")
        print(f"[!] Traceback: {error_details}")
        
        # Log to file as well
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in SRM update chat: {e}")
        logger.error(f"Traceback: {error_details}")
        
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")


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


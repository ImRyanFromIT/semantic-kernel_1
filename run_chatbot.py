#!/usr/bin/env python3
"""
Recommender Chatbot Web API Service

Standalone FastAPI service for the AI Concierge (SRM discovery chatbot).
Provides web API and frontend for interactive SRM recommendations and hostname lookups.

Usage:
    python run_chatbot.py
    python run_chatbot.py --host 0.0.0.0 --port 8000
"""

import asyncio
import argparse
import json
import uuid
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, TypedDict

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from semantic_kernel.processes.kernel_process import KernelProcessEvent
from semantic_kernel.processes.local_runtime.local_kernel_process import start
from semantic_kernel.contents import ChatHistory
from semantic_kernel.contents.utils.author_role import AuthorRole

from src.utils.kernel_builder import create_kernel
from src.utils.telemetry import TelemetryLogger
from src.utils.store_factory import create_vector_store
from src.utils.debug_config import debug_print
from src.data.data_loader import SRMDataLoader
from src.processes.discovery.srm_discovery_process import SRMDiscoveryProcess
from src.processes.discovery.hostname_lookup_process import HostnameLookupProcess
from src.memory.feedback_store import FeedbackStore
from src.utils.feedback_processor import FeedbackProcessor
from src.models.feedback_record import FeedbackRecord, FeedbackType


# FastAPI app
app = FastAPI(
    title="AI Concierge - Recommender Chatbot",
    description="SRM Discovery and Recommendation Service",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="web"), name="static")


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class QueryRequest(BaseModel):
    """Request model for query endpoint."""
    query: str


class QueryResponse(BaseModel):
    """Response model for query endpoint."""
    response: str
    session_id: str


class HostnameRequest(BaseModel):
    """Request model for hostname lookup endpoint."""
    hostname: str


class HostnameResponse(BaseModel):
    """Response model for hostname lookup endpoint."""
    response: str
    session_id: str


class FeedbackRequest(BaseModel):
    """Request model for feedback endpoint."""
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
    """Response model for feedback endpoint."""
    success: bool
    message: str
    feedback_id: str | None = None


class SrmUpdateChatRequest(BaseModel):
    """Request model for SRM update chat endpoint."""
    session_id: str | None = None
    message: str


class SrmUpdateChatResponse(BaseModel):
    """Response model for SRM update chat endpoint."""
    session_id: str
    response: str
    status: str  # "disabled" for this service


# TypedDict definitions for maintainer API responses
class SRMSearchResult(TypedDict):
    """Structure for SRM search results."""
    id: str
    name: str
    category: str
    use_case: str
    score: float


class SRMDetail(TypedDict):
    """Structure for detailed SRM information."""
    id: str
    name: str
    category: str
    use_case: str
    owner_notes: str
    hidden_notes: str


class ChangeRecord(TypedDict):
    """Structure for tracking field changes."""
    field: str
    before: str
    after: str


class MaintainerSearchRequest(BaseModel):
    """Request model for maintainer search endpoint."""
    query: str
    top_k: int = 5


class MaintainerSearchResponse(BaseModel):
    """Response model for maintainer search endpoint."""
    results: list[SRMSearchResult]


class MaintainerGetRequest(BaseModel):
    """Request model for maintainer get by ID endpoint."""
    srm_id: str


class MaintainerGetResponse(BaseModel):
    """Response model for maintainer get by ID endpoint."""
    srm: SRMDetail | None
    error: str | None = None


class MaintainerUpdateRequest(BaseModel):
    """Request model for maintainer update endpoint."""
    srm_id: str
    updates: dict[str, str]  # Field name -> new value


class MaintainerUpdateResponse(BaseModel):
    """Response model for maintainer update endpoint."""
    success: bool
    srm_id: str
    srm_name: str | None = None
    changes: list[ChangeRecord] | None = None
    error: str | None = None


# ============================================================================
# STARTUP
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Initialize the kernel, vector store, build processes, and load SRM data on startup.
    """
    import os

    print("\n" + "=" * 80)
    print("AI CONCIERGE - RECOMMENDER CHATBOT SERVICE")
    print("=" * 80)

    # Create kernel with chat and embedding services
    print("[*] Initializing Semantic Kernel...")
    app.state.kernel = create_kernel()
    print("[+] Kernel initialized")

    # Get embedding service
    print("[*] Getting embedding service...")
    embedding_service = app.state.kernel.get_service("embedding")

    # Create vector store using factory
    print("[*] Creating vector store...")
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
        print("[*] Using existing Azure AI Search index...")
        await app.state.vector_store.ensure_collection_exists()
        print("[+] Azure AI Search index ready")

    # Build process definitions once (they will be reused for all requests)
    print("[*] Building process definitions...")
    srm_process_builder = SRMDiscoveryProcess.create_process()
    app.state.srm_process = srm_process_builder.build()

    hostname_process_builder = HostnameLookupProcess.create_process()
    app.state.hostname_process = hostname_process_builder.build()
    print("[+] Process definitions built")

    # Initialize telemetry
    print("[*] Initializing telemetry...")
    app.state.telemetry = TelemetryLogger()
    print("[+] Telemetry initialized")

    # Initialize feedback system
    print("[*] Initializing feedback system...")
    app.state.feedback_store = FeedbackStore()
    app.state.feedback_processor = FeedbackProcessor(
        feedback_store=app.state.feedback_store,
        vector_store=app.state.vector_store
    )
    print("[+] Feedback system initialized")

    # Initialize maintainer plugin for API endpoints
    print("[*] Initializing maintainer plugin...")
    from src.plugins.maintainer.srm_metadata_plugin import SRMMetadataPlugin
    app.state.maintainer_plugin = SRMMetadataPlugin(
        vector_store=app.state.vector_store
    )
    print("[+] Maintainer plugin initialized")

    # Initialize session storage for multi-turn conversations
    app.state.chat_sessions: Dict[str, Dict[str, Any]] = {}
    print("[+] Chat session management initialized")

    # Start background task for session cleanup
    asyncio.create_task(_cleanup_old_sessions())

    print("=" * 80)
    print("SERVICE READY")
    print("Web UI: http://localhost:8000")
    print("API Docs: http://localhost:8000/docs")
    print("=" * 80 + "\n")


# ============================================================================
# QUERY PROCESSING
# ============================================================================

async def run_query(
    kernel,
    vector_store,
    srm_process,
    telemetry,
    user_query: str,
    session_id: str
) -> str:
    """
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
    """
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
    """
    Run a hostname lookup query.

    Args:
        kernel: Semantic Kernel instance
        hostname_process: Pre-built process definition
        telemetry: Telemetry logger
        hostname_query: The hostname to look up
        session_id: Session identifier

    Returns:
        The formatted hostname information
    """
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


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.post("/api/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest):
    """
    Process a user query and return the response.

    Args:
        request: QueryRequest containing the user's query

    Returns:
        QueryResponse with the response and session_id
    """
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
    """
    Look up hostname details and return the information.

    Args:
        request: HostnameRequest containing the hostname to look up

    Returns:
        HostnameResponse with the hostname details and session_id
    """
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
    """
    Handle user feedback on SRM recommendations.

    Args:
        request: FeedbackRequest containing feedback details

    Returns:
        FeedbackResponse with success status and feedback ID
    """
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


@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """
    Serve the main HTML page.
    """
    html_path = Path(__file__).parent / "web" / "index.html"

    if not html_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")

    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


@app.post("/api/srm-update-chat", response_model=SrmUpdateChatResponse)
async def srm_update_chat_endpoint(request: SrmUpdateChatRequest):
    """
    SRM update chat endpoint (disabled in this service).

    The SRM update functionality has been moved to the email monitoring agent.
    This endpoint returns a helpful message directing users to use email instead.
    """
    session_id = request.session_id or str(uuid.uuid4())

    response_message = (
        "The SRM update chat feature has been moved to email-based processing. "
        "To update an SRM, please send an email to the configured mailbox with your update request. "
        "The email monitoring agent will process your request automatically.\n\n"
        "For SRM discovery and recommendations, please use the main search interface."
    )

    return SrmUpdateChatResponse(
        session_id=session_id,
        response=response_message,
        status="disabled"
    )


# ============================================================================
# MAINTAINER API ENDPOINTS
# ============================================================================

@app.post("/api/maintainer/search", response_model=MaintainerSearchResponse)
async def maintainer_search_endpoint(request: MaintainerSearchRequest):
    """
    Search for SRMs by keywords (maintainer endpoint).

    This endpoint is used by the CLI maintainer to search for SRMs.
    It calls the maintainer plugin which uses the vector store.

    Args:
        request: Search request with query and top_k

    Returns:
        Search results with SRM IDs, names, categories
    """
    # Validate input
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        # Call maintainer plugin search function
        result_json = await app.state.maintainer_plugin.search_srm(
            query=request.query,
            top_k=request.top_k
        )

        results = json.loads(result_json)

        return MaintainerSearchResponse(results=results)

    except Exception as e:
        print(f"[!] Error in maintainer search: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@app.post("/api/maintainer/get", response_model=MaintainerGetResponse)
async def maintainer_get_endpoint(request: MaintainerGetRequest):
    """
    Get specific SRM by ID (maintainer endpoint).

    Args:
        request: Get request with srm_id

    Returns:
        SRM details or error
    """
    # Validate input
    if not request.srm_id or not request.srm_id.strip():
        raise HTTPException(status_code=400, detail="SRM ID cannot be empty")

    try:
        # Call maintainer plugin get function
        result_json = await app.state.maintainer_plugin.get_srm_by_id(
            srm_id=request.srm_id
        )

        result = json.loads(result_json)

        if not result.get("success"):
            return MaintainerGetResponse(srm=None, error=result.get("error", "Unknown error"))

        return MaintainerGetResponse(srm=result["srm"], error=None)

    except Exception as e:
        print(f"[!] Error in maintainer get: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Get failed: {str(e)}"
        )


@app.post("/api/maintainer/update", response_model=MaintainerUpdateResponse)
async def maintainer_update_endpoint(request: MaintainerUpdateRequest):
    """
    Update SRM metadata (maintainer endpoint).

    Updates fields like owner_notes, hidden_notes, etc. in the vector store.

    Args:
        request: Update request with srm_id and updates dict

    Returns:
        Update result with success status and before/after values
    """
    # Validate input
    if not request.srm_id or not request.srm_id.strip():
        raise HTTPException(status_code=400, detail="SRM ID cannot be empty")
    if not request.updates:
        raise HTTPException(status_code=400, detail="Updates cannot be empty")

    try:
        # Convert updates dict to JSON string for plugin
        updates_json = json.dumps(request.updates)

        # Call maintainer plugin update function
        result_json = await app.state.maintainer_plugin.update_srm_metadata(
            srm_id=request.srm_id,
            updates=updates_json
        )

        result = json.loads(result_json)

        if not result.get("success"):
            return MaintainerUpdateResponse(
                success=False,
                srm_id=request.srm_id,
                error=result.get("error", "Unknown error")
            )

        return MaintainerUpdateResponse(
            success=True,
            srm_id=result["srm_id"],
            srm_name=result.get("srm_name"),
            changes=result.get("changes", []),
            error=None
        )

    except Exception as e:
        print(f"[!] Error in maintainer update: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Update failed: {str(e)}"
        )


@app.get("/api/maintainer/health")
async def maintainer_health_endpoint():
    """
    Health check for maintainer API.

    Verifies that maintainer plugin is initialized and ready.
    """
    try:
        has_plugin = hasattr(app.state, 'maintainer_plugin')
        has_vector_store = hasattr(app.state, 'vector_store')

        status = "healthy" if (has_plugin and has_vector_store) else "degraded"

        return {
            "status": status,
            "service": "maintainer-api",
            "plugin_initialized": has_plugin,
            "vector_store_initialized": has_vector_store,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "recommender-chatbot",
        "timestamp": datetime.now().isoformat()
    }


# ============================================================================
# BACKGROUND TASKS
# ============================================================================

async def _process_feedback_async(
    feedback: FeedbackRecord,
    feedback_processor: FeedbackProcessor,
    telemetry: TelemetryLogger
):
    """
    Process feedback asynchronously in the background.

    Args:
        feedback: FeedbackRecord to process
        feedback_processor: FeedbackProcessor instance
        telemetry: TelemetryLogger instance
    """
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
    """
    Background task to clean up old chat sessions (>1 hour inactive).
    """
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


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AI Concierge Recommender Chatbot Service"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind to"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code changes"
    )

    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        "run_chatbot:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()

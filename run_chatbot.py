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


class ConciergeSearchRequest(BaseModel):
    """Request model for concierge search endpoint."""
    query: str
    top_k: int = 5


class ConciergeSearchResponse(BaseModel):
    """Response model for concierge search endpoint."""
    results: list[SRMSearchResult]


class ConciergeGetRequest(BaseModel):
    """Request model for concierge get by ID endpoint."""
    srm_id: str


class ConciergeGetResponse(BaseModel):
    """Response model for concierge get by ID endpoint."""
    srm: SRMDetail | None
    error: str | None = None


class ConciergeUpdateRequest(BaseModel):
    """Request model for concierge update endpoint."""
    srm_id: str
    updates: dict[str, str]  # Field name -> new value


class ConciergeUpdateResponse(BaseModel):
    """Response model for concierge update endpoint."""
    success: bool
    srm_id: str
    srm_name: str | None = None
    changes: list[ChangeRecord] | None = None
    error: str | None = None


class ConciergeBatchUpdateRequest(BaseModel):
    """Request model for concierge batch update endpoint."""
    filter: dict[str, str]  # Filter criteria (team, type, technology)
    updates: dict[str, str]  # Field name -> new value


class ConciergeBatchUpdateResponse(BaseModel):
    """Response model for concierge batch update endpoint."""
    success: bool
    updated_count: int
    updated_ids: list[str]
    failures: list[dict[str, str]] = []  # List of {srm_id, error}
    error: str | None = None


class TempSRMCreateRequest(BaseModel):
    """Request model for temp SRM creation."""
    name: str
    category: str
    owning_team: str
    use_case: str


class TempSRMCreateResponse(BaseModel):
    """Response model for temp SRM creation."""
    success: bool
    srm_id: str | None = None
    srm: dict | None = None
    error: str | None = None


class TempSRMListResponse(BaseModel):
    """Response model for listing temp SRMs."""
    temp_srms: list[dict]


class TempSRMDeleteRequest(BaseModel):
    """Request model for deleting temp SRM."""
    srm_id: str


class TempSRMDeleteResponse(BaseModel):
    """Response model for deleting temp SRM."""
    success: bool
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

    # Initialize concierge plugin for API endpoints
    print("[*] Initializing concierge plugin...")
    from src.plugins.concierge.srm_metadata_plugin import SRMMetadataPlugin
    app.state.concierge_plugin = SRMMetadataPlugin(
        vector_store=app.state.vector_store
    )
    print("[+] Concierge plugin initialized")

    # Initialize session storage for multi-turn conversations
    app.state.chat_sessions: Dict[str, Dict[str, Any]] = {}
    print("[+] Chat session management initialized")

    # Initialize temp SRM storage
    app.state.temp_srms: Dict[str, Any] = {}  # Maps SRM-TEMP-XXX to SRMRecord
    app.state.temp_id_counter: int = 1
    print("[+] Temp SRM storage initialized")

    # Store server configuration (will be set by main())
    app.state.server_host = os.getenv('CHATBOT_HOST', '0.0.0.0')
    app.state.server_port = int(os.getenv('CHATBOT_PORT', '8000'))

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
# CONCIERGE API ENDPOINTS
# ============================================================================

@app.post("/api/concierge/search", response_model=ConciergeSearchResponse)
async def concierge_search_endpoint(request: ConciergeSearchRequest):
    """
    Search for SRMs by keywords (concierge endpoint).

    This endpoint is used by the CLI concierge to search for SRMs.
    It calls the concierge plugin which uses the vector store.

    Args:
        request: Search request with query and top_k

    Returns:
        Search results with SRM IDs, names, categories
    """
    # Validate input
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        # Call concierge plugin search function
        result_json = await app.state.concierge_plugin.search_srm(
            query=request.query,
            top_k=request.top_k
        )

        results = json.loads(result_json)

        return ConciergeSearchResponse(results=results)

    except Exception as e:
        print(f"[!] Error in concierge search: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@app.post("/api/concierge/get", response_model=ConciergeGetResponse)
async def concierge_get_endpoint(request: ConciergeGetRequest):
    """
    Get specific SRM by ID (concierge endpoint).

    Args:
        request: Get request with srm_id

    Returns:
        SRM details or error
    """
    # Validate input
    if not request.srm_id or not request.srm_id.strip():
        raise HTTPException(status_code=400, detail="SRM ID cannot be empty")

    try:
        # Call concierge plugin get function
        result_json = await app.state.concierge_plugin.get_srm_by_id(
            srm_id=request.srm_id
        )

        result = json.loads(result_json)

        if not result.get("success"):
            return ConciergeGetResponse(srm=None, error=result.get("error", "Unknown error"))

        return ConciergeGetResponse(srm=result["srm"], error=None)

    except Exception as e:
        print(f"[!] Error in concierge get: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Get failed: {str(e)}"
        )


@app.post("/api/concierge/update", response_model=ConciergeUpdateResponse)
async def concierge_update_endpoint(request: ConciergeUpdateRequest):
    """
    Update SRM metadata (concierge endpoint).

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

        # Call concierge plugin update function
        result_json = await app.state.concierge_plugin.update_srm_metadata(
            srm_id=request.srm_id,
            updates=updates_json
        )

        result = json.loads(result_json)

        if not result.get("success"):
            return ConciergeUpdateResponse(
                success=False,
                srm_id=request.srm_id,
                error=result.get("error", "Unknown error")
            )

        return ConciergeUpdateResponse(
            success=True,
            srm_id=result["srm_id"],
            srm_name=result.get("srm_name"),
            changes=result.get("changes", []),
            error=None
        )

    except Exception as e:
        print(f"[!] Error in concierge update: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Update failed: {str(e)}"
        )


@app.post("/api/concierge/batch/update", response_model=ConciergeBatchUpdateResponse)
async def concierge_batch_update_endpoint(request: ConciergeBatchUpdateRequest):
    """
    Batch update SRMs matching filter criteria.

    Supports filtering by:
    - team: Exact match on owning_team
    - type: Exact match on category

    Max 20 SRMs per batch for safety.
    """
    if not request.filter:
        raise HTTPException(status_code=400, detail="Filter cannot be empty")
    if not request.updates:
        raise HTTPException(status_code=400, detail="Updates cannot be empty")

    try:
        # Convert to JSON strings for plugin
        filter_json = json.dumps(request.filter)
        updates_json = json.dumps(request.updates)

        # Call concierge plugin batch update
        result_json = await app.state.concierge_plugin.batch_update_srms(
            filter_json=filter_json,
            updates=updates_json
        )

        result = json.loads(result_json)

        if not result.get("success"):
            return ConciergeBatchUpdateResponse(
                success=False,
                updated_count=0,
                updated_ids=[],
                error=result.get("error", "Unknown error")
            )

        return ConciergeBatchUpdateResponse(
            success=True,
            updated_count=result["updated_count"],
            updated_ids=result["updated_ids"],
            failures=result.get("failures", [])
        )

    except Exception as e:
        print(f"[!] Error in batch update: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Batch update failed: {str(e)}"
        )


@app.get("/api/concierge/health")
async def concierge_health_endpoint():
    """
    Health check for concierge API.

    Verifies that concierge plugin is initialized and ready.
    """
    try:
        has_plugin = hasattr(app.state, 'concierge_plugin')
        has_vector_store = hasattr(app.state, 'vector_store')

        status = "healthy" if (has_plugin and has_vector_store) else "degraded"

        return {
            "status": status,
            "service": "concierge-api",
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


@app.get("/api/concierge/stats")
async def concierge_stats_endpoint():
    """
    Get concierge system statistics.

    Returns current state information for help command:
    - Total SRM count
    - Temp SRM count (always 0 for now)
    - Chatbot URL
    """
    # Build chatbot URL from app state configuration
    host = getattr(app.state, 'server_host', '0.0.0.0')
    port = getattr(app.state, 'server_port', 8000)
    # Use localhost for local binding, otherwise use actual host
    url_host = 'localhost' if host in ('0.0.0.0', '127.0.0.1') else host
    chatbot_url = f"http://{url_host}:{port}"

    try:
        # Count total SRMs in vector store
        # For in-memory store, we need to count records
        total_count = 0
        if hasattr(app.state, 'vector_store'):
            # Search with empty query to get all records (limited to top 1000 for count)
            # Increase limit to 1000 to handle larger SRM datasets
            results = []
            async for result in await app.state.vector_store.search("", top_k=1000):
                results.append(result)
            total_count = len(results)

        # Count temp SRMs
        temp_count = len(app.state.temp_srms) if hasattr(app.state, 'temp_srms') else 0

        return {
            "total_srms": total_count,
            "temp_srms": temp_count,
            "chatbot_url": chatbot_url,
            "status": "healthy"
        }
    except Exception as e:
        return {
            "total_srms": 0,
            "temp_srms": 0,
            "chatbot_url": chatbot_url,
            "status": "error",
            "error": str(e)
        }


@app.post("/api/concierge/temp/create", response_model=TempSRMCreateResponse)
async def temp_srm_create_endpoint(request: TempSRMCreateRequest):
    """
    Create temporary SRM (session-scoped, not persisted).

    Temp SRMs:
    - Get IDs like SRM-TEMP-001, SRM-TEMP-002, etc.
    - Stored in app.state.temp_srms (in-memory)
    - Appear in search results with [TEMP] marker
    - Lost on restart
    """
    try:
        # Generate temp ID
        temp_id = f"SRM-TEMP-{app.state.temp_id_counter:03d}"
        app.state.temp_id_counter += 1

        # Create SRMRecord
        from src.models.srm_record import SRMRecord

        temp_srm = SRMRecord(
            id=temp_id,
            name=request.name,
            category=request.category,
            owning_team=request.owning_team,
            use_case=request.use_case,
            text=f"{request.name} {request.category} {request.use_case} {request.owning_team}",
            owner_notes="[TEMP SRM - Not persisted to CSV]",
            hidden_notes=""
        )

        # Store in temp storage
        app.state.temp_srms[temp_id] = temp_srm

        # Also add to vector store for search (in-memory only)
        await app.state.vector_store.upsert([temp_srm])

        logger.info(f"Created temp SRM: {temp_id} - {request.name}")

        return TempSRMCreateResponse(
            success=True,
            srm_id=temp_id,
            srm={
                "id": temp_id,
                "name": request.name,
                "category": request.category,
                "owning_team": request.owning_team,
                "use_case": request.use_case,
                "owner_notes": temp_srm.owner_notes
            }
        )

    except Exception as e:
        print(f"[!] Error creating temp SRM: {e}")
        return TempSRMCreateResponse(
            success=False,
            error=str(e)
        )


@app.get("/api/concierge/temp/list", response_model=TempSRMListResponse)
async def temp_srm_list_endpoint():
    """List all temporary SRMs."""
    try:
        temp_list = []
        for srm_id, srm in app.state.temp_srms.items():
            temp_list.append({
                "id": srm.id,
                "name": srm.name,
                "category": srm.category,
                "owning_team": srm.owning_team,
                "use_case": srm.use_case
            })

        return TempSRMListResponse(temp_srms=temp_list)

    except Exception as e:
        print(f"[!] Error listing temp SRMs: {e}")
        return TempSRMListResponse(temp_srms=[])


@app.post("/api/concierge/temp/delete", response_model=TempSRMDeleteResponse)
async def temp_srm_delete_endpoint(request: TempSRMDeleteRequest):
    """Delete temporary SRM."""
    try:
        if request.srm_id not in app.state.temp_srms:
            return TempSRMDeleteResponse(
                success=False,
                error=f"Temp SRM {request.srm_id} not found"
            )

        # Remove from temp storage
        del app.state.temp_srms[request.srm_id]

        # Note: Can't easily remove from vector store in SK
        # It will be gone on restart anyway

        logger.info(f"Deleted temp SRM: {request.srm_id}")

        return TempSRMDeleteResponse(success=True)

    except Exception as e:
        print(f"[!] Error deleting temp SRM: {e}")
        return TempSRMDeleteResponse(
            success=False,
            error=str(e)
        )


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

    # Set environment variables for server configuration so startup_event can access them
    import os
    os.environ['CHATBOT_HOST'] = args.host
    os.environ['CHATBOT_PORT'] = str(args.port)

    import uvicorn

    uvicorn.run(
        "run_chatbot:app",
        host=args.host,
        port=args.port,
        reload=args.reload
    )


if __name__ == "__main__":
    main()

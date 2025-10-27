'''
AI Concierge - SRM Discovery Chatbot

Interactive CLI for finding the right Service Request Model (SRM).
'''

import asyncio
import uuid

from semantic_kernel.processes.kernel_process import KernelProcessEvent
from semantic_kernel.processes.local_runtime.local_kernel_process import start

from src.utils.kernel_builder import create_kernel
from src.utils.telemetry import TelemetryLogger
from src.utils.store_factory import create_vector_store
from src.utils.debug_config import debug_print
from src.data.data_loader import SRMDataLoader
from src.processes.discovery.srm_discovery_process import SRMDiscoveryProcess
from src.processes.discovery.hostname_lookup_process import HostnameLookupProcess


async def initialize_system():
    '''
    Initialize the kernel, vector store, build processes, and load SRM data.
    
    Returns:
        Tuple of (kernel, vector_store, srm_process, hostname_process, session_id)
    '''
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
    
    # Build process definitions once (they will be reused for all requests)
    print("[*] Building process definitions...")
    srm_process_builder = SRMDiscoveryProcess.create_process()
    srm_process = srm_process_builder.build()
    
    hostname_process_builder = HostnameLookupProcess.create_process()
    hostname_process = hostname_process_builder.build()
    print("[+] Process definitions built")
    
    # Generate session ID
    session_id = str(uuid.uuid4())[:8]
    
    return kernel, vector_store, srm_process, hostname_process, session_id


async def run_query(
    kernel,
    vector_store,
    kernel_process,
    user_query: str,
    session_id: str,
    telemetry: TelemetryLogger
) -> str:
    '''
    Run a single query through the SRM discovery process.
    
    Args:
        kernel: Semantic Kernel instance
        vector_store: Vector store with SRM data
        kernel_process: Pre-built process definition (reused for all requests)
        user_query: The user's query
        session_id: Session identifier
        telemetry: Telemetry logger
        
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
        async with await start(
            process=kernel_process,
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
    kernel_process,
    user_query: str,
    session_id: str,
    telemetry: TelemetryLogger
) -> str:
    '''
    Run a hostname lookup query.
    
    Args:
        kernel: Semantic Kernel instance
        kernel_process: Pre-built process definition (reused for all requests)
        user_query: The hostname to look up
        session_id: Session identifier
        telemetry: Telemetry logger
        
    Returns:
        The formatted hostname information
    '''
    # Create initial event data with user_query, session_id, and kernel
    # Note: SK ProcessBuilder requires passing dependencies through events, not constructors
    # result_container will be populated by steps with the final output
    result_container = {}
    initial_data = {
        "user_query": user_query,
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
        async with await start(
            process=kernel_process,
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


async def interactive_loop():
    '''
    Main interactive conversation loop.
    '''
    # Initialize system (processes are built once here)
    kernel, vector_store, srm_process, hostname_process, session_id = await initialize_system()
    telemetry = TelemetryLogger()
    
    # Welcome message
    print("\n" + "="*60)
    print("AI Concierge - SRM Discovery & Hostname Lookup")
    print("="*60)
    print("\nWelcome! I can help you with:")
    print("1. Find the right Service Request Model (SRM) for your needs")
    print("2. Look up hostname and server details")
    print("\nExamples:")
    print("  SRM Discovery:")
    print("    - 'I need to expand storage on a file share'")
    print("    - 'How do I restore deleted files?'")
    print("    - 'Need to add more CPU to a VM'")
    print("\n  Hostname Lookup (use 'lookup:' prefix):")
    print("    - 'lookup: srv-vmcap-001-prod'")
    print("    - 'lookup: vmcap' (partial match)")
    print("\nType 'exit' to quit.\n")
    
    # Interactive loop
    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("\nThanks for using AI Concierge! Goodbye.\n")
                break
            
            # Check if this is a hostname lookup query
            is_hostname_lookup = False
            hostname_query = user_input
            
            if user_input.lower().startswith('lookup:') or user_input.lower().startswith('hostname:'):
                is_hostname_lookup = True
                # Extract the hostname from the prefix
                if user_input.lower().startswith('lookup:'):
                    hostname_query = user_input[7:].strip()
                elif user_input.lower().startswith('hostname:'):
                    hostname_query = user_input[9:].strip()
            
            # Process query based on type
            print("\n[*] Searching...\n")
            
            if is_hostname_lookup:
                # Hostname lookup process (reusing pre-built process)
                response = await run_hostname_query(
                    kernel=kernel,
                    kernel_process=hostname_process,
                    user_query=hostname_query,
                    session_id=session_id,
                    telemetry=telemetry
                )
            else:
                # SRM discovery process (reusing pre-built process)
                response = await run_query(
                    kernel=kernel,
                    vector_store=vector_store,
                    kernel_process=srm_process,
                    user_query=user_input,
                    session_id=session_id,
                    telemetry=telemetry
                )
            
            # Display response
            print(f"Assistant:\n{response}\n")
        
        except KeyboardInterrupt:
            print("\n\nThanks for using AI Concierge! Goodbye.\n")
            break
        except EOFError:
            print("\n\nThanks for using AI Concierge! Goodbye.\n")
            break
        except Exception as e:
            print(f"\n[!] Error: {e}\n")
            telemetry.log_error(
                session_id=session_id,
                error_code="MAIN_LOOP_ERROR",
                error_message=str(e)
            )


async def run_test_queries():
    '''
    Run a set of test queries to validate the system.
    '''
    print("\n" + "="*60)
    print("Running Test Queries")
    print("="*60 + "\n")
    
    # Initialize system (processes are built once here)
    kernel, vector_store, srm_process, hostname_process, session_id = await initialize_system()
    telemetry = TelemetryLogger()
    
    test_queries = [
        "I need to add storage to a file share",
        "Restore deleted files from last week",
        "Want backup for new application",
        "Need more space",  # Ambiguous - should ask for clarification
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n--- Test {i} ---")
        print(f"Query: {query}")
        print()
        
        response = await run_query(
            kernel=kernel,
            vector_store=vector_store,
            kernel_process=srm_process,
            user_query=query,
            session_id=f"test-{i}",
            telemetry=telemetry
        )
        
        print(f"Response:\n{response}")
        print("\n" + "-"*60)


async def main():
    '''Main entry point.'''
    import sys
    from src.utils.debug_config import set_debug
    
    # Parse command-line arguments
    args = sys.argv[1:]
    test_mode = '--test' in args
    debug_mode = '--debug' in args
    
    # Set debug mode
    set_debug(debug_mode)
    
    if test_mode:
        # Run test queries
        await run_test_queries()
    else:
        # Run interactive loop
        await interactive_loop()


if __name__ == "__main__":
    asyncio.run(main())


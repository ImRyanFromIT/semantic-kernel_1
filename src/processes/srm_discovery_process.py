'''
SRM Discovery Process definition.

This process implements the state machine for finding and recommending SRMs.
'''

from enum import Enum

from semantic_kernel import Kernel
from semantic_kernel.processes.process_builder import ProcessBuilder

from src.memory.vector_store_base import VectorStoreBase
from src.processes.steps.validation_step import ValidationStep
from src.processes.steps.clarity_step import ClarityStep
from src.processes.steps.retrieval_step import RetrievalStep
from src.processes.steps.rerank_step import RerankStep
from src.processes.steps.answer_step import AnswerStep


class SRMDiscoveryProcess:
    '''
    SRM Discovery Process - helps users find the right SRM.
    
    Process Flow:
    1. ValidationStep: Validate input against guardrails (length, patterns, content)
    2. ClarityStep: Analyze query and determine if clarification needed
    3. RetrievalStep: Search for candidate SRMs using vector similarity
    4. RerankStep: Score and select the best recommendation
    5. AnswerStep: Format and return the final answer
    '''
    
    class ProcessEvents(Enum):
        '''Process-level events.'''
        StartProcess = "StartProcess"
        UserResponse = "UserResponse"
        ProcessComplete = "ProcessComplete"
    
    @staticmethod
    def create_process(
        kernel: Kernel,
        vector_store: VectorStoreBase,
        process_name: str = "SRMDiscoveryProcess"
    ) -> ProcessBuilder:
        '''
        Create the SRM Discovery process.
        
        Args:
            kernel: The Semantic Kernel instance
            vector_store: The vector store containing SRM records
            process_name: Name for the process
            
        Returns:
            ProcessBuilder configured with all steps and transitions
        '''
        # Create process builder
        process_builder = ProcessBuilder(name=process_name)
        
        ValidationStep.set_kernel(kernel)
        ClarityStep.set_kernel(kernel)
        AnswerStep.set_kernel(kernel)
        
        # Add steps
        validation_step = process_builder.add_step(ValidationStep)
        clarity_step = process_builder.add_step(ClarityStep)
        retrieval_step = process_builder.add_step(RetrievalStep)
        rerank_step = process_builder.add_step(RerankStep)
        answer_step = process_builder.add_step(AnswerStep)
        
        # Process start -> ValidationStep
        # The initial event data will contain user_query, vector_store, session_id as a dict
        process_builder.on_input_event(
            SRMDiscoveryProcess.ProcessEvents.StartProcess.value
        ).send_event_to(validation_step, parameter_name="input_data")
        
        # ValidationStep -> ClarityStep (if input is valid)
        validation_step.on_event(
            ValidationStep.OutputEvents.InputValid.value
        ).send_event_to(clarity_step, parameter_name="input_data")
        
        # ValidationStep -> (stop process if input is rejected)
        validation_step.on_event(
            ValidationStep.OutputEvents.InputRejected.value
        ).stop_process()
        
        # ClarityStep -> RetrievalStep (if clarity obtained)
        # Pass the entire event data dict containing all context
        clarity_step.on_event(
            ClarityStep.OutputEvents.ClarityObtained.value
        ).send_event_to(retrieval_step, parameter_name="input_data")
        
        # ClarityStep -> (wait for user response if clarification needed)
        # In a real implementation, this would pause and wait for user input
        # For now, we'll handle this in the main loop
        clarity_step.on_event(
            ClarityStep.OutputEvents.NeedsClarification.value
        ).stop_process()
        
        # RetrievalStep -> RerankStep (if candidates found)
        # Pass the entire event data dict
        retrieval_step.on_event(
            RetrievalStep.OutputEvents.CandidatesFound.value
        ).send_event_to(rerank_step, parameter_name="input_data")
        
        # RetrievalStep -> AnswerStep (if no candidates)
        retrieval_step.on_event(
            RetrievalStep.OutputEvents.NoCandidates.value
        ).send_event_to(answer_step, parameter_name="input_data")
        
        # RerankStep -> AnswerStep
        # Pass the entire event data dict
        rerank_step.on_event(
            RerankStep.OutputEvents.RecommendationSelected.value
        ).send_event_to(answer_step, parameter_name="input_data")
        
        rerank_step.on_event(
            RerankStep.OutputEvents.MultipleOptions.value
        ).send_event_to(answer_step, parameter_name="input_data")
        
        # AnswerStep -> Process complete
        answer_step.on_event(
            AnswerStep.OutputEvents.AnswerPublished.value
        ).stop_process()
        
        answer_step.on_event(
            AnswerStep.OutputEvents.FallbackAnswer.value
        ).stop_process()
        
        return process_builder


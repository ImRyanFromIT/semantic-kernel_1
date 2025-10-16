'''
Hostname Lookup Process definition.

This process implements the workflow for looking up hostname information.
'''

from enum import Enum

from semantic_kernel import Kernel
from semantic_kernel.processes.process_builder import ProcessBuilder

from src.processes.steps.hostname_validation_step import HostnameValidationStep
from src.processes.steps.hostname_lookup_step import HostnameLookupStep
from src.processes.steps.hostname_format_step import HostnameFormatStep


class HostnameLookupProcess:
    '''
    Hostname Lookup Process - helps users find hostname details.
    
    Process Flow:
    1. HostnameValidationStep: Simple validation for hostname queries (length, characters)
    2. HostnameLookupStep: Search for hostname in Azure AI Search (exact and partial)
    3. HostnameFormatStep: Format and return the result
    '''
    
    class ProcessEvents(Enum):
        '''Process-level events.'''
        StartProcess = "StartProcess"
        ProcessComplete = "ProcessComplete"
    
    @staticmethod
    def create_process(
        kernel: Kernel,
        process_name: str = "HostnameLookupProcess"
    ) -> ProcessBuilder:
        '''
        Create the Hostname Lookup process.
        
        Args:
            kernel: The Semantic Kernel instance
            process_name: Name for the process
            
        Returns:
            ProcessBuilder configured with all steps and transitions
        '''
        # Create process builder
        process_builder = ProcessBuilder(name=process_name)
        
        # Set kernel for steps (available for future agent-based enhancements)
        HostnameValidationStep.set_kernel(kernel)
        
        # Add steps
        validation_step = process_builder.add_step(HostnameValidationStep)
        lookup_step = process_builder.add_step(HostnameLookupStep)
        format_step = process_builder.add_step(HostnameFormatStep)
        
        # Process start -> HostnameValidationStep
        # The initial event data will contain user_query and session_id as a dict
        process_builder.on_input_event(
            HostnameLookupProcess.ProcessEvents.StartProcess.value
        ).send_event_to(validation_step, parameter_name="input_data")
        
        # HostnameValidationStep -> HostnameLookupStep (if input is valid)
        validation_step.on_event(
            HostnameValidationStep.OutputEvents.InputValid.value
        ).send_event_to(lookup_step, parameter_name="input_data")
        
        # HostnameValidationStep -> (stop process if input is rejected)
        validation_step.on_event(
            HostnameValidationStep.OutputEvents.InputRejected.value
        ).stop_process()
        
        # HostnameLookupStep -> HostnameFormatStep (exact match)
        lookup_step.on_event(
            HostnameLookupStep.OutputEvents.ExactMatchFound.value
        ).send_event_to(format_step, parameter_name="input_data")
        
        # HostnameLookupStep -> HostnameFormatStep (multiple matches)
        lookup_step.on_event(
            HostnameLookupStep.OutputEvents.MultipleMatchesFound.value
        ).send_event_to(format_step, parameter_name="input_data")
        
        # HostnameLookupStep -> HostnameFormatStep (no match)
        lookup_step.on_event(
            HostnameLookupStep.OutputEvents.NoMatchFound.value
        ).send_event_to(format_step, parameter_name="input_data")
        
        # HostnameFormatStep -> Process complete
        format_step.on_event(
            HostnameFormatStep.OutputEvents.ResultFormatted.value
        ).stop_process()
        
        return process_builder


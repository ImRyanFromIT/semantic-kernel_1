'''
Hostname validation step - LLM-based validation for hostname queries.
'''

from enum import Enum

from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function
from semantic_kernel.processes.kernel_process import (
    KernelProcessStep,
    KernelProcessStepContext,
    KernelProcessEventVisibility,
)

from src.utils.debug_config import debug_print
from src.utils.result_store import store_result


class HostnameValidationStep(KernelProcessStep):
    '''
    Process step to validate hostname queries using LLM.
    
    Uses semantic kernel to invoke the hostname_validation plugin
    to intelligently validate hostname queries.
    '''
    
    class OutputEvents(Enum):
        '''Output events from the validation step.'''
        InputValid = "InputValid"
        InputRejected = "InputRejected"
    
    @kernel_function(name="validate_hostname_query")
    async def validate_hostname_query(
        self,
        context: KernelProcessStepContext,
        input_data: dict,
    ) -> None:
        '''
        Validate hostname query input using LLM.
        
        Args:
            context: Process step context
            input_data: Dictionary containing user_query and session_id
        '''
        user_query = input_data.get('user_query', '').strip()
        session_id = input_data.get('session_id', '')
        kernel = input_data.get('kernel')
        
        debug_print(f"DEBUG HostnameValidationStep: Validating hostname query for session {session_id}")
        debug_print(f"DEBUG HostnameValidationStep: Query: '{user_query}'")
        
        # Use LLM to validate the hostname query - get kernel from input_data
        is_valid, rejection_reason = await self._validate_with_llm(user_query, kernel)
        
        if not is_valid:
            debug_print(f"DEBUG HostnameValidationStep: Input rejected - {rejection_reason}")
            
            # Format rejection message based on reason
            rejection_message = self._format_rejection_message(rejection_reason)
            
            # Store rejection result
            store_result(session_id, {
                'rejection': rejection_message,
                'reason': rejection_reason
            })
            
            # Emit rejection event
            await context.emit_event(
                process_event=self.OutputEvents.InputRejected.value,
                data={
                    "rejection_message": rejection_message,
                    "rejection_reason": rejection_reason,
                    "user_query": user_query,
                    "session_id": session_id,
                },
                visibility=KernelProcessEventVisibility.Public
            )
        else:
            debug_print(f"DEBUG HostnameValidationStep: Input is valid")
            
            # Pass through to next step (include kernel for subsequent steps)
            await context.emit_event(
                process_event=self.OutputEvents.InputValid.value,
                data=input_data,  # kernel is already in input_data
            )
    
    async def _validate_with_llm(self, hostname_query: str, kernel: Kernel) -> tuple[bool, str]:
        '''
        Use LLM to validate the hostname query.
        
        Args:
            hostname_query: The hostname query to validate
            kernel: Semantic Kernel instance
            
        Returns:
            Tuple of (is_valid, rejection_reason)
        '''
        if not kernel:
            debug_print("DEBUG HostnameValidationStep: No kernel available for LLM validation")
            return True, ''  # Fail open if no kernel
        
        try:
            # Use the plugin loader utility to invoke the hostname_validation plugin
            from src.utils.plugin_loader import invoke_plugin
            
            validation_result = await invoke_plugin(
                kernel=kernel,
                plugin_name="hostname_validation",
                function_name="hostname_validation",
                hostname_query=hostname_query
            )
            
            debug_print(f"DEBUG HostnameValidationStep: LLM validation result: {validation_result}")
            
            if validation_result.startswith('INVALID'):
                # Extract the reason from the validation result
                reason = self._extract_rejection_reason(validation_result)
                return False, reason
            
            return True, ''
            
        except Exception as e:
            debug_print(f"DEBUG HostnameValidationStep: Error in LLM validation: {e}")
            # Fail open - allow input if LLM check fails
            return True, ''
    
    def _extract_rejection_reason(self, validation_result: str) -> str:
        '''
        Extract the rejection reason from LLM validation result.
        
        Args:
            validation_result: The validation result from LLM (e.g., "INVALID: empty")
            
        Returns:
            The rejection reason
        '''
        # Parse "INVALID: reason" format
        if ':' in validation_result:
            parts = validation_result.split(':', 1)
            if len(parts) == 2:
                return parts[1].strip()
        
        return 'invalid_hostname'
    
    def _format_rejection_message(self, rejection_reason: str) -> str:
        '''
        Format a user-friendly rejection message based on the reason.
        
        Args:
            rejection_reason: The rejection reason from validation
            
        Returns:
            Formatted rejection message
        '''
        reason_messages = {
            'empty': "Please provide a hostname to look up.",
            'too_long': "Hostname query is too long. Please provide a valid hostname (max 253 characters).",
            'invalid_characters': "Hostname contains invalid characters. Use only letters, numbers, hyphens, and dots.",
            'natural_language': "It looks like you entered a full question. For IT service requests, use the main search (without 'lookup:' prefix).\n\nFor hostname lookups, use: lookup: <hostname>",
            'gibberish': "The hostname query doesn't appear to be valid. Please provide a valid hostname or partial hostname pattern.",
            'invalid_hostname': "The hostname query doesn't appear to be valid. Please provide a valid hostname or partial hostname pattern.",
        }
        
        return reason_messages.get(rejection_reason, 
            "Unable to process this hostname query. Please provide a valid hostname.")


'''
Hostname validation step - LLM-based validation for hostname queries.
'''

import logging
from enum import Enum

from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function
from semantic_kernel.processes.kernel_process import (
    KernelProcessStep,
    KernelProcessStepContext,
    KernelProcessEventVisibility,
)
from semantic_kernel.processes.kernel_process.kernel_process_step_metadata import kernel_process_step_metadata


# Configure logger
logger = logging.getLogger(__name__)


@kernel_process_step_metadata("HostnameValidationStep.V1")
class HostnameValidationStep(KernelProcessStep):
    '''
    Process step to validate hostname queries using LLM.
    
    Uses semantic kernel to invoke the hostname_validation plugin
    to intelligently validate hostname queries.
    
    Note: Kernel is passed through event data due to SK ProcessBuilder constraints.
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
        result_container = input_data.get('result_container', {})
        
        logger.info("Validating hostname query", extra={"session_id": session_id, "query": user_query})
        
        # Use LLM to validate the hostname query using kernel from input_data
        is_valid, rejection_reason = await self._validate_with_llm(user_query, kernel)
        
        if not is_valid:
            logger.warning("Hostname query rejected", extra={"session_id": session_id, "reason": rejection_reason})
            
            # Format rejection message based on reason
            rejection_message = self._format_rejection_message(rejection_reason)
            
            # Store result in container for entry point to retrieve
            result_container['rejection_message'] = rejection_message
            result_container['rejection_reason'] = rejection_reason
            
            # Emit rejection event with answer data
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
            logger.info("Hostname query validated successfully", extra={"session_id": session_id})
            
            # Pass through to next step with dependencies
            await context.emit_event(
                process_event=self.OutputEvents.InputValid.value,
                data={
                    "user_query": user_query,
                    "session_id": session_id,
                    "kernel": kernel,
                    "result_container": result_container,
                },
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
            logger.debug("No kernel available for LLM validation, failing open")
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
            
            logger.debug("LLM validation result received", extra={"result": validation_result})
            
            if validation_result.startswith('INVALID'):
                # Extract the reason from the validation result
                reason = self._extract_rejection_reason(validation_result)
                return False, reason
            
            return True, ''
            
        except Exception as e:
            logger.warning("Error in LLM validation, failing open", extra={"error": str(e)})
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


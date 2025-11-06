'''
Validation step - Validate user input for guardrails enforcement.

This step checks for basic input validation (length, patterns) and uses
LLM-based content filtering to detect junk, spam, and gibberish.
'''

import logging
import re
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

# Validation configuration constants
MIN_LENGTH = 3
MAX_LENGTH = 500
MAX_SPECIAL_CHAR_RATIO = 0.3
MAX_REPETITION_COUNT = 5


@kernel_process_step_metadata("ValidationStep.V1")
class ValidationStep(KernelProcessStep):
    '''
    Process step to validate user input against guardrails.
    
    Performs multiple validation checks:
    1. Length validation (min/max bounds)
    2. Character pattern analysis (special chars, repetition)
    3. LLM-based content filtering (gibberish, spam detection)
    
    Note: Kernel is passed through event data due to SK ProcessBuilder constraints.
    '''
    
    class OutputEvents(Enum):
        '''Output events from the validation step.'''
        InputValid = "InputValid"
        InputRejected = "InputRejected"
    
    @kernel_function(name="validate_input")
    async def validate_input(
        self,
        context: KernelProcessStepContext,
        input_data: dict,
    ) -> None:
        '''
        Validate user input against guardrails.
        
        Args:
            context: Process step context
            input_data: Dictionary containing user_query, vector_store, session_id, kernel
        '''
        user_query = input_data.get('user_query', '')
        vector_store = input_data.get('vector_store')
        session_id = input_data.get('session_id', '')
        kernel = input_data.get('kernel')
        result_container = input_data.get('result_container', {})
        
        logger.info("Validating input", extra={"session_id": session_id, "query_length": len(user_query)})
        
        # Run validation checks - kernel from input_data
        is_valid, rejection_reason = await self._run_validation_checks(user_query, kernel)
        
        if not is_valid:
            logger.warning("Input rejected", extra={"session_id": session_id, "reason": rejection_reason})
            
            # Format rejection message
            from src.utils.rejection_responses import format_rejection_response
            rejection_message = format_rejection_response(rejection_reason)
            
            # Log rejection to telemetry
            from src.utils.telemetry import TelemetryLogger
            telemetry = TelemetryLogger()
            telemetry.log_input_rejected(
                session_id=session_id,
                user_query=user_query,
                rejection_reason=rejection_reason
            )
            
            # Store result in container for entry point to retrieve
            result_container['rejection_message'] = rejection_message
            result_container['rejection_reason'] = rejection_reason
            
            # Emit rejection event with business data only
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
            logger.info("Input validated successfully", extra={"session_id": session_id})
            
            # Pass through to next step with dependencies
            await context.emit_event(
                process_event=self.OutputEvents.InputValid.value,
                data={
                    "user_query": user_query,
                    "vector_store": vector_store,
                    "session_id": session_id,
                    "kernel": kernel,
                    "result_container": result_container,
                },
            )
    
    async def _run_validation_checks(self, user_query: str, kernel: Kernel) -> tuple[bool, str]:
        '''
        Run all validation checks on the user input.
        
        Args:
            user_query: The user's input to validate
            kernel: Semantic Kernel instance for LLM validation
            
        Returns:
            Tuple of (is_valid, rejection_reason)
        '''
        # Check 1: Length validation
        if not user_query or len(user_query.strip()) < MIN_LENGTH:
            return False, 'too_short'
        
        if len(user_query) > MAX_LENGTH:
            return False, 'too_long'
        
        # Check 2: Pattern validation
        pattern_valid, pattern_reason = self._check_patterns(user_query)
        if not pattern_valid:
            return False, pattern_reason
        
        # Check 3: LLM-based content validation
        try:
            content_valid, content_reason = await self._check_content_with_llm(user_query, kernel)
            if not content_valid:
                return False, content_reason
        except Exception as e:
            logger.debug("LLM validation failed, failing open", extra={"error": str(e)})

        return True, ''
    
    def _check_patterns(self, user_query: str) -> tuple[bool, str]:
        '''
        Check for problematic patterns in the input.
        
        Args:
            user_query: The user's input
            
        Returns:
            Tuple of (is_valid, rejection_reason)
        '''
        # Count alphanumeric vs special characters
        alphanumeric_count = sum(c.isalnum() or c.isspace() for c in user_query)
        total_count = len(user_query)
        
        if total_count > 0:
            special_char_ratio = 1 - (alphanumeric_count / total_count)
            if special_char_ratio > MAX_SPECIAL_CHAR_RATIO:
                return False, 'excessive_special_chars'
        
        # Check for excessive repetition of characters
        if self._has_excessive_repetition(user_query):
            return False, 'repetitive_content'
        
        return True, ''
    
    def _has_excessive_repetition(self, text: str) -> bool:
        '''
        Check if text has excessive character or word repetition.
        
        Args:
            text: The text to check
            
        Returns:
            True if excessive repetition detected
        '''
        # Check for repeated characters (e.g., "aaaaaaa")
        if re.search(r'(.)\1{' + str(MAX_REPETITION_COUNT) + ',}', text):
            return True
        
        # Check for repeated words (e.g., "test test test test test test")
        words = text.lower().split()
        if len(words) > MAX_REPETITION_COUNT:
            word_counts = {}
            for word in words:
                word_counts[word] = word_counts.get(word, 0) + 1
                if word_counts[word] > MAX_REPETITION_COUNT:
                    return True
        
        return False
    
    async def _check_content_with_llm(self, user_query: str, kernel: Kernel) -> tuple[bool, str]:
        '''
        Use LLM to check if content is genuine or junk.
        
        Args:
            user_query: The user's input
            kernel: Semantic Kernel instance
            
        Returns:
            Tuple of (is_valid, rejection_reason)
        '''
        if not kernel:
            logger.debug("No kernel available for LLM validation, failing open")
            return True, ''  # Fail open if no kernel
        
        try:
            # Use the plugin loader utility to invoke the already-loaded plugin
            from src.utils.plugin_loader import invoke_plugin
            
            validation_result = await invoke_plugin(
                kernel=kernel,
                plugin_name="content_validation",
                function_name="content_validation",
                user_input=user_query
            )
            
            logger.debug("LLM validation result received", extra={"result": validation_result})
            
            if validation_result.startswith('INVALID'):
                # Map LLM reason to our rejection categories
                from src.utils.rejection_responses import get_rejection_reason_from_validation
                rejection_reason = get_rejection_reason_from_validation(validation_result)
                return False, rejection_reason
            
            return True, ''
            
        except Exception as e:
            logger.warning("Error in LLM validation, failing open", extra={"error": str(e)})
            # Fail open - allow input if LLM check fails
            return True, ''


"""
Centralized error handling and retry logic for the SRM Archivist Agent.
"""

import time
import logging
from typing import Callable, Any, Optional, Type
from functools import wraps
from enum import Enum


class ErrorType(Enum):
    """Types of errors that can occur."""
    GRAPH_API_AUTH = "graph_api_auth"
    GRAPH_API_CALL = "graph_api_call"
    AZURE_SEARCH_CONNECTION = "azure_search_connection"
    AZURE_SEARCH_OPERATION = "azure_search_operation"
    LLM_CALL = "llm_call"
    LLM_PARSE = "llm_parse"
    STATE_FILE_CORRUPTION = "state_file_corruption"
    STATE_FILE_IO = "state_file_io"
    MASS_EMAIL_GUARDRAIL = "mass_email_guardrail"
    CONFIGURATION = "configuration"
    UNKNOWN = "unknown"


class ErrorHandler:
    """
    Centralized error handling with retry logic and escalation.
    """
    
    def __init__(self, 
                 max_retries: int = 3,
                 retry_delay: int = 300,
                 logger: Optional[logging.Logger] = None):
        """
        Initialize error handler.
        
        Args:
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            logger: Logger instance for error reporting
        """
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.logger = logger or logging.getLogger(__name__)
        
    def with_retry(self, 
                   error_type: ErrorType,
                   retryable_exceptions: tuple = (Exception,),
                   escalate_after_retries: bool = True):
        """
        Decorator for automatic retry with exponential backoff.
        
        Args:
            error_type: Type of error for logging
            retryable_exceptions: Tuple of exception types to retry
            escalate_after_retries: Whether to escalate after max retries
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                last_exception = None
                
                for attempt in range(self.max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    
                    except retryable_exceptions as e:
                        last_exception = e
                        
                        if attempt < self.max_retries:
                            delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                            self.logger.warning(
                                f"Attempt {attempt + 1} failed for {error_type.value}: {e}. "
                                f"Retrying in {delay} seconds..."
                            )
                            time.sleep(delay)
                        else:
                            self.logger.error(
                                f"All {self.max_retries + 1} attempts failed for {error_type.value}: {e}"
                            )
                            
                            if escalate_after_retries:
                                self.escalate_error(error_type, str(e), func.__name__)
                            
                            raise
                
                # Should never reach here, but just in case
                if last_exception:
                    raise last_exception
                    
            return wrapper
        return decorator
    
    def handle_error(self, 
                     error_type: ErrorType, 
                     error: Exception, 
                     context: str = "",
                     escalate: bool = False) -> None:
        """
        Handle an error with appropriate logging and escalation.
        
        Args:
            error_type: Type of error that occurred
            error: The exception that was raised
            context: Additional context about when/where error occurred
            escalate: Whether to escalate to human support
        """
        error_msg = f"{error_type.value}: {error}"
        if context:
            error_msg = f"{error_msg} (Context: {context})"
        
        self.logger.error(error_msg)
        
        if escalate:
            self.escalate_error(error_type, str(error), context)
    
    def escalate_error(self, 
                       error_type: ErrorType, 
                       error_message: str, 
                       context: str = "") -> None:
        """
        Escalate error to human support team.
        
        Args:
            error_type: Type of error that occurred
            error_message: Description of the error
            context: Additional context information
        """
        escalation_msg = (
            f"[SRM Agent Escalation] {error_type.value.upper()}\n"
            f"Error: {error_message}\n"
            f"Context: {context}\n"
            f"Time: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n"
            f"Action Required: Manual intervention needed"
        )
        
        # Log the escalation
        self.logger.critical(f"ESCALATION: {escalation_msg}")
        
        # For now, just log the escalation
        print(f"[!] ESCALATION REQUIRED: {escalation_msg}")
    
    def should_retry(self, error: Exception, error_type: ErrorType) -> bool:
        """
        Determine if an error should be retried.
        
        Args:
            error: The exception that occurred
            error_type: Type of error
            
        Returns:
            True if error should be retried, False otherwise
        """
        # Define non-retryable error patterns
        non_retryable_patterns = {
            ErrorType.GRAPH_API_AUTH: ["invalid_client", "invalid_grant", "unauthorized"],
            ErrorType.AZURE_SEARCH_CONNECTION: ["authentication", "forbidden"],
            ErrorType.LLM_PARSE: ["json", "parse", "format"],
            ErrorType.CONFIGURATION: ["missing", "invalid", "not found"],
            ErrorType.MASS_EMAIL_GUARDRAIL: ["threshold", "guardrail"],
        }
        
        error_str = str(error).lower()
        
        # Check if error type has non-retryable patterns
        if error_type in non_retryable_patterns:
            for pattern in non_retryable_patterns[error_type]:
                if pattern in error_str:
                    return False
        
        # Default to retryable for transient errors
        return True
    
    def get_error_type(self, error: Exception, context: str = "") -> ErrorType:
        """
        Classify error type based on exception and context.
        
        Args:
            error: The exception that occurred
            context: Context where error occurred
            
        Returns:
            ErrorType classification
        """
        error_str = str(error).lower()
        context_lower = context.lower()
        
        # Graph API errors
        if "graph" in context_lower or "microsoft" in context_lower:
            if "auth" in error_str or "token" in error_str:
                return ErrorType.GRAPH_API_AUTH
            return ErrorType.GRAPH_API_CALL
        
        # Azure Search errors
        if "search" in context_lower or "azure" in context_lower:
            if "connection" in error_str or "timeout" in error_str:
                return ErrorType.AZURE_SEARCH_CONNECTION
            return ErrorType.AZURE_SEARCH_OPERATION
        
        # LLM errors
        if "llm" in context_lower or "openai" in context_lower:
            if "json" in error_str or "parse" in error_str:
                return ErrorType.LLM_PARSE
            return ErrorType.LLM_CALL
        
        # State file errors
        if "state" in context_lower or "jsonl" in context_lower:
            if "corrupt" in error_str or "invalid" in error_str:
                return ErrorType.STATE_FILE_CORRUPTION
            return ErrorType.STATE_FILE_IO
        
        # Configuration errors
        if "config" in context_lower or "environment" in context_lower:
            return ErrorType.CONFIGURATION
        
        # Mass email guardrail
        if "mass" in context_lower or "threshold" in context_lower:
            return ErrorType.MASS_EMAIL_GUARDRAIL
        
        return ErrorType.UNKNOWN

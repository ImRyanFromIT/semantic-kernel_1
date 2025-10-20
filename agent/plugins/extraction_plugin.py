"""
Extraction plugin for LLM-based data extraction from emails.
"""

import json
from pathlib import Path
from typing import Dict, Any
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function

from ..utils.error_handler import ErrorHandler, ErrorType
from ..models.change_request import ChangeRequest, ChangeType


class ExtractionPlugin:
    """
    Semantic Kernel plugin for LLM-based data extraction from emails.
    
    Uses prompt-based function to extract structured SRM change request data.
    """
    
    def __init__(self, kernel: Kernel, error_handler: ErrorHandler):
        """
        Initialize extraction plugin.
        
        Args:
            kernel: Semantic Kernel instance with LLM service
            error_handler: ErrorHandler for retry logic
        """
        self.kernel = kernel
        self.error_handler = error_handler
        
        # Load the data extraction prompt function
        self._load_prompt_function()
    
    def _load_prompt_function(self):
        """Load the data extraction prompt from directory."""
        try:
            import json
            from semantic_kernel.functions import KernelFunction, KernelPlugin
            from semantic_kernel.prompt_template import PromptTemplateConfig
            
            # Get the path to the data_extraction prompt directory
            plugin_dir = Path(__file__).parent / "data_extraction"
            config_file = plugin_dir / "config.json"
            prompt_file = plugin_dir / "skprompt.txt"
            
            # Load config and prompt
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
            
            # Create prompt template config
            template_config = PromptTemplateConfig(
                name="data_extraction",
                description=config_data.get('description', ''),
                template=prompt_template,
                execution_settings=config_data.get('execution_settings', {}),
            )
            
            # Create function from prompt
            function = KernelFunction.from_prompt(
                function_name="data_extraction",
                plugin_name="data_extraction",
                prompt_template_config=template_config,
            )
            
            # Create plugin with the function
            plugin = KernelPlugin(name="data_extraction", functions=[function])
            
            # Add to kernel
            self.kernel.add_plugin(plugin)
            
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.UNKNOWN,
                e,
                "load_data_extraction_prompt"
            )
    
    @kernel_function(
        description="Extract structured SRM change request data from email",
        name="extract_change_request"
    )
    async def extract_change_request(self, 
                                   subject: str, 
                                   sender: str, 
                                   body: str) -> str:
        """
        Extract change request data using LLM prompt.
        
        Args:
            subject: Email subject line
            sender: Email sender address
            body: Email body content
            
        Returns:
            JSON string with extracted data or error message
        """
        try:
            @self.error_handler.with_retry(ErrorType.LLM_CALL)
            async def _extract():
                # Get the data extraction function
                extraction_function = self.kernel.get_function(
                    plugin_name="data_extraction",
                    function_name="data_extraction"
                )
                
                # Execute the function
                result = await self.kernel.invoke(
                    extraction_function,
                    subject=subject,
                    sender=sender,
                    body=body
                )
                
                return str(result)
            
            result = await _extract()
            
            # Log the raw result for debugging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Raw extraction result: {result[:500]}...")
            
            # Validate and structure the response
            try:
                # Clean the result - sometimes LLMs add markdown code blocks
                result_cleaned = result.strip()
                if result_cleaned.startswith("```json"):
                    result_cleaned = result_cleaned[7:]  # Remove ```json
                if result_cleaned.startswith("```"):
                    result_cleaned = result_cleaned[3:]  # Remove ```
                if result_cleaned.endswith("```"):
                    result_cleaned = result_cleaned[:-3]  # Remove trailing ```
                result_cleaned = result_cleaned.strip()
                
                parsed_result = json.loads(result_cleaned)
                
                # Create ChangeRequest object to validate structure
                change_request = ChangeRequest.from_dict(parsed_result)
                
                # Return the validated data
                return json.dumps(change_request.to_dict(), indent=2)
                
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                self.error_handler.handle_error(
                    ErrorType.LLM_PARSE,
                    e,
                    "extract_change_request - JSON validation"
                )
                
                # Return minimal structure for parsing errors
                fallback_result = ChangeRequest(
                    completeness_score=0,
                    change_description=f"Failed to parse extraction result: {e}"
                )
                return json.dumps(fallback_result.to_dict())
            
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.LLM_CALL,
                e,
                "extract_change_request"
            )
            
            # Return minimal structure for errors
            error_result = ChangeRequest(
                completeness_score=0,
                change_description=f"Extraction failed: {e}"
            )
            return json.dumps(error_result.to_dict())
    
    @kernel_function(
        description="Validate extracted data completeness",
        name="validate_completeness"
    )
    def validate_completeness(self, extracted_data: str) -> str:
        """
        Validate if extracted data is complete enough to process.
        
        Args:
            extracted_data: JSON string from extract_change_request
            
        Returns:
            JSON string with validation result
        """
        try:
            data = json.loads(extracted_data)
            change_request = ChangeRequest.from_dict(data)
            
            is_complete = change_request.is_complete()
            missing_fields = change_request.get_missing_fields()
            
            validation_result = {
                "is_complete": is_complete,
                "completeness_score": change_request.completeness_score,
                "missing_fields": missing_fields,
                "needs_clarification": not is_complete
            }
            
            return json.dumps(validation_result)
            
        except (json.JSONDecodeError, ValueError, TypeError) as e:
            # Return incomplete for invalid input
            error_result = {
                "is_complete": False,
                "completeness_score": 0,
                "missing_fields": ["All fields - invalid data format"],
                "needs_clarification": True
            }
            return json.dumps(error_result)
    
    @kernel_function(
        description="Generate clarification questions for incomplete requests",
        name="generate_clarification"
    )
    async def generate_clarification(self, 
                                   extracted_data: str, 
                                   missing_fields: str) -> str:
        """
        Generate clarification email for incomplete change requests.
        
        Args:
            extracted_data: JSON string of extracted data
            missing_fields: Comma-separated list of missing fields
            
        Returns:
            Generated clarification email text
        """
        try:
            # Parse the data
            data = json.loads(extracted_data)
            missing_list = [field.strip() for field in missing_fields.split(",")]
            
            # Create clarification prompt
            clarification_prompt = f"""
            Generate a friendly email asking for clarification on an SRM change request.
            
            What we have: {json.dumps(data, indent=2)}
            What we're missing: {', '.join(missing_list)}
            
            Ask specifically for:
            - Which SRM they're referring to (name/title)
            - What exactly they want changed (owner notes users see, or hidden notes for recommendation logic)
            - Why they need this change
            
            Keep it brief and helpful. Start with thanking them for their request.
            """
            
            @self.error_handler.with_retry(ErrorType.LLM_CALL)
            async def _generate():
                # Use a simple prompt-based approach instead of chat service
                from semantic_kernel.contents import ChatHistory
                from semantic_kernel.connectors.ai.prompt_execution_settings import PromptExecutionSettings
                
                # Get the chat completion service
                chat_service = self.kernel.get_service("chat")
                
                # Create chat history with the prompt
                chat_history = ChatHistory()
                chat_history.add_user_message(clarification_prompt)
                
                # Create execution settings
                settings = PromptExecutionSettings(
                    service_id="chat",
                    max_tokens=300,
                    temperature=0.3
                )
                
                # Get response
                response = await chat_service.get_chat_message_content(
                    chat_history=chat_history,
                    settings=settings
                )
                
                return str(response)
            
            clarification_text = await _generate()
            return clarification_text
            
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.LLM_CALL,
                e,
                "generate_clarification"
            )
            
            # Return generic clarification message
            return (
                "Thank you for your SRM change request. We need some additional information "
                "to process your request:\n\n"
                "1. Which specific SRM are you referring to? (Please provide the exact name/title)\n"
                "2. What exactly would you like us to change?\n"
                "3. Why is this change needed?\n\n"
                "Please reply with these details and we'll process your request promptly."
            )

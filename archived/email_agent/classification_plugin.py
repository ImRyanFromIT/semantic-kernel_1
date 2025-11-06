"""
Classification plugin for LLM-based email classification.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any
from semantic_kernel import Kernel
from semantic_kernel.functions import kernel_function

from src.utils.error_handler import ErrorHandler, ErrorType


class ClassificationPlugin:
    """
    Semantic Kernel plugin for LLM-based email classification.

    Uses prompt-based function to classify emails into help/dont_help/escalate.
    """

    def __init__(self, kernel: Kernel, error_handler: ErrorHandler):
        """
        Initialize classification plugin.

        Args:
            kernel: Semantic Kernel instance with LLM service
            error_handler: ErrorHandler for retry logic
        """
        self.kernel = kernel
        self.error_handler = error_handler
        self.logger = logging.getLogger(__name__)

        # Load the email classification prompt function
        self._load_prompt_function()
    
    def _load_prompt_function(self):
        """Load the email classification prompt from directory."""
        try:
            import json
            from semantic_kernel.functions import KernelFunction, KernelPlugin
            from semantic_kernel.prompt_template import PromptTemplateConfig
            
            # Get the path to the email_classification prompt directory
            plugin_dir = Path(__file__).parent / "email_classification"
            config_file = plugin_dir / "config.json"
            prompt_file = plugin_dir / "skprompt.txt"
            
            # Load config and prompt
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_template = f.read()
            
            # Create prompt template config
            template_config = PromptTemplateConfig(
                name="email_classification",
                description=config_data.get('description', ''),
                template=prompt_template,
                execution_settings=config_data.get('execution_settings', {}),
            )
            
            # Create function from prompt
            function = KernelFunction.from_prompt(
                function_name="email_classification",
                plugin_name="email_classification",
                prompt_template_config=template_config,
            )
            
            # Create plugin with the function
            plugin = KernelPlugin(name="email_classification", functions=[function])
            
            # Add to kernel
            self.kernel.add_plugin(plugin)
            
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.UNKNOWN,
                e,
                "load_email_classification_prompt"
            )
    
    @kernel_function(
        description="Classify an email into three categories: 'help' (processable SRM change requests), 'dont_help' (off-topic/spam), or 'escalate' (ambiguous/uncertain). Returns JSON with classification, confidence, and reason.",
        name="classify_email"
    )
    async def classify_email(self, 
                           subject: str, 
                           sender: str, 
                           body: str) -> str:
        """
        Classify email using LLM prompt.
        
        Args:
            subject: Email subject line
            sender: Email sender address
            body: Email body content
            
        Returns:
            JSON string with classification result or error message
        """
        try:
            @self.error_handler.with_retry(ErrorType.LLM_CALL)
            async def _classify():
                # Get the email classification function
                classification_function = self.kernel.get_function(
                    plugin_name="email_classification",
                    function_name="email_classification"
                )
                
                # Execute the function
                result = await self.kernel.invoke(
                    classification_function,
                    subject=subject,
                    sender=sender,
                    body=body
                )
                
                return str(result)
            
            result = await _classify()
            
            # Validate JSON response
            try:
                parsed_result = json.loads(result)
                
                # Validate required fields
                required_fields = ['classification', 'confidence', 'reason']
                for field in required_fields:
                    if field not in parsed_result:
                        raise ValueError(f"Missing required field: {field}")
                
                # Validate classification value
                valid_classifications = ['help', 'dont_help', 'escalate']
                if parsed_result['classification'] not in valid_classifications:
                    raise ValueError(f"Invalid classification: {parsed_result['classification']}")
                
                # Validate confidence range
                confidence = parsed_result['confidence']
                if not isinstance(confidence, int) or confidence < 0 or confidence > 100:
                    raise ValueError(f"Invalid confidence score: {confidence}")
                
                return result
                
            except (json.JSONDecodeError, ValueError) as e:
                self.error_handler.handle_error(
                    ErrorType.LLM_PARSE,
                    e,
                    "classify_email - JSON validation"
                )
                
                # Return escalate classification for parsing errors
                fallback_result = {
                    "classification": "escalate",
                    "confidence": 0,
                    "reason": f"Failed to parse LLM response: {e}"
                }
                return json.dumps(fallback_result)
            
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.LLM_CALL,
                e,
                "classify_email"
            )
            
            # Return escalate classification for errors
            error_result = {
                "classification": "escalate",
                "confidence": 0,
                "reason": f"Classification failed: {e}"
            }
            return json.dumps(error_result)
    
    @kernel_function(
        description="Validate classification confidence and override if too low",
        name="validate_classification"
    )
    def validate_classification(self, 
                              classification_result: str, 
                              confidence_threshold: int = 70) -> str:
        """
        Validate classification confidence and override to escalate if too low.
        
        Args:
            classification_result: JSON string from classify_email
            confidence_threshold: Minimum confidence threshold
            
        Returns:
            Validated classification result (may be overridden to escalate)
        """
        try:
            result = json.loads(classification_result)
            
            # Check confidence threshold
            if result['confidence'] < confidence_threshold:
                result['classification'] = 'escalate'
                result['reason'] = f"Low confidence ({result['confidence']}%) - escalating for human review"
            
            return json.dumps(result)
            
        except (json.JSONDecodeError, KeyError) as e:
            # Return escalate for invalid input
            error_result = {
                "classification": "escalate",
                "confidence": 0,
                "reason": f"Invalid classification result: {e}"
            }
            return json.dumps(error_result)

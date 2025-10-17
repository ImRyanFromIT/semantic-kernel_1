'''
Clarity step - Extract intent and decide if clarification is needed using LLM plugins.
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


@kernel_process_step_metadata("ClarityStep.V1")
class ClarityStep(KernelProcessStep):
    '''
    Process step to extract key terms and determine if clarification is needed.
    
    Uses LLM-powered plugins to:
    - Detect user intent
    - Extract relevant entities
    - Assess query clarity
    - Generate contextual clarifying questions
    
    Note: Kernel is passed through event data due to SK ProcessBuilder constraints.
    '''
    
    class OutputEvents(Enum):
        '''Output events from the clarity step.'''
        ClarityObtained = "ClarityObtained"
        NeedsClarification = "NeedsClarification"
    
    @kernel_function(name="analyze_query")
    async def analyze_query(
        self,
        context: KernelProcessStepContext,
        input_data: dict,
    ) -> None:
        '''
        Analyze the user query using LLM plugins to extract intent, entities, and determine clarity.
        
        Args:
            context: Process step context
            input_data: Dictionary containing user_query, vector_store, session_id
        '''
        # Extract data from input
        user_query = input_data.get('user_query', '')
        vector_store = input_data.get('vector_store')
        session_id = input_data.get('session_id', '')
        kernel = input_data.get('kernel')
        result_container = input_data.get('result_container', {})
        
        logger.info("Analyzing query clarity", extra={"session_id": session_id, "query": user_query})
        
        # Use LLM plugins to analyze the query - kernel from input_data
        try:
            # Step 1: Detect intent
            detected_intent = await self._detect_intent(user_query, kernel)
            logger.debug("Intent detected", extra={"session_id": session_id, "intent": detected_intent})
            
            # Step 2: Extract entities
            extracted_entities = await self._extract_entities(user_query, kernel)
            logger.debug("Entities extracted", extra={"session_id": session_id, "entities": extracted_entities})
            
            # Step 3: Assess clarity
            needs_clarification = await self._assess_clarity(user_query, extracted_entities, kernel)
            logger.debug("Clarity assessed", extra={"session_id": session_id, "needs_clarification": needs_clarification})
            
            if needs_clarification:
                # Generate a contextual clarifying question using LLM
                clarification = await self._generate_clarification_question(
                    user_query, detected_intent, extracted_entities, kernel
                )
                logger.info("Clarification needed", extra={"session_id": session_id, "clarification": clarification})
                
                # Store result in container for entry point to retrieve
                result_container['clarification'] = clarification
                result_container['intent'] = detected_intent
                result_container['key_terms'] = extracted_entities.split(', ')
                
                # Emit public event for clarification with dependencies
                await context.emit_event(
                    process_event=self.OutputEvents.NeedsClarification.value,
                    data={
                        "clarification": clarification,
                        "key_terms": extracted_entities.split(', '),
                        "intent": detected_intent,
                        "user_query": user_query,
                        "vector_store": vector_store,
                        "session_id": session_id,
                        "kernel": kernel,
                    },
                    visibility=KernelProcessEventVisibility.Public
                )
            else:
                # We have enough clarity to proceed
                logger.info("Clarity obtained, proceeding", extra={"session_id": session_id})
                await context.emit_event(
                    process_event=self.OutputEvents.ClarityObtained.value,
                    data={
                        "key_terms": extracted_entities.split(', '),
                        "intent": detected_intent,
                        "user_query": user_query,
                        "vector_store": vector_store,
                        "session_id": session_id,
                        "kernel": kernel,
                        "result_container": result_container,
                    },
                )
        except Exception as e:
            logger.error("Plugin error in ClarityStep, falling back to default", extra={"session_id": session_id, "error": str(e)})
            
            # Proceed with query as-is with dependencies
            await context.emit_event(
                process_event=self.OutputEvents.ClarityObtained.value,
                data={
                    "key_terms": [],
                    "intent": "GeneralInquiry",
                    "user_query": user_query,
                    "vector_store": vector_store,
                    "session_id": session_id,
                    "kernel": kernel,
                    "result_container": result_container,
                },
            )
    
    async def _detect_intent(self, user_query: str, kernel: Kernel) -> str:
        '''
        Use LLM plugin to detect user intent.
        
        Args:
            user_query: The user's query
            kernel: Semantic Kernel instance
            
        Returns:
            Detected intent string
        '''
        from src.utils.plugin_loader import invoke_plugin
        
        try:
            result = await invoke_plugin(
                kernel,
                plugin_name='intent_detection',
                function_name='detect_intent',
                user_query=user_query
            )
            return result
        except Exception as e:
            logger.warning("Intent detection failed, using default", extra={"error": str(e)})
            return "GeneralInquiry"
    
    async def _extract_entities(self, user_query: str, kernel: Kernel) -> str:
        '''
        Use LLM plugin to extract entities from query.
        
        Args:
            user_query: The user's query
            kernel: Semantic Kernel instance
            
        Returns:
            Comma-separated list of entities
        '''
        from src.utils.plugin_loader import invoke_plugin
        
        try:
            result = await invoke_plugin(
                kernel,
                plugin_name='entity_extraction',
                function_name='extract_entities',
                user_query=user_query,
                entity_categories=""  # Optional parameter - empty means use generic extraction
            )
            return result
        except Exception as e:
            logger.warning("Entity extraction failed, using default", extra={"error": str(e)})
            return "none"
    
    async def _assess_clarity(self, user_query: str, extracted_entities: str, kernel: Kernel) -> bool:
        '''
        Use LLM plugin to assess if query needs clarification.
        
        Args:
            user_query: The user's query
            extracted_entities: Entities extracted from query
            kernel: Semantic Kernel instance
            
        Returns:
            True if clarification is needed
        '''
        from src.utils.plugin_loader import invoke_plugin
        
        try:
            result = await invoke_plugin(
                kernel,
                plugin_name='clarity_classifier',
                function_name='assess_clarity',
                user_query=user_query,
                extracted_entities=extracted_entities
            )
            return result.lower() == 'unclear'
        except Exception as e:
            logger.warning("Clarity assessment failed, defaulting to clear", extra={"error": str(e)})
            # Default to not needing clarification on error
            return False
    
    async def _generate_clarification_question(
        self, 
        user_query: str, 
        detected_intent: str, 
        extracted_entities: str,
        kernel: Kernel
    ) -> str:
        '''
        Use LLM plugin to generate a contextual clarifying question.
        
        Args:
            user_query: The user's query
            detected_intent: The detected intent
            extracted_entities: Extracted entities
            kernel: Semantic Kernel instance
            
        Returns:
            A clarifying question to ask the user
        '''
        from src.utils.plugin_loader import invoke_plugin
        
        try:
            result = await invoke_plugin(
                kernel,
                plugin_name='clarification_generator',
                function_name='generate_clarification',
                user_query=user_query,
                detected_intent=detected_intent,
                extracted_entities=extracted_entities
            )
            return result
        except Exception as e:
            logger.warning("Clarification generation failed, using default", extra={"error": str(e)})
            return "Could you provide more details about your request?"


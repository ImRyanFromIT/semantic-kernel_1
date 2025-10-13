'''
Clarity step - Extract intent and decide if clarification is needed using LLM plugins.
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


class ClarityStep(KernelProcessStep):
    '''
    Process step to extract key terms and determine if clarification is needed.
    
    Uses LLM-powered plugins to:
    - Detect user intent
    - Extract relevant entities
    - Assess query clarity
    - Generate contextual clarifying questions
    '''
    
    _kernel: Kernel = None
    
    class OutputEvents(Enum):
        '''Output events from the clarity step.'''
        ClarityObtained = "ClarityObtained"
        NeedsClarification = "NeedsClarification"
    
    @classmethod
    def set_kernel(cls, kernel: Kernel):
        '''Set the kernel for all instances of this step.'''
        cls._kernel = kernel
    
    @property
    def kernel(self) -> Kernel:
        '''Get the kernel instance.'''
        return self.__class__._kernel
    
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
        
        debug_print(f"DEBUG ClarityStep: Called with user_query='{user_query}', session_id='{session_id}'")
        
        # Use LLM plugins to analyze the query
        try:
            # Step 1: Detect intent
            detected_intent = await self._detect_intent(user_query)
            debug_print(f"DEBUG ClarityStep: Detected intent: {detected_intent}")
            
            # Step 2: Extract entities
            extracted_entities = await self._extract_entities(user_query)
            debug_print(f"DEBUG ClarityStep: Extracted entities: {extracted_entities}")
            
            # Step 3: Assess clarity
            needs_clarification = await self._assess_clarity(user_query, extracted_entities)
            debug_print(f"DEBUG ClarityStep: Needs clarification: {needs_clarification}")
            
            if needs_clarification:
                # Generate a contextual clarifying question using LLM
                clarification = await self._generate_clarification_question(
                    user_query, detected_intent, extracted_entities
                )
                debug_print(f"DEBUG ClarityStep: Generated clarification: {clarification}")
                
                # Store result in global store
                from src.utils.result_store import store_result
                store_result(session_id, {'clarification': clarification})
                
                # Emit public event for clarification
                await context.emit_event(
                    process_event=self.OutputEvents.NeedsClarification.value,
                    data={
                        "clarification": clarification,
                        "key_terms": extracted_entities.split(', '),
                        "intent": detected_intent,
                        "user_query": user_query,
                        "vector_store": vector_store,
                        "session_id": session_id,
                    },
                    visibility=KernelProcessEventVisibility.Public
                )
            else:
                # We have enough clarity to proceed
                await context.emit_event(
                    process_event=self.OutputEvents.ClarityObtained.value,
                    data={
                        "key_terms": extracted_entities.split(', '),
                        "intent": detected_intent,
                        "user_query": user_query,
                        "vector_store": vector_store,
                        "session_id": session_id,
                    },
                )
        except Exception as e:
            print(f"[!] Plugin error in ClarityStep: {e}")
            print("[*] Falling back to default behavior")
            
            # Proceed with query as-is
            await context.emit_event(
                process_event=self.OutputEvents.ClarityObtained.value,
                data={
                    "key_terms": [],
                    "intent": "GeneralInquiry",
                    "user_query": user_query,
                    "vector_store": vector_store,
                    "session_id": session_id,
                },
            )
    
    async def _detect_intent(self, user_query: str) -> str:
        '''
        Use LLM plugin to detect user intent.
        
        Args:
            user_query: The user's query
            
        Returns:
            Detected intent string
        '''
        from src.utils.plugin_loader import invoke_plugin
        
        try:
            result = await invoke_plugin(
                self.kernel,
                plugin_name='intent_detection',
                function_name='detect_intent',
                user_query=user_query
            )
            return result
        except Exception as e:
            print(f"[!] Intent detection failed: {e}")
            return "GeneralInquiry"
    
    async def _extract_entities(self, user_query: str) -> str:
        '''
        Use LLM plugin to extract entities from query.
        
        Args:
            user_query: The user's query
            
        Returns:
            Comma-separated list of entities
        '''
        from src.utils.plugin_loader import invoke_plugin
        
        try:
            result = await invoke_plugin(
                self.kernel,
                plugin_name='entity_extraction',
                function_name='extract_entities',
                user_query=user_query,
                entity_categories=""  # Optional parameter - empty means use generic extraction
            )
            return result
        except Exception as e:
            print(f"[!] Entity extraction failed: {e}")
            return "none"
    
    async def _assess_clarity(self, user_query: str, extracted_entities: str) -> bool:
        '''
        Use LLM plugin to assess if query needs clarification.
        
        Args:
            user_query: The user's query
            extracted_entities: Entities extracted from query
            
        Returns:
            True if clarification is needed
        '''
        from src.utils.plugin_loader import invoke_plugin
        
        try:
            result = await invoke_plugin(
                self.kernel,
                plugin_name='clarity_classifier',
                function_name='assess_clarity',
                user_query=user_query,
                extracted_entities=extracted_entities
            )
            return result.lower() == 'unclear'
        except Exception as e:
            print(f"[!] Clarity assessment failed: {e}")
            # Default to not needing clarification on error
            return False
    
    async def _generate_clarification_question(
        self, 
        user_query: str, 
        detected_intent: str, 
        extracted_entities: str
    ) -> str:
        '''
        Use LLM plugin to generate a contextual clarifying question.
        
        Args:
            user_query: The user's query
            detected_intent: The detected intent
            extracted_entities: Extracted entities
            
        Returns:
            A clarifying question to ask the user
        '''
        from src.utils.plugin_loader import invoke_plugin
        
        try:
            result = await invoke_plugin(
                self.kernel,
                plugin_name='clarification_generator',
                function_name='generate_clarification',
                user_query=user_query,
                detected_intent=detected_intent,
                extracted_entities=extracted_entities
            )
            return result
        except Exception as e:
            print(f"[!] Clarification generation failed: {e}")
            return "Could you provide more details about your request?"


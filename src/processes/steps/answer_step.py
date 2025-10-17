'''
Answer step - Format the final response for the user using LLM plugins.
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


class AnswerStep(KernelProcessStep):
    '''
    Process step to format the final answer for the user.
    
    Formats SRM recommendations with relevant details and confidence scores.
    '''
    
    class OutputEvents(Enum):
        '''Output events from the answer step.'''
        AnswerPublished = "AnswerPublished"
        FallbackAnswer = "FallbackAnswer"
    
    @kernel_function(name="format_answer")
    async def format_answer(
        self,
        context: KernelProcessStepContext,
        input_data: dict,
    ) -> None:
        '''
        Format the final answer with SRM recommendation.
        
        Args:
            context: Process step context
            input_data: Dictionary containing selected_srm, confidence, alternatives, session_id, user_query
        '''
        # Extract data from input
        selected_srm = input_data.get('selected_srm')
        confidence = input_data.get('confidence', 0.0)
        alternatives = input_data.get('alternatives', [])
        session_id = input_data.get('session_id', '')
        user_query = input_data.get('user_query', '')
        
        debug_print(f"DEBUG AnswerStep: Called with session_id='{session_id}', selected_srm={selected_srm is not None}")
        
        if alternatives is None:
            alternatives = []
        
        if not selected_srm:
            answer = self._format_fallback()
            
            # Store result in global store
            from src.utils.result_store import store_result
            store_result(session_id, {
                'answer': answer,
                'selected_id': None,
                'confidence': confidence,
            })
            
            # Emit public event so it can be captured at process level
            await context.emit_event(
                process_event=self.OutputEvents.FallbackAnswer.value,
                data={
                    "final_answer": answer,
                    "selected_id": None,
                    "confidence": confidence,
                },
                visibility=KernelProcessEventVisibility.Public
            )
            return
        
        # Format the main recommendation
        answer = await self._format_recommendation(
            selected_srm, confidence, alternatives, user_query
        )
        
        # Store result in global store
        from src.utils.result_store import store_result
        store_result(session_id, {
            'answer': answer,
            'selected_id': selected_srm.get('srm_id'),
            'confidence': confidence,
        })
        
        # Emit public event so it can be captured at process level
        await context.emit_event(
            process_event=self.OutputEvents.AnswerPublished.value,
            data={
                "final_answer": answer,
                "selected_id": selected_srm.get('srm_id'),
                "confidence": confidence,
            },
            visibility=KernelProcessEventVisibility.Public
        )
    
    async def _format_recommendation(
        self, 
        selected: dict, 
        confidence: float,
        alternatives: list[dict],
        user_query: str
    ) -> str:
        '''
        Format the recommended SRM as a markdown response.
        
        Args:
            selected: The selected SRM
            confidence: Confidence score
            alternatives: Alternative SRM options
            user_query: Original user query for context
            
        Returns:
            Formatted markdown answer
        '''
        answer = f"""## Recommended SRM: {selected['name']}

**Category:** {selected['category']}

**Use Case:** {selected['use_case']}

**Owning Team:** {selected['owning_team']}
"""
        
        # Add URL if available
        if selected.get('url'):
            answer += f"\n**URL:** {selected['url']}\n"
        
        # Always show 2 alternative options
        if alternatives:
            answer += "\n### Alternative Options:\n\n"
            for i, alt in enumerate(alternatives[:2], 1):
                answer += f"{i}. **{alt['name']}** ({alt['category']}) - {alt['use_case']}\n"
                if alt.get('url'):
                    answer += f"   **URL:** {alt['url']}\n"
        
        answer += "\n---\n*If this doesn't match your need, please provide more details and I'll search again.*"
        
        return answer
    
    def _format_fallback(self) -> str:
        '''
        Format a fallback response when no SRM is found.
        
        Returns:
            Formatted fallback message
        '''
        return """## No Matching SRM Found

I couldn't find an SRM that closely matches your request. This could be because:

1. Your request might need more specific details
2. The task might not have a dedicated SRM
3. The request might need to be handled by direct team contact

"""


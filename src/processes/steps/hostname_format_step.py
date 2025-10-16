'''
Hostname format step - Format hostname lookup results for display.
'''

from enum import Enum

from semantic_kernel.functions import kernel_function
from semantic_kernel.processes.kernel_process import KernelProcessStep, KernelProcessStepContext

from src.utils.debug_config import debug_print
from src.utils.result_store import store_result


class HostnameFormatStep(KernelProcessStep):
    '''
    Process step to format hostname lookup results.
    
    Formats single matches, multiple matches, and no match scenarios.
    '''
    
    class OutputEvents(Enum):
        '''Output events from the format step.'''
        ResultFormatted = "ResultFormatted"
    
    @kernel_function(name="format_result")
    async def format_result(
        self,
        context: KernelProcessStepContext,
        input_data: dict,
    ) -> None:
        '''
        Format the hostname lookup result for display.
        
        Routes to appropriate formatter based on input data.
        
        Args:
            context: Process step context
            input_data: Dictionary containing lookup results and session_id
        '''
        session_id = input_data.get('session_id', '')
        
        # Determine which type of result to format based on what's in input_data
        if 'hostname_record' in input_data:
            # Single match found
            await self._format_single_match(context, input_data, session_id)
        elif 'hostname_records' in input_data:
            # Multiple matches found
            await self._format_multiple_matches(context, input_data, session_id)
        else:
            # No match found
            await self._format_no_match(context, input_data, session_id)
    
    async def _format_single_match(
        self,
        context: KernelProcessStepContext,
        input_data: dict,
        session_id: str,
    ) -> None:
        '''
        Format a single hostname match for display.
        
        Args:
            context: Process step context
            input_data: Dictionary containing hostname_record
            session_id: Session identifier
        '''
        hostname_record = input_data.get('hostname_record')
        
        debug_print(f"DEBUG HostnameFormatStep: Formatting single match for session '{session_id}'")
        
        # Format the response
        response = self._format_hostname_details(hostname_record)
        
        # Store result
        store_result(session_id, {
            'answer': response,
            'hostname': hostname_record.hostname,
            'application_name': hostname_record.application_name,
        })
        
        # Emit completion event
        await context.emit_event(
            process_event=self.OutputEvents.ResultFormatted.value,
            data={
                "response": response,
                "session_id": session_id,
            }
        )
    
    async def _format_multiple_matches(
        self,
        context: KernelProcessStepContext,
        input_data: dict,
        session_id: str,
    ) -> None:
        '''
        Format multiple hostname matches for display.
        
        Args:
            context: Process step context
            input_data: Dictionary containing hostname_records and user_query
            session_id: Session identifier
        '''
        hostname_records = input_data.get('hostname_records', [])
        user_query = input_data.get('user_query', '')
        
        debug_print(f"DEBUG HostnameFormatStep: Formatting {len(hostname_records)} matches for session '{session_id}'")
        
        # Format the response
        response = f"**Multiple matches found for '{user_query}' ({len(hostname_records)} results)**\n\n"
        response += "Please be more specific. Here are the matching hostnames:\n\n"
        
        for record in hostname_records:
            response += f"- **{record.hostname}** ({record.application_name})\n"
        
        response += "\n*Tip: Use the exact hostname for detailed information.*"
        
        # Store result
        store_result(session_id, {
            'answer': response,
            'match_count': len(hostname_records),
        })
        
        # Emit completion event
        await context.emit_event(
            process_event=self.OutputEvents.ResultFormatted.value,
            data={
                "response": response,
                "session_id": session_id,
            }
        )
    
    async def _format_no_match(
        self,
        context: KernelProcessStepContext,
        input_data: dict,
        session_id: str,
    ) -> None:
        '''
        Format a no match response.
        
        Args:
            context: Process step context
            input_data: Dictionary containing user_query
            session_id: Session identifier
        '''
        user_query = input_data.get('user_query', '')
        
        debug_print(f"DEBUG HostnameFormatStep: Formatting no match for session '{session_id}'")
        
        # Format the response
        response = f"**No hostname found matching '{user_query}'**\n\n"
        response += "Please check the hostname and try again. Make sure:\n"
        response += "- The hostname is spelled correctly (hostnames use hyphens, e.g., 'srv-vmcap-001-prod')\n"
        response += "- The machine exists in the system\n"
        response += "- The application has team information configured\n\n"
        response += "*Note: The lookup command requires exact hostname matches.*"
        
        # Store result
        store_result(session_id, {
            'answer': response,
            'match_count': 0,
        })
        
        # Emit completion event
        await context.emit_event(
            process_event=self.OutputEvents.ResultFormatted.value,
            data={
                "response": response,
                "session_id": session_id,
            }
        )
    
    def _format_hostname_details(self, record) -> str:
        '''
        Format detailed hostname information.
        
        Args:
            record: HostnameRecord object
            
        Returns:
            Formatted string with hostname details
        '''
        response = f"## Hostname Details\n\n"
        response += f"**Hostname:** {record.hostname}\n\n"
        response += f"**Application:** {record.application_name}\n\n"
        response += f"**Maintenance Window:** {record.maintenance_window}\n\n"
        response += f"**Team:** {record.team}\n\n"
        response += f"**Contact:** {record.email_distros}\n\n"
        response += "---\n"
        response += "*For questions about this system, contact the team listed above.*"
        
        return response


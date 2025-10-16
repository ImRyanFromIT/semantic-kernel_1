'''
Hostname lookup step - Search for hostname in Azure AI Search indexes.
'''

import os
from enum import Enum

from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

from semantic_kernel.functions import kernel_function
from semantic_kernel.processes.kernel_process import KernelProcessStep, KernelProcessStepContext

from src.models.hostname_record import HostnameRecord
from src.utils.debug_config import debug_print


class HostnameLookupStep(KernelProcessStep):
    '''
    Process step to lookup hostname information from Azure AI Search.
    
    This step searches app_machines and app_team_index indexes,
    joins them, and returns complete hostname records.
    '''
    
    class OutputEvents(Enum):
        '''Output events from the hostname lookup step.'''
        ExactMatchFound = "ExactMatchFound"
        MultipleMatchesFound = "MultipleMatchesFound"
        NoMatchFound = "NoMatchFound"
    
    def _get_search_clients(self):
        '''
        Create and return Azure AI Search clients for both indexes.
        
        Returns:
            Tuple of (machines_client, team_client)
        '''
        # Azure AI Search configuration
        endpoint = os.getenv('AZURE_AI_SEARCH_ENDPOINT')
        api_key = os.getenv('AZURE_AI_SEARCH_API_KEY')
        
        if not endpoint or not api_key:
            raise ValueError(
                "Azure AI Search credentials must be set in environment variables: "
                "AZURE_AI_SEARCH_ENDPOINT and AZURE_AI_SEARCH_API_KEY"
            )
        
        # Get configurable index names
        machines_index = os.getenv('AZURE_AI_SEARCH_APP_MACHINES_INDEX', 'app_machines')
        team_index = os.getenv('AZURE_AI_SEARCH_APP_TEAM_INDEX', 'app_team_index')
        
        # Create search clients for both indexes
        machines_client = SearchClient(
            endpoint=endpoint,
            index_name=machines_index,
            credential=AzureKeyCredential(api_key)
        )
        
        team_client = SearchClient(
            endpoint=endpoint,
            index_name=team_index,
            credential=AzureKeyCredential(api_key)
        )
        
        return machines_client, team_client
    
    @kernel_function(name="lookup_hostname")
    async def lookup_hostname(
        self,
        context: KernelProcessStepContext,
        input_data: dict,
    ) -> None:
        '''
        Search for hostname information.
        
        Args:
            context: Process step context
            input_data: Dictionary containing user_query and session_id
        '''
        user_query = input_data.get('user_query', '').strip()
        session_id = input_data.get('session_id', '')
        
        debug_print(f"DEBUG HostnameLookupStep: Looking up hostname '{user_query}', session_id='{session_id}'")
        
        # Get search clients
        try:
            machines_client, team_client = self._get_search_clients()
        except Exception as e:
            debug_print(f"DEBUG HostnameLookupStep: Failed to initialize search clients: {e}")
            await context.emit_event(
                process_event=self.OutputEvents.NoMatchFound.value,
                data={
                    "user_query": user_query,
                    "session_id": session_id,
                    "error": str(e),
                }
            )
            return
        
        try:
            # Step 1: Try exact match only (lookup command should only return exact matches)
            exact_matches = await self._search_machines(machines_client, user_query, exact=True)
            
            debug_print(f"DEBUG HostnameLookupStep: Found {len(exact_matches)} exact matches for '{user_query}'")
            
            if len(exact_matches) == 1:
                # Single exact match - get team info and return
                hostname_record = await self._enrich_with_team_info(team_client, exact_matches[0])
                
                if hostname_record:
                    debug_print(f"DEBUG HostnameLookupStep: Found exact match for '{user_query}'")
                    await context.emit_event(
                        process_event=self.OutputEvents.ExactMatchFound.value,
                        data={
                            "hostname_record": hostname_record,
                            "session_id": session_id,
                        }
                    )
                    return
                else:
                    # Machine found but no team info - treat as not found
                    debug_print(f"DEBUG HostnameLookupStep: Found machine but no team info for '{user_query}'")
                    await context.emit_event(
                        process_event=self.OutputEvents.NoMatchFound.value,
                        data={
                            "user_query": user_query,
                            "session_id": session_id,
                        }
                    )
                    return
            elif len(exact_matches) > 1:
                # Multiple exact matches (shouldn't happen, but handle it)
                enriched_matches = []
                for machine in exact_matches:
                    hostname_record = await self._enrich_with_team_info(team_client, machine)
                    if hostname_record:
                        enriched_matches.append(hostname_record)
                
                if len(enriched_matches) > 0:
                    debug_print(f"DEBUG HostnameLookupStep: Found {len(enriched_matches)} exact matches with team info")
                    await context.emit_event(
                        process_event=self.OutputEvents.MultipleMatchesFound.value,
                        data={
                            "hostname_records": enriched_matches,
                            "user_query": user_query,
                            "session_id": session_id,
                        }
                    )
                    return
            
            # No exact matches found
            debug_print(f"DEBUG HostnameLookupStep: No exact match found for '{user_query}'")
            await context.emit_event(
                process_event=self.OutputEvents.NoMatchFound.value,
                data={
                    "user_query": user_query,
                    "session_id": session_id,
                }
            )
        
        except Exception as e:
            debug_print(f"DEBUG HostnameLookupStep: Error during lookup: {e}")
            await context.emit_event(
                process_event=self.OutputEvents.NoMatchFound.value,
                data={
                    "user_query": user_query,
                    "session_id": session_id,
                    "error": str(e),
                }
            )
    
    async def _search_machines(self, machines_client: SearchClient, query: str, exact: bool = True) -> list[dict]:
        '''
        Search the app_machines index.
        
        Args:
            machines_client: Azure Search client for app_machines index
            query: Hostname to search for
            exact: If True, use exact match; otherwise partial match
            
        Returns:
            List of machine records
        '''
        try:
            # Always use search (not filter) since Hostname may not be filterable
            results = machines_client.search(
                search_text=query,
                select=["Hostname", "Application_Name", "Maintenance_Window"],
                top=50
            )
            
            # Collect results
            machines = []
            for result in results:
                hostname = result.get('Hostname', '')
                machines.append({
                    'hostname': hostname,
                    'application_name': result.get('Application_Name', ''),
                    'maintenance_window': result.get('Maintenance_Window', ''),
                })
            
            # If exact match requested, filter results to exact matches only
            if exact:
                machines = [m for m in machines if m['hostname'].lower() == query.lower()]
            
            return machines
        
        except Exception as e:
            debug_print(f"DEBUG HostnameLookupStep: Error searching machines: {e}")
            return []
    
    async def _get_team_info(self, team_client: SearchClient, application_name: str) -> dict | None:
        '''
        Get team information for an application.
        
        Args:
            team_client: Azure Search client for app_team_index
            application_name: The application name to look up
            
        Returns:
            Team information dict or None if not found
        '''
        try:
            # Exact match on application name
            filter_str = f"Application_Name eq '{application_name}'"
            results = team_client.search(
                search_text="*",
                filter=filter_str,
                select=["Team", "Email_Distros"],
                top=1
            )
            
            # Get first result
            for result in results:
                return {
                    'team': result.get('Team', ''),
                    'email_distros': result.get('Email_Distros', ''),
                }
            
            return None
        
        except Exception as e:
            debug_print(f"DEBUG HostnameLookupStep: Error getting team info: {e}")
            return None
    
    async def _enrich_with_team_info(self, team_client: SearchClient, machine: dict) -> HostnameRecord | None:
        '''
        Enrich machine record with team information.
        
        Args:
            team_client: Azure Search client for app_team_index
            machine: Machine record from app_machines
            
        Returns:
            HostnameRecord if team info exists, None otherwise
        '''
        team_info = await self._get_team_info(team_client, machine['application_name'])
        
        if not team_info or not team_info.get('team'):
            # No team info available - return None per requirement 3b
            return None
        
        return HostnameRecord(
            hostname=machine['hostname'],
            application_name=machine['application_name'],
            maintenance_window=machine['maintenance_window'],
            team=team_info['team'],
            email_distros=team_info['email_distros'],
        )


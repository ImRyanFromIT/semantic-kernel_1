'''
Hostname record model for machine and team information.
'''

from dataclasses import dataclass


@dataclass
class HostnameRecord:
    '''
    Model to store hostname information combined from app_machines and app_team_index.
    
    Fields:
        hostname: The server hostname
        application_name: Name of the application
        maintenance_window: Scheduled maintenance window
        team: Owning team name
        email_distros: Email distribution lists
        id: Unique identifier (hostname-based)
    '''
    
    hostname: str
    application_name: str
    maintenance_window: str
    team: str
    email_distros: str
    id: str = ""
    
    def __post_init__(self):
        '''Generate ID from hostname if not set.'''
        if not self.id:
            self.id = self.hostname.lower().replace(' ', '-')


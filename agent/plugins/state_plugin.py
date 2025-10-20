"""
State plugin for JSONL state file operations.
"""

import json
from typing import List, Dict, Any, Optional
from semantic_kernel.functions import kernel_function

from ..utils.state_manager import StateManager
from ..utils.error_handler import ErrorHandler, ErrorType
from ..models.email_record import EmailRecord, EmailStatus


class StatePlugin:
    """
    Semantic Kernel plugin for JSONL state file operations.
    """
    
    def __init__(self, state_manager: StateManager, error_handler: ErrorHandler):
        """
        Initialize state plugin.
        
        Args:
            state_manager: StateManager instance
            error_handler: ErrorHandler for error handling
        """
        self.state_manager = state_manager
        self.error_handler = error_handler
    
    @kernel_function(
        description="Load all email records from state file",
        name="load_state"
    )
    def load_state(self) -> str:
        """
        Load all email records from agent_state.jsonl.
        
        Returns:
            JSON string of email records or error message
        """
        try:
            records = self.state_manager.read_state()
            
            # Convert to dictionaries for JSON serialization
            record_dicts = [record.to_dict() for record in records]
            
            return json.dumps(record_dicts, indent=2)
            
        except Exception as e:
            error_type = self.error_handler.get_error_type(e, "load_state")
            self.error_handler.handle_error(error_type, e, "load_state")
            
            if error_type == ErrorType.STATE_FILE_CORRUPTION:
                # Try to recover from corruption
                corrupted_file = self.state_manager.backup_corrupted_state()
                return f"State file corrupted. Backed up to {corrupted_file}. Starting fresh."
            
            return f"Failed to load state: {e}"
    
    @kernel_function(
        description="Find email records that need resuming (in-progress or awaiting)",
        name="find_resumable_records"
    )
    def find_resumable_records(self) -> str:
        """
        Find email records with in-progress or awaiting status.
        
        Returns:
            JSON string of resumable records
        """
        try:
            records = self.state_manager.find_in_progress_records()
            record_dicts = [record.to_dict() for record in records]
            
            return json.dumps(record_dicts, indent=2)
            
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.STATE_FILE_IO,
                e,
                "find_resumable_records"
            )
            return f"Failed to find resumable records: {e}"
    
    @kernel_function(
        description="Find stale email records that need escalation",
        name="find_stale_records"
    )
    def find_stale_records(self, hours: int = 48) -> str:
        """
        Find email records that haven't been updated in specified hours.
        
        Args:
            hours: Number of hours to consider stale
            
        Returns:
            JSON string of stale records
        """
        try:
            records = self.state_manager.find_stale_records(hours)
            record_dicts = [record.to_dict() for record in records]
            
            return json.dumps(record_dicts, indent=2)
            
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.STATE_FILE_IO,
                e,
                "find_stale_records"
            )
            return f"Failed to find stale records: {e}"
    
    @kernel_function(
        description="Add new email record to state",
        name="add_email_record"
    )
    def add_email_record(self, email_data: str) -> str:
        """
        Add new email record to state file.
        
        Args:
            email_data: JSON string of email record data
            
        Returns:
            Success or error message
        """
        try:
            # Parse email data
            data = json.loads(email_data)
            
            # Create EmailRecord from data
            record = EmailRecord(
                email_id=data['email_id'],
                sender=data['sender'],
                subject=data['subject'],
                body=data['body'],
                received_datetime=data['received_datetime'],
                conversation_id=data.get('conversation_id')
            )
            
            # Add to state
            self.state_manager.append_record(record)
            
            return f"Email record {record.email_id} added to state"
            
        except json.JSONDecodeError as e:
            return f"Invalid JSON in email_data: {e}"
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.STATE_FILE_IO,
                e,
                "add_email_record"
            )
            return f"Failed to add email record: {e}"
    
    @kernel_function(
        description="Update email record status and fields",
        name="update_email_record"
    )
    def update_email_record(self, email_id: str, updates: str) -> str:
        """
        Update specific fields of an email record.
        
        Args:
            email_id: ID of email to update
            updates: JSON string of field updates
            
        Returns:
            Success or error message
        """
        try:
            # Parse updates
            update_data = json.loads(updates)
            
            # Convert status string to enum if present
            if 'status' in update_data:
                update_data['status'] = EmailStatus(update_data['status'])
            
            # Update record
            success = self.state_manager.update_record(email_id, update_data)
            
            if success:
                return f"Email record {email_id} updated successfully"
            else:
                return f"Email record {email_id} not found"
                
        except json.JSONDecodeError as e:
            return f"Invalid JSON in updates: {e}"
        except ValueError as e:
            return f"Invalid status value: {e}"
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.STATE_FILE_IO,
                e,
                "update_email_record"
            )
            return f"Failed to update email record: {e}"
    
    @kernel_function(
        description="Get specific email record by ID",
        name="get_email_record"
    )
    def get_email_record(self, email_id: str) -> str:
        """
        Get email record by ID.
        
        Args:
            email_id: ID of email to retrieve
            
        Returns:
            JSON string of email record or error message
        """
        try:
            record = self.state_manager.find_record(email_id)
            
            if record:
                return json.dumps(record.to_dict(), indent=2)
            else:
                return f"Email record {email_id} not found"
                
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.STATE_FILE_IO,
                e,
                "get_email_record"
            )
            return f"Failed to get email record: {e}"
    
    @kernel_function(
        description="Check if email ID already exists in state",
        name="email_exists"
    )
    def email_exists(self, email_id: str) -> str:
        """
        Check if email ID already exists in state.
        
        Args:
            email_id: Email ID to check
            
        Returns:
            "true" if exists, "false" if not, or error message
        """
        try:
            record = self.state_manager.find_record(email_id)
            return "true" if record else "false"
            
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.STATE_FILE_IO,
                e,
                "email_exists"
            )
            return f"Failed to check email existence: {e}"

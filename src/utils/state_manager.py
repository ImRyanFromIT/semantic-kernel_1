"""
JSONL state file management for the SRM Archivist Agent.
"""

import json
import os
import shutil
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from pathlib import Path

from src.models.email_record import EmailRecord, EmailStatus


class StateManager:
    """
    Manages agent state using JSONL file format with atomic writes.
    
    Provides thread-safe operations for reading and writing email records
    to the agent_state.jsonl file.
    """
    
    def __init__(self, state_file: str = "agent_state.jsonl"):
        """
        Initialize state manager.
        
        Args:
            state_file: Path to the JSONL state file
        """
        self.state_file = Path(state_file)
        self.backup_file = Path(f"{state_file}.backup")
        
        # Create parent directories if they don't exist
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        
    def read_state(self) -> List[EmailRecord]:
        """
        Load and parse agent_state.jsonl file.
        
        Returns:
            List of EmailRecord objects from the state file
            
        Raises:
            FileNotFoundError: If state file doesn't exist
            json.JSONDecodeError: If JSONL parsing fails
        """
        if not self.state_file.exists():
            return []
        
        records = []
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        data = json.loads(line)
                        record = EmailRecord.from_dict(data)
                        records.append(record)
                    except (json.JSONDecodeError, KeyError, ValueError) as e:
                        print(f"[!] Warning: Skipping invalid line {line_num} in {self.state_file}: {e}")
                        continue
                        
        except Exception as e:
            print(f"[!] Error reading state file {self.state_file}: {e}")
            # Try to recover from backup
            if self.backup_file.exists():
                print(f"[*] Attempting to recover from backup: {self.backup_file}")
                return self._read_backup()
            raise
        
        return records
    
    def write_state(self, records: List[EmailRecord]) -> None:
        """
        Write complete state to JSONL file with atomic operation.
        
        Args:
            records: List of EmailRecord objects to write
            
        Raises:
            IOError: If file write operation fails
        """
        # Create backup of existing file
        if self.state_file.exists():
            shutil.copy2(self.state_file, self.backup_file)
        
        # Write to temporary file first
        temp_file = Path(f"{self.state_file}.tmp")
        
        try:
            with open(temp_file, 'w', encoding='utf-8') as f:
                for record in records:
                    json_line = json.dumps(record.to_dict(), ensure_ascii=False)
                    f.write(json_line + '\n')
            
            # Atomic move to final location
            shutil.move(str(temp_file), str(self.state_file))
            
        except Exception as e:
            # Clean up temp file if it exists
            if temp_file.exists():
                temp_file.unlink()
            raise IOError(f"Failed to write state file: {e}")
    
    def append_record(self, record: EmailRecord) -> None:
        """
        Append new record to state file.
        
        Args:
            record: EmailRecord to append
            
        Raises:
            IOError: If file write operation fails
        """
        try:
            with open(self.state_file, 'a', encoding='utf-8') as f:
                json_line = json.dumps(record.to_dict(), ensure_ascii=False)
                f.write(json_line + '\n')
        except Exception as e:
            raise IOError(f"Failed to append to state file: {e}")
    
    def update_record(self, email_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update specific fields of an email record.
        
        Args:
            email_id: ID of email to update
            updates: Dictionary of field updates
            
        Returns:
            True if record was found and updated, False otherwise
            
        Raises:
            IOError: If file operations fail
        """
        records = self.read_state()
        updated = False
        
        for record in records:
            if record.email_id == email_id:
                # Update fields
                for field, value in updates.items():
                    if hasattr(record, field):
                        setattr(record, field, value)
                
                # Update timestamp
                record.timestamp = datetime.now(timezone.utc).isoformat()
                updated = True
                break
        
        if updated:
            self.write_state(records)
        
        return updated
    
    def find_record(self, email_id: str) -> Optional[EmailRecord]:
        """
        Find email record by ID.
        
        Args:
            email_id: ID of email to find
            
        Returns:
            EmailRecord if found, None otherwise
        """
        records = self.read_state()
        for record in records:
            if record.email_id == email_id:
                return record
        return None
    
    def find_stale_records(self, hours: int = 48) -> List[EmailRecord]:
        """
        Find records that haven't been updated in specified hours.
        
        Args:
            hours: Number of hours to consider stale
            
        Returns:
            List of stale EmailRecord objects
        """
        records = self.read_state()
        stale_records = []
        
        for record in records:
            if record.is_stale(hours):
                stale_records.append(record)
        
        return stale_records
    
    def find_in_progress_records(self) -> List[EmailRecord]:
        """
        Find records with in-progress or awaiting status.
        
        Returns:
            List of EmailRecord objects that need resuming
        """
        records = self.read_state()
        in_progress = []
        
        resume_statuses = {
            EmailStatus.IN_PROGRESS,
            EmailStatus.AWAITING_CLARIFICATION,
            EmailStatus.AWAITING_RESPONSE,
        }
        
        for record in records:
            if record.status in resume_statuses:
                in_progress.append(record)
        
        return in_progress
    
    def has_conversation(self, conversation_id: str) -> bool:
        """
        Check if a conversation ID has already been processed.
        
        Args:
            conversation_id: Conversation ID to check
            
        Returns:
            True if conversation exists in state, False otherwise
        """
        if not conversation_id:
            return False
        
        records = self.read_state()
        for record in records:
            if record.conversation_id == conversation_id:
                return True
        
        return False
    
    def backup_corrupted_state(self) -> str:
        """
        Rename corrupted state file with timestamp and create fresh file.
        
        Returns:
            Path to the backed up corrupted file
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        corrupted_file = Path(f"{self.state_file}.corrupted_{timestamp}")
        
        if self.state_file.exists():
            shutil.move(str(self.state_file), str(corrupted_file))
        
        # Create fresh empty state file
        self.state_file.touch()
        
        return str(corrupted_file)
    
    def _read_backup(self) -> List[EmailRecord]:
        """Read from backup file."""
        records = []
        with open(self.backup_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        record = EmailRecord.from_dict(data)
                        records.append(record)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue
        return records

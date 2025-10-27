"""
Notification logger for tracking SRM update notifications.
"""

import json
import os
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path


class NotificationLogger:
    """
    Logger for SRM update notifications.
    
    Logs notification events to a separate JSONL file for tracking
    and audit purposes.
    """
    
    def __init__(self, log_file: str = "agent/state/notifications.log"):
        """
        Initialize notification logger.
        
        Args:
            log_file: Path to notification log file (JSONL format)
        """
        self.log_file = log_file
        
        # Ensure directory exists
        log_dir = os.path.dirname(log_file)
        if log_dir:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
    
    def log_notification_sent(
        self,
        srm_id: str,
        recipients: List[str],
        fields_changed: List[str],
        sent_by: Optional[str] = None,
        additional_info: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a successful notification send.
        
        Args:
            srm_id: ID of SRM that was updated
            recipients: List of email addresses notified
            fields_changed: List of field names that were changed
            sent_by: Optional name/email of person who requested the change
            additional_info: Optional additional information to log
        """
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'srm_id': srm_id,
            'recipients': recipients,
            'fields_changed': fields_changed,
            'sent_by': sent_by,
            'status': 'success',
        }
        
        if additional_info:
            log_entry['additional_info'] = additional_info
        
        self._write_log_entry(log_entry)
    
    def log_notification_failed(
        self,
        srm_id: str,
        recipients: List[str],
        error_message: str,
        fields_changed: Optional[List[str]] = None,
        sent_by: Optional[str] = None
    ) -> None:
        """
        Log a failed notification attempt.
        
        Args:
            srm_id: ID of SRM that was updated
            recipients: List of email addresses that notification was attempted to
            error_message: Error message describing the failure
            fields_changed: Optional list of field names that were changed
            sent_by: Optional name/email of person who requested the change
        """
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'srm_id': srm_id,
            'recipients': recipients,
            'fields_changed': fields_changed or [],
            'sent_by': sent_by,
            'status': 'failed',
            'error': error_message,
        }
        
        self._write_log_entry(log_entry)
    
    def _write_log_entry(self, entry: Dict[str, Any]) -> None:
        """
        Write log entry to JSONL file.
        
        Args:
            entry: Log entry dictionary
        """
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            # If we can't write to the log, print to console as fallback
            print(f"WARNING: Failed to write to notification log: {e}")
            print(f"Log entry: {json.dumps(entry)}")
    
    def get_recent_notifications(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent notification log entries.
        
        Args:
            limit: Maximum number of entries to return
            
        Returns:
            List of log entry dictionaries (most recent first)
        """
        if not os.path.exists(self.log_file):
            return []
        
        entries = []
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            print(f"WARNING: Failed to read notification log: {e}")
            return []
        
        # Return most recent first
        return entries[-limit:][::-1]
    
    def get_notifications_for_srm(self, srm_id: str) -> List[Dict[str, Any]]:
        """
        Get all notification log entries for a specific SRM.
        
        Args:
            srm_id: SRM ID to filter by
            
        Returns:
            List of log entry dictionaries for the specified SRM
        """
        all_entries = self.get_recent_notifications(limit=10000)  # Get all
        return [entry for entry in all_entries if entry.get('srm_id') == srm_id]


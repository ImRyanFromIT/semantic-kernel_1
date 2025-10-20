"""
File-based email reader for testing without Microsoft Graph API.

Reads emails from text files in the Test/ directory.
"""

import os
import re
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime


class FileEmailReader:
    """
    Reads emails from text files for testing purposes.
    
    Email files should be in the format:
    Subject: <subject>
    From: <sender>
    Date: <iso_date>
    ID: <email_id>
    
    <email_body>
    """
    
    def __init__(self, test_directory: str = "test_emails/Inbox"):
        """
        Initialize file email reader.
        
        Args:
            test_directory: Directory containing email text files
        """
        self.test_directory = Path(test_directory)
        self.processed_files = set()
    
    def parse_email_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """
        Parse an email text file.
        
        Args:
            file_path: Path to email text file
            
        Returns:
            Dictionary with email data or None if parsing fails
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse headers
            lines = content.split('\n')
            headers = {}
            body_start = 0
            
            for i, line in enumerate(lines):
                if line.strip() == '':
                    body_start = i + 1
                    break
                
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip().lower()] = value.strip()
            
            # Extract body
            body = '\n'.join(lines[body_start:]).strip()
            
            # Validate required headers
            required_headers = ['subject', 'from', 'date', 'id']
            for header in required_headers:
                if header not in headers:
                    print(f"Warning: Missing header '{header}' in {file_path}")
                    return None
            
            # Create email record
            email_data = {
                'email_id': headers['id'],
                'sender': headers['from'],
                'subject': headers['subject'],
                'body': body,
                'received_datetime': headers['date'],
                'conversation_id': f"conv_{headers['id']}"
            }
            
            return email_data
            
        except Exception as e:
            print(f"Error parsing email file {file_path}: {e}")
            return None
    
    def fetch_emails(self, 
                     days_back: int = 7, 
                     processed_email_ids: List[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch emails from text files.
        
        Args:
            days_back: Number of days to look back (ignored for file-based)
            processed_email_ids: List of already processed email IDs
            
        Returns:
            List of email dictionaries
        """
        processed_email_ids = processed_email_ids or []
        emails = []
        
        if not self.test_directory.exists():
            print(f"Inbox directory {self.test_directory} does not exist")
            return emails
        
        # Find all .txt files in test directory
        email_files = list(self.test_directory.glob("*.txt"))
        
        for file_path in email_files:
            # Skip if already processed
            if file_path.name in self.processed_files:
                continue
            
            email_data = self.parse_email_file(file_path)
            if email_data:
                # Skip if email ID already processed
                if email_data['email_id'] not in processed_email_ids:
                    emails.append(email_data)
                    self.processed_files.add(file_path.name)
        
        return emails
    
    def mark_file_as_processed(self, email_id: str) -> None:
        """
        Mark an email file as processed.
        
        Args:
            email_id: ID of the email to mark as processed
        """
        # Find the file with this email ID
        for file_path in self.test_directory.glob("*.txt"):
            email_data = self.parse_email_file(file_path)
            if email_data and email_data['email_id'] == email_id:
                self.processed_files.add(file_path.name)
                break
    
    def reset_processed_files(self) -> None:
        """Reset the list of processed files for testing."""
        self.processed_files.clear()
    
    def list_available_emails(self) -> List[str]:
        """
        List all available email files.
        
        Returns:
            List of email file names
        """
        if not self.test_directory.exists():
            return []
        
        return [f.name for f in self.test_directory.glob("*.txt")]

"""
Email plugin for Microsoft Graph API operations.
"""

from typing import List, Dict, Any, Optional
from semantic_kernel.functions import kernel_function

from ..utils.graph_client import GraphClient
from ..utils.error_handler import ErrorHandler, ErrorType


class EmailPlugin:
    """
    Semantic Kernel plugin for email operations using Microsoft Graph API.
    """
    
    def __init__(self, graph_client: GraphClient, error_handler: ErrorHandler):
        """
        Initialize email plugin.
        
        Args:
            graph_client: Configured GraphClient instance
            error_handler: ErrorHandler for retry logic
        """
        self.graph_client = graph_client
        self.error_handler = error_handler
    
    @kernel_function(
        description="Authenticate with Microsoft Graph API",
        name="authenticate_graph"
    )
    def authenticate(self) -> str:
        """
        Authenticate with Microsoft Graph API.
        
        Returns:
            Success or error message
        """
        try:
            success = self.graph_client.authenticate()
            if success:
                return "Successfully authenticated with Microsoft Graph API"
            else:
                return "Failed to authenticate with Microsoft Graph API"
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.GRAPH_API_AUTH, 
                e, 
                "authenticate_graph",
                escalate=True
            )
            return f"Authentication failed: {e}"
    
    @kernel_function(
        description="Fetch new emails from the monitored mailbox",
        name="fetch_emails"
    )
    def fetch_emails(self, 
                     days_back: int = 7, 
                     processed_email_ids: str = "") -> str:
        """
        Fetch unprocessed emails from mailbox.
        
        Args:
            days_back: Number of days to look back
            processed_email_ids: Comma-separated list of processed email IDs
            
        Returns:
            JSON string of email list or error message
        """
        try:
            processed_ids = [id.strip() for id in processed_email_ids.split(",") if id.strip()]
            
            @self.error_handler.with_retry(ErrorType.GRAPH_API_CALL)
            def _fetch():
                return self.graph_client.fetch_emails(days_back, processed_ids)
            
            emails = _fetch()
            
            # Return as JSON string for Semantic Kernel
            import json
            return json.dumps(emails, indent=2)
            
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.GRAPH_API_CALL,
                e,
                "fetch_emails"
            )
            return f"Failed to fetch emails: {e}"
    
    @kernel_function(
        description="Send a new email",
        name="send_email"
    )
    def send_email(self, 
                   to_address: str, 
                   subject: str, 
                   body: str, 
                   cc_addresses: str = "") -> str:
        """
        Send a new email.
        
        Args:
            to_address: Recipient email address
            subject: Email subject
            body: Email body content
            cc_addresses: Comma-separated CC recipients
            
        Returns:
            Success or error message
        """
        try:
            cc_list = [addr.strip() for addr in cc_addresses.split(",") if addr.strip()]
            
            @self.error_handler.with_retry(ErrorType.GRAPH_API_CALL)
            def _send():
                return self.graph_client.send_email(to_address, subject, body, cc_list)
            
            success = _send()
            
            if success:
                return f"Email sent successfully to {to_address}"
            else:
                return f"Failed to send email to {to_address}"
                
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.GRAPH_API_CALL,
                e,
                "send_email"
            )
            return f"Failed to send email: {e}"
    
    @kernel_function(
        description="Reply to an existing email",
        name="reply_to_email"
    )
    def reply_to_email(self, email_id: str, reply_body: str) -> str:
        """
        Reply to an existing email.
        
        Args:
            email_id: ID of email to reply to
            reply_body: Reply content
            
        Returns:
            Success or error message
        """
        try:
            @self.error_handler.with_retry(ErrorType.GRAPH_API_CALL)
            def _reply():
                return self.graph_client.reply_to_email(email_id, reply_body)
            
            success = _reply()
            
            if success:
                return f"Reply sent successfully for email {email_id}"
            else:
                return f"Failed to send reply for email {email_id}"
                
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.GRAPH_API_CALL,
                e,
                "reply_to_email"
            )
            return f"Failed to reply to email: {e}"
    
    @kernel_function(
        description="Forward an email to support team for escalation",
        name="escalate_email"
    )
    def escalate_email(self, 
                       email_id: str, 
                       to_addresses: str, 
                       escalation_reason: str) -> str:
        """
        Forward email to support team for escalation.
        
        Args:
            email_id: ID of email to escalate
            to_addresses: Comma-separated support team addresses
            escalation_reason: Reason for escalation
            
        Returns:
            Success or error message
        """
        try:
            support_addresses = [addr.strip() for addr in to_addresses.split(",") if addr.strip()]
            
            comment = (
                f"[SRM Agent Escalation]\n"
                f"Reason: {escalation_reason}\n"
                f"This email requires manual review and handling.\n"
                f"Original email ID: {email_id}"
            )
            
            @self.error_handler.with_retry(ErrorType.GRAPH_API_CALL)
            def _escalate():
                return self.graph_client.forward_email(email_id, support_addresses, comment)
            
            success = _escalate()
            
            if success:
                return f"Email {email_id} escalated successfully to support team"
            else:
                return f"Failed to escalate email {email_id}"
                
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.GRAPH_API_CALL,
                e,
                "escalate_email"
            )
            return f"Failed to escalate email: {e}"

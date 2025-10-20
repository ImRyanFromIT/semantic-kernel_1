"""
Microsoft Graph client wrapper for email operations.
"""

import asyncio
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from azure.identity import ClientSecretCredential
from msgraph import GraphServiceClient
from msgraph.generated.users.item.messages.messages_request_builder import MessagesRequestBuilder
from kiota_abstractions.base_request_configuration import RequestConfiguration

from .file_email_reader import FileEmailReader


def _run_async_safe(coro):
    """
    Helper function to run async coroutines safely from sync context.
    
    Only use this from synchronous code (like tests). 
    From async code, await the async methods directly.
    
    Args:
        coro: Coroutine to run
        
    Returns:
        Result of the coroutine
    """
    try:
        # Check if we're already in an event loop
        asyncio.get_running_loop()
        # If we get here, we're in a running loop - cannot use this function
        raise RuntimeError(
            "Cannot use _run_async_safe from within an async context. "
            "Use the async method versions instead (fetch_emails_async, reply_to_email_async, etc.)"
        )
    except RuntimeError:
        # No running loop - safe to create one
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        except Exception:
            return asyncio.run(coro)


class GraphClient:
    """
    Wrapper for Microsoft Graph SDK operations.
    
    Provides simplified interface for email operations needed by the agent.
    """
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str, mailbox: str, test_mode: bool = False):
        """
        Initialize Graph client.
        
        Args:
            tenant_id: Azure AD tenant ID
            client_id: Application client ID
            client_secret: Application client secret
            mailbox: Email address of mailbox to monitor
            test_mode: If True, use file-based email reading instead of Graph API
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.mailbox = mailbox
        self.test_mode = test_mode
        self._client = None
        self._authenticated = False
        
        # Initialize file email reader for test mode
        if self.test_mode:
            self.file_reader = FileEmailReader()
        else:
            self.file_reader = None
    
    def authenticate(self) -> bool:
        """
        Authenticate with Microsoft Graph API.
        
        Returns:
            True if authentication successful, False otherwise
            
        Raises:
            Exception: If authentication fails
        """
        try:
            if self.test_mode:
                # In test mode, always succeed if we have basic parameters
                if self.tenant_id and self.client_id:
                    self._authenticated = True
                    print(f"[TEST MODE] Graph API authentication simulated successfully")
                    return True
                else:
                    raise ValueError("Missing required test parameters")
            
            # Validate required parameters
            if not all([self.tenant_id, self.client_id, self.client_secret, self.mailbox]):
                raise ValueError("Missing required authentication parameters: TENANT_ID, CLIENT_ID, CLIENT_SECRET, MAILBOX_EMAIL")
            
            # Create credential for application permissions (client credentials flow)
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            
            # Initialize Graph client with application permissions scope
            self._client = GraphServiceClient(
                credentials=credential,
                scopes=['https://graph.microsoft.com/.default']
            )
            
            self._authenticated = True
            print(f"Successfully authenticated with Microsoft Graph API for mailbox: {self.mailbox}")
            return True
                
        except Exception as e:
            self._authenticated = False
            raise Exception(f"Graph API authentication failed: {e}")
    
    async def _fetch_emails_async(self, 
                                   days_back: int = 7, 
                                   processed_email_ids: List[str] = None) -> List[Dict[str, Any]]:
        """
        Async implementation to fetch emails from mailbox.
        
        Args:
            days_back: Number of days to look back for emails
            processed_email_ids: List of email IDs already processed
            
        Returns:
            List of email dictionaries with required fields
        """
        processed_email_ids = processed_email_ids or []
        
        # Calculate date filter for emails
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        cutoff_iso = cutoff_date.strftime('%Y-%m-%dT%H:%M:%SZ')
        
        # Configure request to fetch messages
        query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
            filter=f"receivedDateTime ge {cutoff_iso}",
            select=['id', 'subject', 'from', 'body', 'receivedDateTime', 'conversationId'],
            orderby=['receivedDateTime DESC'],
            top=50  # Limit to 50 most recent emails
        )
        
        request_config = RequestConfiguration(
            query_parameters=query_params
        )
        
        # Fetch messages from Inbox folder only (excludes Deleted Items, Sent Items, etc.)
        messages_response = await self._client.users.by_user_id(self.mailbox).mail_folders.by_mail_folder_id("Inbox").messages.get(
            request_configuration=request_config
        )
        
        emails = []
        if messages_response and messages_response.value:
            for message in messages_response.value:
                # Skip if already processed
                if message.id in processed_email_ids:
                    continue
                
                # Extract sender email address
                sender = message.from_.email_address.address if message.from_ and message.from_.email_address else "unknown@unknown.com"
                
                # Extract body content
                body = message.body.content if message.body else ""
                
                # Format received datetime
                received_dt = message.received_date_time.isoformat() if message.received_date_time else datetime.utcnow().isoformat()
                
                email_data = {
                    'email_id': message.id,
                    'sender': sender,
                    'subject': message.subject or "(No Subject)",
                    'body': body,
                    'received_datetime': received_dt,
                    'conversation_id': message.conversation_id or f"conv_{message.id}"
                }
                
                emails.append(email_data)
        
        print(f"Fetched {len(emails)} new emails from {self.mailbox}")
        return emails
    
    async def fetch_emails_async(self, 
                                  days_back: int = 7, 
                                  processed_email_ids: List[str] = None) -> List[Dict[str, Any]]:
        """
        Async version: Fetch unprocessed emails from the mailbox.
        
        Use this from async code (like the agent's monitoring loop).
        
        Args:
            days_back: Number of days to look back for emails
            processed_email_ids: List of email IDs already processed
            
        Returns:
            List of email dictionaries with required fields
            
        Raises:
            Exception: If API call fails
        """
        if not self._authenticated:
            raise Exception("Not authenticated. Call authenticate() first.")
        
        processed_email_ids = processed_email_ids or []
        
        try:
            if self.test_mode:
                # Use file-based email reading
                emails = self.file_reader.fetch_emails(days_back, processed_email_ids)
                print(f"[TEST MODE] Fetched {len(emails)} emails from test_emails/Inbox/ directory")
                return emails
            
            # Call async implementation directly
            return await self._fetch_emails_async(days_back, processed_email_ids)
            
        except Exception as e:
            raise Exception(f"Failed to fetch emails: {e}")
    
    def fetch_emails(self, 
                     days_back: int = 7, 
                     processed_email_ids: List[str] = None) -> List[Dict[str, Any]]:
        """
        Sync version: Fetch unprocessed emails from the mailbox.
        
        Use this from synchronous code (like tests). 
        From async code, use fetch_emails_async() instead.
        
        Args:
            days_back: Number of days to look back for emails
            processed_email_ids: List of email IDs already processed
            
        Returns:
            List of email dictionaries with required fields
            
        Raises:
            Exception: If API call fails
        """
        if not self._authenticated:
            raise Exception("Not authenticated. Call authenticate() first.")
        
        processed_email_ids = processed_email_ids or []
        
        try:
            if self.test_mode:
                # Use file-based email reading
                emails = self.file_reader.fetch_emails(days_back, processed_email_ids)
                print(f"[TEST MODE] Fetched {len(emails)} emails from test_emails/Inbox/ directory")
                return emails
            
            # Run async operation synchronously (only safe from sync context)
            return _run_async_safe(self._fetch_emails_async(days_back, processed_email_ids))
            
        except Exception as e:
            raise Exception(f"Failed to fetch emails: {e}")
    
    async def _send_email_async(self, to_address: str, subject: str, body: str, cc_addresses: List[str] = None) -> bool:
        """
        Async implementation to send an email.
        
        Args:
            to_address: Recipient email address
            subject: Email subject
            body: Email body content
            cc_addresses: Optional CC recipients
            
        Returns:
            True if email sent successfully
        """
        # Import required classes
        from msgraph.generated.users.item.send_mail.send_mail_post_request_body import SendMailPostRequestBody
        from msgraph.generated.models.message import Message
        from msgraph.generated.models.recipient import Recipient
        from msgraph.generated.models.email_address import EmailAddress
        from msgraph.generated.models.item_body import ItemBody
        from msgraph.generated.models.body_type import BodyType
        
        # Create message
        message = Message()
        message.subject = subject
        
        # Set body
        message.body = ItemBody()
        message.body.content_type = BodyType.Text
        message.body.content = body
        
        # Set recipients
        to_recipient = Recipient()
        to_recipient.email_address = EmailAddress()
        to_recipient.email_address.address = to_address
        message.to_recipients = [to_recipient]
        
        # Add CC recipients if provided
        if cc_addresses:
            cc_recipients = []
            for cc_addr in cc_addresses:
                cc_recipient = Recipient()
                cc_recipient.email_address = EmailAddress()
                cc_recipient.email_address.address = cc_addr
                cc_recipients.append(cc_recipient)
            message.cc_recipients = cc_recipients
        
        # Create request body
        request_body = SendMailPostRequestBody()
        request_body.message = message
        request_body.save_to_sent_items = True
        
        # Send email (await the async call)
        await self._client.users.by_user_id(self.mailbox).send_mail.post(body=request_body)
        
        print(f"Successfully sent email to {to_address}")
        return True
    
    def send_email(self, 
                   to_address: str, 
                   subject: str, 
                   body: str, 
                   cc_addresses: List[str] = None) -> bool:
        """
        Send a new email.
        
        Args:
            to_address: Recipient email address
            subject: Email subject
            body: Email body content
            cc_addresses: Optional CC recipients
            
        Returns:
            True if email sent successfully, False otherwise
            
        Raises:
            Exception: If API call fails
        """
        if not self._authenticated:
            raise Exception("Not authenticated. Call authenticate() first.")
        
        try:
            if self.test_mode:
                # In test mode, just log the email
                print(f"[TEST MODE] Would send email to {to_address}")
                print(f"Subject: {subject}")
                print(f"Body: {body[:100]}...")
                return True
            
            # Run async operation synchronously
            return _run_async_safe(self._send_email_async(to_address, subject, body, cc_addresses))
            
        except Exception as e:
            raise Exception(f"Failed to send email: {e}")
    
    async def _reply_to_email_async(self, email_id: str, reply_body: str) -> bool:
        """
        Async implementation to reply to an email.
        
        Args:
            email_id: ID of email to reply to
            reply_body: Reply content (can include \r\n for line breaks)
            
        Returns:
            True if reply sent successfully
        """
        # Import required classes
        from msgraph.generated.users.item.messages.item.reply.reply_post_request_body import ReplyPostRequestBody
        from msgraph.generated.models.message import Message
        from msgraph.generated.models.item_body import ItemBody
        from msgraph.generated.models.body_type import BodyType
        
        # Create message with properly formatted body
        message = Message()
        message.body = ItemBody()
        
        # Convert \r\n to HTML line breaks for better rendering
        html_body = reply_body.replace("\r\n", "<br>").replace("\n", "<br>")
        message.body.content_type = BodyType.Html
        message.body.content = html_body
        
        # Create reply request body
        reply_request = ReplyPostRequestBody()
        reply_request.message = message
        
        # Send reply using Graph API (await the async call)
        await self._client.users.by_user_id(self.mailbox).messages.by_message_id(email_id).reply.post(
            body=reply_request
        )
        
        print(f"Successfully sent reply to email {email_id}")
        return True
    
    async def reply_to_email_async(self, email_id: str, reply_body: str) -> bool:
        """
        Async version: Reply to an existing email.
        
        Use this from async code (like the agent).
        
        Args:
            email_id: ID of email to reply to
            reply_body: Reply content
            
        Returns:
            True if reply sent successfully
            
        Raises:
            Exception: If API call fails
        """
        if not self._authenticated:
            raise Exception("Not authenticated. Call authenticate() first.")
        
        try:
            if self.test_mode:
                # In test mode, just log the reply
                print(f"[TEST MODE] Would reply to email {email_id}")
                print(f"Reply body: {reply_body[:100]}...")
                return True
            
            # Call async implementation directly
            return await self._reply_to_email_async(email_id, reply_body)
            
        except Exception as e:
            raise Exception(f"Failed to reply to email: {e}")
    
    def reply_to_email(self, 
                       email_id: str, 
                       reply_body: str) -> bool:
        """
        Sync version: Reply to an existing email.
        
        Use this from synchronous code. From async code, use reply_to_email_async().
        
        Args:
            email_id: ID of email to reply to
            reply_body: Reply content
            
        Returns:
            True if reply sent successfully, False otherwise
            
        Raises:
            Exception: If API call fails
        """
        if not self._authenticated:
            raise Exception("Not authenticated. Call authenticate() first.")
        
        try:
            if self.test_mode:
                # In test mode, just log the reply
                print(f"[TEST MODE] Would reply to email {email_id}")
                print(f"Reply body: {reply_body[:100]}...")
                return True
            
            # Run async operation synchronously
            return _run_async_safe(self._reply_to_email_async(email_id, reply_body))
            
        except Exception as e:
            raise Exception(f"Failed to reply to email: {e}")
    
    async def _forward_email_async(self, email_id: str, to_addresses: List[str], comment: str = "") -> bool:
        """
        Async implementation to forward an email.
        
        Args:
            email_id: ID of email to forward
            to_addresses: List of recipient email addresses
            comment: Optional comment to add to forwarded email
            
        Returns:
            True if email forwarded successfully
        """
        # Import required classes
        from msgraph.generated.users.item.messages.item.forward.forward_post_request_body import ForwardPostRequestBody
        from msgraph.generated.models.recipient import Recipient
        from msgraph.generated.models.email_address import EmailAddress
        
        # Create forward request
        forward_request = ForwardPostRequestBody()
        forward_request.comment = comment
        
        # Add recipients
        recipients = []
        for addr in to_addresses:
            recipient = Recipient()
            recipient.email_address = EmailAddress()
            recipient.email_address.address = addr
            recipients.append(recipient)
        forward_request.to_recipients = recipients
        
        # Forward email (await the async call)
        await self._client.users.by_user_id(self.mailbox).messages.by_message_id(email_id).forward.post(
            body=forward_request
        )
        
        print(f"Successfully forwarded email {email_id} to {', '.join(to_addresses)}")
        return True
    
    async def forward_email_async(self, email_id: str, to_addresses: List[str], comment: str = "") -> bool:
        """
        Async version: Forward an email to specified recipients.
        
        Use this from async code (like the agent).
        
        Args:
            email_id: ID of email to forward
            to_addresses: List of recipient email addresses
            comment: Optional comment to add to forwarded email
            
        Returns:
            True if email forwarded successfully
            
        Raises:
            Exception: If API call fails
        """
        if not self._authenticated:
            raise Exception("Not authenticated. Call authenticate() first.")
        
        try:
            if self.test_mode:
                # In test mode, just log the forward
                print(f"[TEST MODE] Would forward email {email_id} to {', '.join(to_addresses)}")
                if comment:
                    print(f"Comment: {comment[:100]}...")
                return True
            
            # Call async implementation directly
            return await self._forward_email_async(email_id, to_addresses, comment)
            
        except Exception as e:
            raise Exception(f"Failed to forward email: {e}")
    
    def forward_email(self, 
                      email_id: str, 
                      to_addresses: List[str], 
                      comment: str = "") -> bool:
        """
        Sync version: Forward an email to specified recipients.
        
        Use this from synchronous code. From async code, use forward_email_async().
        
        Args:
            email_id: ID of email to forward
            to_addresses: List of recipient email addresses
            comment: Optional comment to add to forwarded email
            
        Returns:
            True if email forwarded successfully, False otherwise
            
        Raises:
            Exception: If API call fails
        """
        if not self._authenticated:
            raise Exception("Not authenticated. Call authenticate() first.")
        
        try:
            if self.test_mode:
                # In test mode, just log the forward
                print(f"[TEST MODE] Would forward email {email_id} to {', '.join(to_addresses)}")
                if comment:
                    print(f"Comment: {comment[:100]}...")
                return True
            
            # Run async operation synchronously
            return _run_async_safe(self._forward_email_async(email_id, to_addresses, comment))
            
        except Exception as e:
            raise Exception(f"Failed to forward email: {e}")
    
    async def _mark_as_read_async(self, email_id: str) -> bool:
        """
        Async implementation to mark an email as read.
        
        Args:
            email_id: ID of email to mark as read
            
        Returns:
            True if successful
        """
        # Import required classes
        from msgraph.generated.models.message import Message
        
        # Create message update
        message = Message()
        message.is_read = True
        
        # Update message (await the async call)
        await self._client.users.by_user_id(self.mailbox).messages.by_message_id(email_id).patch(message)
        
        print(f"Marked email {email_id} as read")
        return True
    
    def mark_as_read(self, email_id: str) -> bool:
        """
        Mark an email as read.
        
        Args:
            email_id: ID of email to mark as read
            
        Returns:
            True if successful, False otherwise
        """
        if not self._authenticated:
            raise Exception("Not authenticated. Call authenticate() first.")
        
        try:
            if self.test_mode:
                # In test mode, just log the action
                print(f"[TEST MODE] Would mark email {email_id} as read")
                return True
            
            # Run async operation synchronously
            return _run_async_safe(self._mark_as_read_async(email_id))
            
        except Exception as e:
            raise Exception(f"Failed to mark email as read: {e}")

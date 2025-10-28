"""
Response Handler for the SRM Archivist Agent.

Handles sending email responses (success, rejection, escalation).
"""

import logging
from typing import Dict, Any, Optional

from .graph_client import GraphClient
from .state_manager import StateManager
from src.models.email_record import EmailStatus


class ResponseHandler:
    """
    Handles email response generation and sending.
    
    Centralizes all email response logic for success notifications,
    rejection responses, and escalations.
    """
    
    def __init__(
        self,
        graph_client: GraphClient,
        state_manager: StateManager,
        support_team_email: str,
        logger: Optional[logging.Logger] = None
    ):
        """
        Initialize ResponseHandler.
        
        Args:
            graph_client: Graph API client for sending emails
            state_manager: State manager for updating records
            support_team_email: Email address for escalations
            logger: Logger instance
        """
        self.graph_client = graph_client
        self.state_manager = state_manager
        self.support_team_email = support_team_email
        self.logger = logger or logging.getLogger(__name__)
    
    async def send_success_notification(
        self,
        email_id: str,
        extracted_data: Dict[str, Any],
        update_payload: Dict[str, Any]
    ) -> bool:
        """
        Send success notification to user after SRM update.
        
        Args:
            email_id: Email ID
            extracted_data: Extracted request data
            update_payload: Update payload with change details
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            self.logger.info(f"Sending success notification for email {email_id}")
            
            # Generate success message with HTML formatting
            srm_title = extracted_data.get('srm_title', 'Unknown SRM')
            updated_fields = list(update_payload['fields_to_update'].keys())
            
            # Build message with HTML formatting for better readability
            message_parts = []
            message_parts.append("<p><strong>Your SRM update request has been processed successfully.</strong></p>")
            message_parts.append("<hr>")
            message_parts.append(f"<p><b><u>SRM:</u></b> {srm_title}</p>")
            message_parts.append(f"<p><b><u>Updated fields:</u></b> {', '.join(updated_fields)}</p>")
            
            # Add details for each updated field
            new_values = update_payload.get('new_values', {})
            
            if 'owner_notes' in updated_fields:
                owner_notes = new_values.get('owner_notes', '')
                # Truncate if too long (keep first 300 chars for better preview)
                if len(owner_notes) > 300:
                    owner_notes_preview = owner_notes[:300] + "..."
                else:
                    owner_notes_preview = owner_notes
                
                message_parts.append("<p><b><u>Owner Notes Updated:</u></b></p>")
                message_parts.append(f"<p><i>{owner_notes_preview}</i></p>")
            
            if 'hidden_notes' in updated_fields:
                hidden_notes = new_values.get('hidden_notes', '')
                # Truncate if too long (keep first 300 chars)
                if len(hidden_notes) > 300:
                    hidden_notes_preview = hidden_notes[:300] + "..."
                else:
                    hidden_notes_preview = hidden_notes
                
                message_parts.append("<p><b><u>Hidden Notes Updated:</u></b></p>")
                message_parts.append(f"<p><i>{hidden_notes_preview}</i></p>")
            
            message_parts.append("<hr>")
            message_parts.append("<p><strong>The changes are now live in the chatbot system.</strong></p>")
            message_parts.append("<p>Thank you for helping keep our SRM information current!</p>")
            
            # Join all parts (HTML doesn't need explicit line breaks between tags)
            success_message = "\n".join(message_parts)
            
            # Send via Graph API
            await self.graph_client.reply_to_email_async(email_id, success_message)
            
            # Update state
            self.state_manager.update_record(
                email_id,
                {
                    'status': EmailStatus.COMPLETED_SUCCESS,
                    'success_notification': success_message
                }
            )
            
            self.logger.info(f"Success notification sent for email {email_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending success notification for {email_id}: {e}")
            return False
    
    async def send_rejection_response(
        self,
        email_id: str,
        reason: str
    ) -> bool:
        """
        Send polite rejection email for dont_help classification.
        
        Args:
            email_id: Email ID
            reason: Reason for rejection
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            self.logger.info(f"Sending rejection response for email {email_id}")
            
            # Generate rejection message with HTML formatting
            rejection_message = f"""
<p>Thank you for reaching out.</p>

<p>We're unable to process this request automatically because: <b>{reason}</b></p>

<p><b><u>What we can help with:</u></b></p>
<ul>
<li>Updating SRM owner notes (user-facing information)</li>
<li>Updating SRM hidden notes (recommendation logic)</li>
</ul>

<p>If you believe this was a mistake, please reply to this email and it will be escalated to a human for review.</p>

<p>Thank you for your understanding.</p>
"""
            
            # Send via Graph API
            await self.graph_client.reply_to_email_async(email_id, rejection_message)
            
            # Update state
            self.state_manager.update_record(
                email_id,
                {
                    'status': EmailStatus.COMPLETED_DONT_HELP,
                    'rejection_response': rejection_message
                }
            )
            
            self.logger.info(f"Rejection response sent for email {email_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending rejection response for {email_id}: {e}")
            return False
    
    async def send_escalation(
        self,
        email_id: str,
        reason: str,
        subject: Optional[str] = None,
        srm_title: Optional[str] = None,
        clarification_history: Optional[list] = None,
        clarification_attempts: int = 0
    ) -> bool:
        """
        Escalate email to support team.

        Args:
            email_id: Email ID
            reason: Reason for escalation
            subject: Email subject line (optional, for better formatting)
            srm_title: SRM title mentioned in request (optional, for better formatting)
            clarification_history: List of clarification Q&A exchanges (optional)
            clarification_attempts: Number of clarification attempts made (optional)

        Returns:
            True if escalated successfully, False otherwise
        """
        try:
            self.logger.info(f"Escalating email {email_id} to {self.support_team_email}")
            self.logger.info(f"Escalation reason: {reason}")

            # Generate escalation message for support team with HTML formatting
            escalation_parts = []
            escalation_parts.append("<p><strong><u>[SRM Agent Escalation]</u></strong></p>")
            escalation_parts.append("<hr>")

            if subject:
                escalation_parts.append(f"<p><b>Subject:</b> {subject}<br>")
            else:
                escalation_parts.append(f"<p><b>Email ID:</b> {email_id}<br>")

            if srm_title:
                escalation_parts.append(f"<b>SRM Requested:</b> {srm_title}<br>")

            escalation_parts.append(f"<b>Reason:</b> {reason}</p>")

            # Include clarification history if available
            if clarification_history and len(clarification_history) > 0:
                escalation_parts.append("<hr>")
                escalation_parts.append(f"<p><b>Agent Actions Taken:</b></p>")
                escalation_parts.append(f"<p>The agent attempted to clarify this request {clarification_attempts} time(s) but received insufficient information.</p>")
                escalation_parts.append("<p><b>Clarification Thread:</b></p>")

                for i, exchange in enumerate(clarification_history, 1):
                    escalation_parts.append(f"<div style='margin-left: 20px; margin-bottom: 15px;'>")
                    escalation_parts.append(f"<p><b>Attempt {i}:</b></p>")
                    escalation_parts.append(f"<p><i>Agent asked:</i></p>")
                    escalation_parts.append(f"<blockquote style='margin-left: 20px; padding-left: 10px; border-left: 3px solid #ccc;'>")
                    question = exchange.get('question', '(no question recorded)')
                    escalation_parts.append(f"{question.replace(chr(10), '<br>')}")
                    escalation_parts.append("</blockquote>")

                    escalation_parts.append(f"<p><i>User replied:</i></p>")
                    escalation_parts.append(f"<blockquote style='margin-left: 20px; padding-left: 10px; border-left: 3px solid #ccc;'>")
                    answer = exchange.get('answer', '(no answer recorded)')
                    escalation_parts.append(f"{answer.replace(chr(10), '<br>')}")
                    escalation_parts.append("</blockquote>")
                    escalation_parts.append("</div>")

            escalation_parts.append("<hr>")
            escalation_parts.append("<p>This email requires manual review and handling.<br>")
            escalation_parts.append("Please review the original email and take appropriate action.</p>")
            
            escalation_message = "\n".join(escalation_parts)
            
            # Forward to support team if configured
            if self.support_team_email:
                await self.graph_client.forward_email_async(
                    email_id=email_id,
                    to_addresses=[self.support_team_email],
                    comment=escalation_message
                )
            else:
                self.logger.warning("No support team email configured - escalation logged only")
            
            # Send acknowledgment to original sender with HTML formatting
            acknowledgment_parts = []
            acknowledgment_parts.append("<p>Thank you for contacting the SRM Archivist.</p>")
            acknowledgment_parts.append("<p><strong>Your request has been escalated to our support team for manual review.</strong></p>")
            acknowledgment_parts.append("<hr>")
            
            if srm_title:
                acknowledgment_parts.append(f"<p><b>SRM Requested:</b> {srm_title}<br>")
            else:
                acknowledgment_parts.append("<p>")
            
            acknowledgment_parts.append(f"<b>Reason:</b> {reason}</p>")
            acknowledgment_parts.append("<hr>")
            acknowledgment_parts.append("<p>You will hear from a human team member shortly.</p>")
            acknowledgment_parts.append("<p>Thank you for your patience.</p>")
            
            acknowledgment_message = "\n".join(acknowledgment_parts)
            
            await self.graph_client.reply_to_email_async(
                email_id=email_id,
                reply_body=acknowledgment_message
            )
            
            # Update state
            self.state_manager.update_record(
                email_id,
                {
                    'status': EmailStatus.ESCALATED,
                    'escalation_reason': reason,
                    'escalation_message': escalation_message,
                    'acknowledgment_sent': True
                }
            )
            
            self.logger.info(f"Email {email_id} escalated successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error escalating email {email_id}: {e}")
            return False
    
    async def send_clarification_request(
        self,
        email_id: str,
        clarification_text: str
    ) -> bool:
        """
        Request clarification from user for incomplete data.
        
        Args:
            email_id: Email ID
            clarification_text: Generated clarification request text
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            self.logger.info(f"Sending clarification request for email {email_id}")
            
            # Send via Graph API
            await self.graph_client.reply_to_email_async(email_id, clarification_text)
            
            # Update state
            self.state_manager.update_record(
                email_id,
                {
                    'status': EmailStatus.AWAITING_CLARIFICATION,
                    'clarification_request': clarification_text
                }
            )
            
            self.logger.info(f"Clarification request sent for email {email_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error sending clarification request for {email_id}: {e}")
            return False


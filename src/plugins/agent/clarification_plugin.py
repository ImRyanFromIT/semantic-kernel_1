"""
Clarification Plugin - Tools for agent to handle multi-turn clarification conversations.

Provides tools for sending clarification questions, checking for replies,
and merging replies with original context.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from semantic_kernel.functions import kernel_function

from src.utils.response_handler import ResponseHandler
from src.utils.state_manager import StateManager
from src.utils.graph_client import GraphClient
from src.models.email_record import EmailStatus


class ClarificationPlugin:
    """
    Semantic Kernel plugin providing tools for agent-driven clarification.

    Agent uses these tools to:
    - Ask clarification questions
    - Check for user replies
    - Merge replies with original context
    - Track attempt count
    """

    def __init__(
        self,
        response_handler: ResponseHandler,
        state_manager: StateManager,
        graph_client: GraphClient
    ):
        """
        Initialize clarification plugin.

        Args:
            response_handler: For sending clarification emails
            state_manager: For tracking clarification state
            graph_client: For fetching reply emails
        """
        self.response_handler = response_handler
        self.state_manager = state_manager
        self.graph_client = graph_client
        self.logger = logging.getLogger(__name__)

    @kernel_function(
        name="send_clarification_email",
        description="Send a clarification question to the user via email reply. Use this when you need to ask the user for more information or to resolve confusion."
    )
    async def send_clarification_email(
        self,
        email_id: str,
        question: str
    ) -> str:
        """
        Send clarification email and update state.

        Args:
            email_id: ID of email to reply to
            question: Clarification question to ask

        Returns:
            Confirmation message with current attempt count
        """
        try:
            self.logger.info(f"Sending clarification email for {email_id}: {question[:50]}...")

            # Get current record
            record = self.state_manager.find_record(email_id)
            if not record:
                return json.dumps({
                    'success': False,
                    'error': f'Email record {email_id} not found'
                })

            # Send clarification via response handler
            await self.response_handler.send_clarification_request(
                email_id=email_id,
                clarification_text=question
            )

            # Update record (don't increment attempts yet - wait for reply evaluation)
            self.state_manager.update_record(email_id, {
                'last_clarification_question': question,
                'status': EmailStatus.AWAITING_CLARIFICATION,
                'clarification_sent_datetime': datetime.utcnow().isoformat()
            })

            current_attempt_count = record.clarification_attempts

            return json.dumps({
                'success': True,
                'message': f'Clarification sent. Attempt {current_attempt_count + 1}/2. Waiting for user reply.',
                'attempts': current_attempt_count,
                'max_attempts': 2
            })

        except Exception as e:
            self.logger.error(f"Error sending clarification email: {e}", exc_info=True)
            return json.dumps({
                'success': False,
                'error': str(e)
            })

    @kernel_function(
        name="check_for_reply",
        description="Check if the user has replied to the clarification request. Returns whether a reply exists and the reply content if available."
    )
    async def check_for_reply(self, email_id: str) -> str:
        """
        Check for user reply in email thread.

        Args:
            email_id: ID of original email

        Returns:
            JSON with has_reply, reply_body, reply_time
        """
        try:
            record = self.state_manager.find_record(email_id)
            if not record:
                return json.dumps({
                    'has_reply': False,
                    'error': f'Email record {email_id} not found'
                })

            if not record.conversation_id:
                return json.dumps({
                    'has_reply': False,
                    'error': 'No conversation ID tracked'
                })

            if not record.clarification_sent_datetime:
                return json.dumps({
                    'has_reply': False,
                    'error': 'No clarification sent yet'
                })

            self.logger.info(f"Checking for reply to {email_id}")

            # Fetch emails in same conversation (Graph client might not support this filter, try anyway)
            # Fallback: Fetch recent emails and filter manually
            try:
                new_emails = await self.graph_client.fetch_emails_async(
                    days_back=2,  # Look at last 2 days
                    processed_email_ids=[]  # Don't filter by processed
                )
            except Exception as fetch_error:
                self.logger.warning(f"Error fetching emails: {fetch_error}")
                new_emails = []

            # Find replies from original sender in same conversation after clarification was sent
            # Parse clarification time with timezone handling
            clarification_time_str = record.clarification_sent_datetime
            if clarification_time_str.endswith('Z'):
                clarification_time = datetime.fromisoformat(clarification_time_str.replace('Z', '+00:00'))
            elif '+' in clarification_time_str or clarification_time_str.count('-') > 2:
                clarification_time = datetime.fromisoformat(clarification_time_str)
            else:
                # No timezone info, assume UTC
                from datetime import timezone
                clarification_time = datetime.fromisoformat(clarification_time_str).replace(tzinfo=timezone.utc)

            replies = []
            for email in new_emails:
                # Check if from original sender
                if email.get('sender', '').lower() != record.sender.lower():
                    continue

                # Check if in same conversation
                if email.get('conversation_id') != record.conversation_id:
                    continue

                # Check if after clarification was sent
                email_time_str = email.get('received_datetime', '')
                try:
                    # Parse email time with timezone handling
                    if email_time_str.endswith('Z'):
                        email_time = datetime.fromisoformat(email_time_str.replace('Z', '+00:00'))
                    elif '+' in email_time_str or email_time_str.count('-') > 2:
                        email_time = datetime.fromisoformat(email_time_str)
                    else:
                        # No timezone info, assume UTC
                        from datetime import timezone
                        email_time = datetime.fromisoformat(email_time_str).replace(tzinfo=timezone.utc)

                    if email_time <= clarification_time:
                        continue
                except (ValueError, AttributeError):
                    continue

                # This is a reply!
                replies.append(email)

            if replies:
                # Get most recent reply
                reply = max(replies, key=lambda e: e.get('received_datetime', ''))

                self.logger.info(f"Found reply for {email_id} from {reply['sender']}")

                return json.dumps({
                    'has_reply': True,
                    'reply_body': reply['body'],
                    'reply_time': reply['received_datetime'],
                    'reply_sender': reply['sender']
                })
            else:
                return json.dumps({
                    'has_reply': False,
                    'message': 'No reply yet, check again later'
                })

        except Exception as e:
            self.logger.error(f"Error checking for reply: {e}", exc_info=True)
            return json.dumps({
                'has_reply': False,
                'error': str(e)
            })

    @kernel_function(
        name="merge_reply_with_original",
        description="Merge the user's clarification reply with the original request to create enriched context for re-extraction. Call this after receiving a reply."
    )
    async def merge_reply_with_original(
        self,
        email_id: str,
        reply_body: str
    ) -> str:
        """
        Merge clarification reply into email context.

        Args:
            email_id: ID of original email
            reply_body: Body of user's reply

        Returns:
            Confirmation message
        """
        try:
            record = self.state_manager.find_record(email_id)
            if not record:
                return json.dumps({
                    'success': False,
                    'error': f'Email record {email_id} not found'
                })

            self.logger.info(f"Merging reply into context for {email_id}")

            # Update clarification history
            history = record.clarification_history or []
            history.append({
                'question': record.last_clarification_question or '(unknown)',
                'answer': reply_body,
                'timestamp': datetime.utcnow().isoformat()
            })

            # Build merged context
            history_text = ""
            for i, exchange in enumerate(history, 1):
                history_text += f"\nClarification {i}:\n"
                history_text += f"Q: {exchange['question']}\n"
                history_text += f"A: {exchange['answer']}\n"

            merged_body = f"""ORIGINAL REQUEST:
{record.original_body or record.body}

CLARIFICATION EXCHANGE:{history_text}

LATEST REPLY:
{reply_body}
"""

            # Update record
            self.state_manager.update_record(email_id, {
                'body': merged_body,
                'original_body': record.original_body or record.body,
                'clarification_history': history,
                'status': EmailStatus.IN_PROGRESS  # Ready for re-extraction
            })

            return json.dumps({
                'success': True,
                'message': 'Reply merged with original context. Ready for re-extraction.',
                'history_length': len(history)
            })

        except Exception as e:
            self.logger.error(f"Error merging reply: {e}", exc_info=True)
            return json.dumps({
                'success': False,
                'error': str(e)
            })

    @kernel_function(
        name="check_for_human_escalation_request",
        description="Check if the user's reply requests human assistance. Call this FIRST after receiving any reply to detect escalation requests. Returns true if user wants human help."
    )
    def check_for_human_escalation_request(self, reply_text: str) -> str:
        """
        Check if reply contains request for human escalation.

        Args:
            reply_text: The user's reply text

        Returns:
            JSON with is_escalation_request and detected_phrases
        """
        try:
            reply_lower = reply_text.lower()

            escalation_keywords = [
                'connect me with a human',
                'speak to a human',
                'talk to a human',
                'human representative',
                'human help',
                'speak to a person',
                'talk to a person',
                'real person',
                'escalate',
                'connect me with someone',
                'speak to someone',
                'contact support',
                'talk to support',
                'need a human',
                'need human help',
                'prefer human',
                'want to speak',
                'want to talk'
            ]

            detected = []
            for keyword in escalation_keywords:
                if keyword in reply_lower:
                    detected.append(keyword)

            is_request = len(detected) > 0

            if is_request:
                self.logger.info(
                    f"Detected escalation request in reply. Keywords found: {', '.join(detected)}"
                )

            return json.dumps({
                'is_escalation_request': is_request,
                'detected_phrases': detected,
                'message': 'User requested human assistance' if is_request else 'No escalation request detected'
            })

        except Exception as e:
            self.logger.error(f"Error checking for escalation request: {e}", exc_info=True)
            return json.dumps({
                'is_escalation_request': False,
                'error': str(e)
            })

    @kernel_function(
        name="record_unsatisfactory_reply",
        description="Record that the user's reply was insufficient/unclear. Call this after evaluating a reply that doesn't provide the needed information. This increments the attempt counter."
    )
    def record_unsatisfactory_reply(self, email_id: str, reason: str = "") -> str:
        """
        Record that a reply was received but insufficient.

        Args:
            email_id: ID of email
            reason: Why the reply was insufficient

        Returns:
            JSON with updated attempts count
        """
        try:
            record = self.state_manager.find_record(email_id)
            if not record:
                return json.dumps({
                    'error': f'Email record {email_id} not found'
                })

            new_attempts = record.clarification_attempts + 1
            self.state_manager.update_record(email_id, {
                'clarification_attempts': new_attempts
            })

            self.logger.info(
                f"Recorded unsatisfactory reply for {email_id}: {reason}. "
                f"Attempts now: {new_attempts}/2"
            )

            return json.dumps({
                'success': True,
                'attempts': new_attempts,
                'max_attempts': 2,
                'can_retry': new_attempts < 2
            })

        except Exception as e:
            self.logger.error(f"Error recording unsatisfactory reply: {e}", exc_info=True)
            return json.dumps({
                'error': str(e)
            })

    @kernel_function(
        name="get_clarification_attempts",
        description="Get the current number of clarification attempts made for this email. Maximum is 2 attempts."
    )
    def get_clarification_attempts(self, email_id: str) -> str:
        """
        Return current attempt count.

        Args:
            email_id: ID of email

        Returns:
            JSON with attempts, max_attempts, can_retry
        """
        try:
            record = self.state_manager.find_record(email_id)
            if not record:
                return json.dumps({
                    'error': f'Email record {email_id} not found'
                })

            attempts = record.clarification_attempts
            max_attempts = 2

            return json.dumps({
                'attempts': attempts,
                'max_attempts': max_attempts,
                'can_retry': attempts < max_attempts,
                'remaining': max(0, max_attempts - attempts)
            })

        except Exception as e:
            self.logger.error(f"Error getting attempt count: {e}", exc_info=True)
            return json.dumps({
                'error': str(e)
            })

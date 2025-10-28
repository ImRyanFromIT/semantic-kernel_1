"""
Email Intake Process for the SRM Archivist Agent.

Implements the email intake workflow using SK Process Framework with proper state management.
"""

from enum import Enum
from typing import Dict, Any, List
from datetime import datetime
from pydantic import Field
import json
import logging

from semantic_kernel import Kernel
from semantic_kernel.processes.process_builder import ProcessBuilder
from semantic_kernel.functions import kernel_function
from semantic_kernel.processes.kernel_process import (
    KernelProcessStep,
    KernelProcessStepContext,
    KernelProcessStepState,
)
from semantic_kernel.kernel_pydantic import KernelBaseModel
from semantic_kernel.processes.kernel_process.kernel_process_step_metadata import kernel_process_step_metadata

from src.models.email_record import EmailRecord, EmailStatus


logger = logging.getLogger(__name__)


# ============================================================================
# STEP STATE CLASSES
# ============================================================================

class InitializeStepState(KernelBaseModel):
    """State for initialization step."""
    state_loaded: bool = Field(default=False)
    records_count: int = Field(default=0)


class ResumeStepState(KernelBaseModel):
    """State for resume step."""
    in_progress_count: int = Field(default=0)
    escalated_stale_count: int = Field(default=0)


class FetchStepState(KernelBaseModel):
    """State for fetch emails step."""
    new_emails_count: int = Field(default=0)
    filtered_count: int = Field(default=0)


class ClassifyStepState(KernelBaseModel):
    """State for classification step."""
    classified_count: int = Field(default=0)
    classifications: List[Dict[str, Any]] = Field(default_factory=list)


class RouteStepState(KernelBaseModel):
    """State for routing step."""
    help_count: int = Field(default=0)
    dont_help_count: int = Field(default=0)
    escalate_count: int = Field(default=0)


# ============================================================================
# PROCESS STEPS
# ============================================================================

@kernel_process_step_metadata("InitializeStateStep.V2")
class InitializeStateStep(KernelProcessStep[InitializeStepState]):
    """Process step to initialize and check for resumable work."""

    state: InitializeStepState = Field(default_factory=InitializeStepState)

    async def activate(self, state: KernelProcessStepState) -> None:
        """Initialize step state."""
        if state and hasattr(state, 'state'):
            self.state = state.state
        else:
            self.state = InitializeStepState()

    class OutputEvents(Enum):
        StateLoaded = "StateLoaded"
        StateError = "StateError"

    @kernel_function(name="initialize")
    async def initialize(
        self,
        context: KernelProcessStepContext,
        input_data: Dict[str, Any]
    ) -> None:
        """Initialize agent state and check for resumable work."""
        try:
            logger.info("Initializing email intake process")

            # Get dependencies from input (passed via initial event)
            state_manager = input_data.get("state_manager")

            # Load existing state
            records = state_manager.read_state()
            self.state.records_count = len(records)
            self.state.state_loaded = True

            # Find incomplete work
            in_progress_records = state_manager.find_in_progress_records()
            stale_records = state_manager.find_stale_records(24)

            # Find records awaiting clarification
            awaiting_clarification = [r for r in records
                                     if r.status == EmailStatus.AWAITING_CLARIFICATION]

            # Escalate stale items
            escalated_count = 0
            for record in stale_records:
                if record.status in [EmailStatus.IN_PROGRESS, EmailStatus.AWAITING_RESPONSE]:
                    record.update_status(EmailStatus.ESCALATED, "Stale item - no response in 24 hours")
                    state_manager.update_record(record.email_id, {"status": record.status})
                    escalated_count += 1

            # Escalate clarification requests that are very stale (48 hours)
            stale_clarifications = state_manager.find_stale_records(48)
            for record in stale_clarifications:
                if record.status == EmailStatus.AWAITING_CLARIFICATION:
                    record.update_status(
                        EmailStatus.ESCALATED,
                        f"No clarification reply after 48 hours. Last question: {record.last_clarification_question}"
                    )
                    state_manager.update_record(record.email_id, {"status": record.status})
                    escalated_count += 1

            logger.info(
                f"State loaded: {len(records)} total records, "
                f"{len(in_progress_records)} in progress, "
                f"{len(awaiting_clarification)} awaiting clarification, "
                f"{escalated_count} stale items escalated"
            )

            # Pass all dependencies forward
            await context.emit_event(
                process_event=self.OutputEvents.StateLoaded.value,
                data={
                    **input_data,
                    "in_progress_records": [r.to_dict() for r in in_progress_records],
                    "awaiting_clarification_records": [r.to_dict() for r in awaiting_clarification],
                    "escalated_stale_count": escalated_count
                }
            )

        except Exception as e:
            logger.error(f"Error initializing state: {e}", exc_info=True)
            await context.emit_event(
                process_event=self.OutputEvents.StateError.value,
                data={"error": str(e), **input_data}
            )


@kernel_process_step_metadata("FetchNewEmailsStep.V2")
class FetchNewEmailsStep(KernelProcessStep[FetchStepState]):
    """Process step to fetch new emails from Microsoft Graph API."""

    state: FetchStepState = Field(default_factory=FetchStepState)

    async def activate(self, state: KernelProcessStepState) -> None:
        """Initialize step state."""
        if state and hasattr(state, 'state'):
            self.state = state.state
        else:
            self.state = FetchStepState()

    class OutputEvents(Enum):
        EmailsFetched = "EmailsFetched"
        NoNewEmails = "NoNewEmails"
        MassEmailDetected = "MassEmailDetected"

    @kernel_function(name="fetch_emails")
    async def fetch_emails(
        self,
        context: KernelProcessStepContext,
        input_data: Dict[str, Any]
    ) -> None:
        """Fetch and filter new emails from mailbox."""
        try:
            # Get dependencies
            state_manager = input_data.get("state_manager")
            graph_client = input_data.get("graph_client")
            config = input_data.get("config")

            if not graph_client:
                logger.warning("No graph client available, skipping email fetch")
                await context.emit_event(
                    process_event=self.OutputEvents.NoNewEmails.value,
                    data=input_data
                )
                return

            logger.info("Fetching new emails from inbox")

            # Get processed email IDs
            existing_records = state_manager.read_state()
            processed_ids = [record.email_id for record in existing_records]

            # Fetch new emails
            new_emails = await graph_client.fetch_emails_async(
                days_back=config.email_history_window_days,
                processed_email_ids=processed_ids
            )

            self.state.new_emails_count = len(new_emails) if new_emails else 0

            if not new_emails:
                logger.info("No new emails found")
                await context.emit_event(
                    process_event=self.OutputEvents.NoNewEmails.value,
                    data=input_data
                )
                return

            logger.info(f"Found {len(new_emails)} new emails")

            # Filter out emails from ourselves and duplicate conversations
            filtered_emails = []
            skipped_self = 0
            skipped_conversation = 0

            for email in new_emails:
                sender = email.get('sender', '').lower()
                conversation_id = email.get('conversation_id')

                # Skip emails from ourselves
                mailbox_email = config.graph_api.mailbox.lower() if config.graph_api else ""
                if sender == mailbox_email:
                    skipped_self += 1
                    continue

                # Skip emails in conversations we've already processed
                # UNLESS we're awaiting clarification on that conversation
                if conversation_id and state_manager.has_conversation(conversation_id):
                    # Check if any record in this conversation is awaiting clarification
                    conversation_records = [r for r in state_manager.read_state()
                                          if r.conversation_id == conversation_id]
                    awaiting_clarification = any(r.status == EmailStatus.AWAITING_CLARIFICATION
                                                for r in conversation_records)

                    if not awaiting_clarification:
                        # Only skip if NOT awaiting clarification
                        skipped_conversation += 1
                        continue

                filtered_emails.append(email)

            self.state.filtered_count = len(filtered_emails)

            # Log filtering summary
            if skipped_self > 0 or skipped_conversation > 0:
                logger.info(
                    f"Filtered out: {skipped_self} self-replies, "
                    f"{skipped_conversation} duplicate conversations"
                )

            if not filtered_emails:
                logger.info("No new emails to process after filtering")
                await context.emit_event(
                    process_event=self.OutputEvents.NoNewEmails.value,
                    data=input_data
                )
                return

            # Check mass email threshold
            threshold = config.mass_email_threshold
            if len(filtered_emails) > threshold:
                logger.warning(
                    f"Mass email detected: {len(filtered_emails)} emails exceeds threshold of {threshold}"
                )
                await context.emit_event(
                    process_event=self.OutputEvents.MassEmailDetected.value,
                    data={
                        "email_count": len(filtered_emails),
                        "threshold": threshold,
                        "sample_subjects": [e.get("subject", "")[:50] for e in filtered_emails[:5]],
                        **input_data
                    }
                )
                return

            # Sort emails chronologically (oldest first) to ensure original emails
            # are processed before their replies. This is critical for clarification
            # reply detection to work correctly.
            filtered_emails.sort(key=lambda e: e.get('received_datetime', ''))

            logger.info(f"Processing {len(filtered_emails)} emails")

            await context.emit_event(
                process_event=self.OutputEvents.EmailsFetched.value,
                data={"new_emails": filtered_emails, **input_data}
            )

        except Exception as e:
            logger.error(f"Error fetching emails: {e}", exc_info=True)
            await context.emit_event(
                process_event=self.OutputEvents.NoNewEmails.value,
                data={"error": str(e), **input_data}
            )


@kernel_process_step_metadata("ClassifyEmailsStep.V2")
class ClassifyEmailsStep(KernelProcessStep[ClassifyStepState]):
    """Process step to classify emails using LLM."""

    state: ClassifyStepState = Field(default_factory=ClassifyStepState)

    async def activate(self, state: KernelProcessStepState) -> None:
        """Initialize step state."""
        if state and hasattr(state, 'state'):
            self.state = state.state
        else:
            self.state = ClassifyStepState()

    class OutputEvents(Enum):
        EmailsClassified = "EmailsClassified"
        ClassificationError = "ClassificationError"

    @kernel_function(name="classify")
    async def classify(
        self,
        context: KernelProcessStepContext,
        input_data: Dict[str, Any]
    ) -> None:
        """Classify each email using LLM classification plugin."""
        try:
            new_emails = input_data.get("new_emails", [])
            state_manager = input_data.get("state_manager")
            config = input_data.get("config")
            kernel = input_data.get("kernel")

            # Get classification plugin from kernel
            classification_plugin = kernel.get_plugin("classification")

            classified_emails = []
            emails_with_replies = {}

            for email in new_emails:
                # Check if this is a reply to a clarification request
                conversation_id = email.get('conversation_id')
                is_clarification_reply = False

                if conversation_id:
                    # Check if any record in this conversation is awaiting clarification
                    records = state_manager.read_state()
                    for record in records:
                        if (record.conversation_id == conversation_id and
                            record.status == EmailStatus.AWAITING_CLARIFICATION):
                            # This is a reply to a clarification request
                            is_clarification_reply = True
                            logger.info(
                                f"Detected clarification reply:\n"
                                f"  ID: {email['email_id']}\n"
                                f"  Original request: {record.email_id}\n"
                                f"  Skipping classification, routing to clarification handler"
                            )
                            # Mark as clarification reply (will be handled specially)
                            classification = {
                                'classification': 'clarification_reply',
                                'confidence': 100,
                                'reason': f'Reply to clarification request for {record.email_id}',
                                'original_email_id': record.email_id
                            }
                            break

                if not is_clarification_reply:
                    logger.info(
                        f"Classifying email:\n"
                        f"  ID: {email['email_id']}\n"
                        f"  Subject: {email['subject'][:50]}...\n"
                        f"  From: {email['sender']}"
                    )

                    # Classify the email using kernel.invoke_prompt with proper settings
                    from src.utils.execution_settings import CLASSIFICATION_SETTINGS
                    from src.models.llm_outputs import EmailClassification

                    prompt = f"""Classify this email for SRM help desk processing:

Subject: {email['subject']}
From: {email['sender']}
Body: {email['body'][:1000]}

Determine if this is:
- help: An SRM-related request we can handle
- dont_help: Out of scope (not SRM-related)
- escalate: Requires human intervention

Provide classification, confidence (0-100), and reasoning in JSON format:
{{"classification": "help|dont_help|escalate", "confidence": 0-100, "reason": "explanation"}}"""

                    result = await kernel.invoke_prompt(
                        prompt=prompt,
                        settings=CLASSIFICATION_SETTINGS
                    )

                    # Parse to structured model with error handling
                    try:
                        classification_obj = EmailClassification.model_validate_json(str(result))
                        classification = {
                            "classification": classification_obj.classification,
                            "confidence": classification_obj.confidence,
                            "reason": classification_obj.reason
                        }
                    except Exception as e:
                        logger.error(f"Failed to parse classification for {email['email_id']}: {e}")
                        # Fallback to escalate on parsing failure
                        classification = {
                            "classification": "escalate",
                            "confidence": 0,
                            "reason": f"Classification parsing failed: {e}"
                        }

                    # Validate confidence threshold
                    if classification['confidence'] < config.confidence_threshold_for_classification:
                        logger.warning(
                            f"Low confidence ({classification['confidence']}%) for {email['email_id']}, escalating"
                        )
                        classification['classification'] = "escalate"
                        classification['reason'] = f"Low confidence ({classification['confidence']}%): {classification['reason']}"

                # Log classification result with emoji indicator
                if classification['classification'] == 'clarification_reply':
                    original_email_id = classification.get('original_email_id')
                    logger.info(
                        f"Clarification reply detected - mapping to original request\n"
                        f"  Reply ID: {email['email_id']}\n"
                        f"  Original request: {original_email_id}"
                    )
                    # Collect reply for targeted processing
                    emails_with_replies[original_email_id] = {
                        'reply_email_id': email['email_id'],
                        'reply_body': email.get('body'),
                        'reply_from': email.get('sender'),
                        'reply_received': email.get('received_datetime')
                    }
                    # Skip creating a new record for the reply itself
                    continue
                else:
                    indicator = "✓" if classification['classification'] == "help" else "⚠" if classification['classification'] == "escalate" else "✗"
                    logger.info(
                        f"{indicator} Email classification result:\n"
                        f"  ID: {email['email_id']}\n"
                        f"  Classification: {classification['classification']}\n"
                        f"  Confidence: {classification['confidence']}%\n"
                        f"  Reason: {classification['reason'][:100]}..."
                    )

                    # Create email record
                    record = EmailRecord(
                        email_id=email["email_id"],
                        sender=email["sender"],
                        subject=email["subject"],
                        body=email["body"],
                        received_datetime=email["received_datetime"],
                        conversation_id=email.get("conversation_id"),
                        classification=classification["classification"],
                        confidence=classification["confidence"],
                        reason=classification["reason"],
                        status=EmailStatus.CLASSIFIED
                    )

                    # Add to state
                    state_manager.append_record(record)
                    classified_emails.append(record.to_dict())

            self.state.classified_count = len(classified_emails)
            self.state.classifications = classified_emails

            logger.info(f"Detected {len(emails_with_replies)} emails with new clarification replies")

            await context.emit_event(
                process_event=self.OutputEvents.EmailsClassified.value,
                data={
                    "classified_emails": classified_emails,
                    "emails_with_replies": emails_with_replies,
                    **input_data
                }
            )

        except Exception as e:
            logger.error(f"Error classifying emails: {e}", exc_info=True)
            await context.emit_event(
                process_event=self.OutputEvents.ClassificationError.value,
                data={"error": str(e), **input_data}
            )


@kernel_process_step_metadata("RouteEmailsStep.V2")
class RouteEmailsStep(KernelProcessStep[RouteStepState]):
    """Process step to route emails based on classification."""

    state: RouteStepState = Field(default_factory=RouteStepState)

    async def activate(self, state: KernelProcessStepState) -> None:
        """Initialize step state."""
        if state and hasattr(state, 'state'):
            self.state = state.state
        else:
            self.state = RouteStepState()

    class OutputEvents(Enum):
        HelpEmails = "HelpEmails"
        DontHelpEmails = "DontHelpEmails"
        EscalateEmails = "EscalateEmails"
        RoutingComplete = "RoutingComplete"

    @kernel_function(name="route")
    async def route(
        self,
        context: KernelProcessStepContext,
        input_data: Dict[str, Any]
    ) -> None:
        """Route emails to appropriate handlers based on classification."""
        try:
            classified_emails = input_data.get("classified_emails", [])
            state_manager = input_data.get("state_manager")

            help_emails = []
            dont_help_emails = []
            escalate_emails = []

            for email in classified_emails:
                classification = email["classification"]
                email_id = email["email_id"]

                logger.info(f"Routing email {email_id} as '{classification}'")

                if classification == "help":
                    state_manager.update_record(email_id, {'status': EmailStatus.ROUTED_TO_SRM_HELP})
                    help_emails.append(email)
                elif classification == "dont_help":
                    state_manager.update_record(email_id, {'status': EmailStatus.RESPONDING_DONT_HELP})
                    dont_help_emails.append(email)
                elif classification == "escalate":
                    state_manager.update_record(email_id, {'status': EmailStatus.ESCALATING})
                    escalate_emails.append(email)

            self.state.help_count = len(help_emails)
            self.state.dont_help_count = len(dont_help_emails)
            self.state.escalate_count = len(escalate_emails)

            # Emit events for each category
            # Only include awaiting_clarification records that have new replies
            awaiting_clarification_all = input_data.get("awaiting_clarification_records", [])
            emails_with_replies = input_data.get("emails_with_replies", {})

            # Filter to only those with new replies
            awaiting_with_replies = [
                record for record in awaiting_clarification_all
                if record.get("email_id") in emails_with_replies
            ]

            # Also filter in_progress records to only those with new replies
            in_progress_all = input_data.get("in_progress_records", [])
            in_progress_with_replies = [
                record for record in in_progress_all
                if record.get("email_id") in emails_with_replies
            ]

            should_emit_help = len(help_emails) > 0 or len(awaiting_with_replies) > 0 or len(in_progress_with_replies) > 0

            if should_emit_help:
                if awaiting_with_replies:
                    logger.info(
                        f"Including {len(awaiting_with_replies)} emails with new clarification replies"
                    )
                if in_progress_with_replies:
                    logger.info(
                        f"Including {len(in_progress_with_replies)} in-progress emails with new replies"
                    )
                await context.emit_event(
                    process_event=self.OutputEvents.HelpEmails.value,
                    data={
                        "emails": help_emails,
                        "awaiting_clarification_records": awaiting_with_replies,
                        "in_progress_records": in_progress_with_replies,
                        "emails_with_replies": emails_with_replies,
                        **input_data
                    }
                )

            if dont_help_emails:
                await context.emit_event(
                    process_event=self.OutputEvents.DontHelpEmails.value,
                    data={"emails": dont_help_emails, **input_data}
                )

            if escalate_emails:
                await context.emit_event(
                    process_event=self.OutputEvents.EscalateEmails.value,
                    data={"emails": escalate_emails, **input_data}
                )

            # Emit completion event
            await context.emit_event(
                process_event=self.OutputEvents.RoutingComplete.value,
                data=input_data
            )

        except Exception as e:
            logger.error(f"Error routing emails: {e}", exc_info=True)
            # Default to escalation for routing errors
            await context.emit_event(
                process_event=self.OutputEvents.EscalateEmails.value,
                data={"emails": classified_emails, "error": str(e), **input_data}
            )


@kernel_process_step_metadata("ProcessHelpEmailsStep.V2")
class ProcessHelpEmailsStep(KernelProcessStep):
    """Process step to handle SRM help requests."""

    class OutputEvents(Enum):
        HelpProcessed = "HelpProcessed"

    @kernel_function(name="process_help")
    async def process_help(
        self,
        context: KernelProcessStepContext,
        input_data: Dict[str, Any]
    ) -> None:
        """Process SRM help requests using the SRM Help Process."""
        from semantic_kernel.processes.kernel_process import KernelProcessEvent
        from semantic_kernel.processes.local_runtime.local_kernel_process import start

        try:
            emails = input_data.get("emails", [])
            state_manager = input_data.get("state_manager")
            kernel = input_data.get("kernel")
            response_handler = input_data.get("response_handler")
            srm_help_process = input_data.get("srm_help_process")

            # Include only emails with new replies (already filtered by RouteEmailsStep)
            awaiting_clarification = input_data.get("awaiting_clarification_records", [])
            emails_with_replies = input_data.get("emails_with_replies", {})
            in_progress = input_data.get("in_progress_records", [])

            if awaiting_clarification:
                logger.info(
                    f"Processing {len(awaiting_clarification)} emails with new clarification replies: "
                    f"{list(emails_with_replies.keys())}"
                )
                emails.extend(awaiting_clarification)

            if in_progress:
                logger.info(f"Processing {len(in_progress)} in-progress emails for continuation")
                emails.extend(in_progress)

            # Deduplicate by email_id to avoid processing the same email multiple times
            seen_ids = set()
            deduplicated_emails = []
            for email in emails:
                email_id = email.get("email_id")
                if email_id not in seen_ids:
                    seen_ids.add(email_id)
                    deduplicated_emails.append(email)
                else:
                    logger.info(f"Skipping duplicate email {email_id}")

            emails = deduplicated_emails
            logger.info(f"Processing {len(emails)} SRM help requests (after deduplication)")

            for email in emails:
                email_id = email["email_id"]
                logger.info(f"Processing SRM help request for email {email_id}")

                # Start the SRM Help Process for this email
                async with await start(
                    process=srm_help_process,
                    kernel=kernel,
                    initial_event=KernelProcessEvent(
                        id="StartHelp",
                        data={
                            "email": email,
                            **input_data  # Pass all dependencies
                        }
                    ),
                    max_supersteps=50,
                ) as process_context:
                    # Process executes automatically
                    await process_context.get_state()

                # Check result and take appropriate action
                record = state_manager.find_record(email_id)
                if record:
                    if record.status == EmailStatus.COMPLETED_SUCCESS:
                        # Success - log and notify
                        if record.update_payload:
                            _log_srm_change(email_id, record.update_payload)
                            if response_handler:
                                await response_handler.send_success_notification(
                                    email_id=email_id,
                                    extracted_data=record.extracted_data or {},
                                    update_payload=record.update_payload
                                )

                        # Log detailed success info
                        srm_id = record.update_payload.get('document_id', 'N/A') if record.update_payload else 'N/A'
                        srm_name = record.update_payload.get('srm_name', 'N/A') if record.update_payload else 'N/A'
                        logger.info(
                            f"✓ SRM Help Process completed successfully:\n"
                            f"  Email: {email_id}\n"
                            f"  Subject: {record.subject[:50]}...\n"
                            f"  SRM Updated: {srm_id} - {srm_name}\n"
                            f"  Notification sent: {bool(response_handler)}"
                        )
                    elif record.status in [
                        EmailStatus.AWAITING_CLARIFICATION,
                        EmailStatus.IN_PROGRESS,
                        EmailStatus.DATA_EXTRACTED,
                        EmailStatus.UPDATE_PREPARED,
                        EmailStatus.AWAITING_RESPONSE,
                        EmailStatus.ROUTED_TO_SRM_HELP
                    ]:
                        # Check if escalation needed (max attempts OR user requested human help)
                        should_escalate = False
                        escalation_reason_log = ""

                        if record.last_error and 'user requested' in record.last_error.lower():
                            # User explicitly requested human help
                            should_escalate = True
                            escalation_reason_log = "User requested human representative"
                        elif record.clarification_attempts >= 2 and record.last_error:
                            # Max attempts reached
                            should_escalate = True
                            escalation_reason_log = "Max clarification attempts reached"

                        if should_escalate:
                            logger.warning(
                                f"{escalation_reason_log} for {email_id} - escalating"
                            )
                            state_manager.update_record(email_id, {'status': EmailStatus.ESCALATING})

                            if response_handler:
                                await response_handler.send_escalation(
                                    email_id=email_id,
                                    reason=record.last_error,
                                    subject=record.subject,
                                    srm_title=record.extracted_data.get('srm_title') if record.extracted_data else None,
                                    clarification_history=record.clarification_history,
                                    clarification_attempts=record.clarification_attempts
                                )
                        else:
                            # Still in progress - don't escalate, just log
                            logger.info(
                                f"Email {email_id} is {record.status.value}, will check again in next cycle"
                            )
                    else:
                        # Incomplete or failed - escalate with detailed reason
                        srm_title = None
                        if record.extracted_data:
                            srm_title = record.extracted_data.get('srm_title')

                        # Use last_error if available, otherwise use generic message
                        if record.last_error:
                            escalation_reason = record.last_error
                        else:
                            escalation_reason = f"Process ended with status: {record.status}"

                        # Log detailed failure info
                        logger.warning(
                            f"SRM Help Process failed for email {email_id}:\n"
                            f"  Subject: {record.subject[:50]}...\n"
                            f"  From: {record.sender}\n"
                            f"  Status: {record.status}\n"
                            f"  SRM Requested: {srm_title or 'Unknown'}\n"
                            f"  Failure Reason:\n"
                            f"    {escalation_reason}\n"
                            f"  Action: Escalating to support team"
                        )

                        state_manager.update_record(email_id, {'status': EmailStatus.ESCALATING})

                        if response_handler:
                            await response_handler.send_escalation(
                                email_id=email_id,
                                reason=escalation_reason,
                                subject=record.subject,
                                srm_title=srm_title,
                                clarification_history=record.clarification_history if record.clarification_history else None,
                                clarification_attempts=record.clarification_attempts if record.clarification_attempts else 0
                            )

            await context.emit_event(
                process_event=self.OutputEvents.HelpProcessed.value,
                data={"processed_count": len(emails), **input_data}
            )

        except Exception as e:
            logger.error(f"Error processing help emails: {e}", exc_info=True)
            await context.emit_event(
                process_event=self.OutputEvents.HelpProcessed.value,
                data={"processed_count": 0, "error": str(e), **input_data}
            )


@kernel_process_step_metadata("RespondDontHelpStep.V2")
class RespondDontHelpStep(KernelProcessStep):
    """Process step to send polite rejection emails."""

    class OutputEvents(Enum):
        ResponsesSent = "ResponsesSent"

    @kernel_function(name="respond")
    async def respond(
        self,
        context: KernelProcessStepContext,
        input_data: Dict[str, Any]
    ) -> None:
        """Send polite rejection emails for dont_help classification."""
        try:
            emails = input_data.get("emails", [])
            response_handler = input_data.get("response_handler")

            logger.info(f"Sending {len(emails)} rejection responses")

            if response_handler:
                for email in emails:
                    email_id = email["email_id"]
                    reason = email.get("reason", "")

                    await response_handler.send_rejection_response(
                        email_id=email_id,
                        reason=reason
                    )

            await context.emit_event(
                process_event=self.OutputEvents.ResponsesSent.value,
                data={"processed_count": len(emails), **input_data}
            )

        except Exception as e:
            logger.error(f"Error sending dont_help responses: {e}", exc_info=True)
            await context.emit_event(
                process_event=self.OutputEvents.ResponsesSent.value,
                data={"processed_count": 0, "error": str(e), **input_data}
            )


@kernel_process_step_metadata("EscalateEmailStep.V2")
class EscalateEmailStep(KernelProcessStep):
    """Process step to escalate emails to human support."""

    class OutputEvents(Enum):
        EmailsEscalated = "EmailsEscalated"

    @kernel_function(name="escalate")
    async def escalate(
        self,
        context: KernelProcessStepContext,
        input_data: Dict[str, Any]
    ) -> None:
        """Forward emails to human support team."""
        try:
            emails = input_data.get("emails", [])
            response_handler = input_data.get("response_handler")
            state_manager = input_data.get("state_manager")

            logger.info(f"Escalating {len(emails)} emails to support team")

            if response_handler:
                for email in emails:
                    email_id = email["email_id"]
                    reason = email.get("reason", "Automatic escalation")
                    subject = email.get("subject")

                    # Get record for clarification history if available
                    record = state_manager.find_record(email_id)
                    clarification_history = record.clarification_history if record and record.clarification_history else None
                    clarification_attempts = record.clarification_attempts if record else 0

                    await response_handler.send_escalation(
                        email_id=email_id,
                        reason=reason,
                        subject=subject,
                        clarification_history=clarification_history,
                        clarification_attempts=clarification_attempts
                    )

            await context.emit_event(
                process_event=self.OutputEvents.EmailsEscalated.value,
                data={"escalated_count": len(emails), **input_data}
            )

        except Exception as e:
            logger.error(f"Error escalating emails: {e}", exc_info=True)
            await context.emit_event(
                process_event=self.OutputEvents.EmailsEscalated.value,
                data={"escalated_count": 0, "error": str(e), **input_data}
            )


# ============================================================================
# PROCESS BUILDER
# ============================================================================

class EmailIntakeProcess:
    """
    Email Intake Process - processes incoming emails and routes them appropriately.

    Process Flow:
    1. InitializeStateStep: Load state and check for incomplete work
    2. FetchNewEmailsStep: Get unprocessed emails, filter, check mass email threshold
    3. ClassifyEmailsStep: Use LLM to classify emails (help/dont_help/escalate)
    4. RouteEmailsStep: Direct emails to appropriate handlers
    5. Handler steps: ProcessHelpEmailsStep, RespondDontHelpStep, EscalateEmailStep
    """

    class ProcessEvents(Enum):
        """Process-level events."""
        StartProcess = "StartProcess"
        ProcessComplete = "ProcessComplete"

    @staticmethod
    def create_process(process_name: str = "EmailIntakeProcess") -> ProcessBuilder:
        """
        Create the Email Intake process using SK framework.

        Args:
            process_name: Name for the process

        Returns:
            ProcessBuilder configured with all steps and transitions
        """
        process_builder = ProcessBuilder(process_name)

        # Add all steps
        initialize_step = process_builder.add_step(InitializeStateStep)
        fetch_step = process_builder.add_step(FetchNewEmailsStep)
        classify_step = process_builder.add_step(ClassifyEmailsStep)
        route_step = process_builder.add_step(RouteEmailsStep)
        process_help_step = process_builder.add_step(ProcessHelpEmailsStep)
        respond_step = process_builder.add_step(RespondDontHelpStep)
        escalate_step = process_builder.add_step(EscalateEmailStep)

        # Define process flow
        process_builder.on_input_event(
            EmailIntakeProcess.ProcessEvents.StartProcess.value
        ).send_event_to(initialize_step, parameter_name="input_data")

        initialize_step.on_event(
            InitializeStateStep.OutputEvents.StateLoaded.value
        ).send_event_to(fetch_step, parameter_name="input_data")

        # Handle errors and empty inbox
        initialize_step.on_event(
            InitializeStateStep.OutputEvents.StateError.value
        ).stop_process()

        fetch_step.on_event(
            FetchNewEmailsStep.OutputEvents.NoNewEmails.value
        ).stop_process()

        fetch_step.on_event(
            FetchNewEmailsStep.OutputEvents.MassEmailDetected.value
        ).stop_process()

        fetch_step.on_event(
            FetchNewEmailsStep.OutputEvents.EmailsFetched.value
        ).send_event_to(classify_step, parameter_name="input_data")

        classify_step.on_event(
            ClassifyEmailsStep.OutputEvents.EmailsClassified.value
        ).send_event_to(route_step, parameter_name="input_data")

        classify_step.on_event(
            ClassifyEmailsStep.OutputEvents.ClassificationError.value
        ).stop_process()

        # Route to appropriate handlers
        route_step.on_event(
            RouteEmailsStep.OutputEvents.HelpEmails.value
        ).send_event_to(process_help_step, parameter_name="input_data")

        route_step.on_event(
            RouteEmailsStep.OutputEvents.DontHelpEmails.value
        ).send_event_to(respond_step, parameter_name="input_data")

        route_step.on_event(
            RouteEmailsStep.OutputEvents.EscalateEmails.value
        ).send_event_to(escalate_step, parameter_name="input_data")

        route_step.on_event(
            RouteEmailsStep.OutputEvents.RoutingComplete.value
        ).stop_process()

        # Handler completion events
        process_help_step.on_event(
            ProcessHelpEmailsStep.OutputEvents.HelpProcessed.value
        ).stop_process()

        respond_step.on_event(
            RespondDontHelpStep.OutputEvents.ResponsesSent.value
        ).stop_process()

        escalate_step.on_event(
            EscalateEmailStep.OutputEvents.EmailsEscalated.value
        ).stop_process()

        return process_builder


def _log_srm_change(email_id: str, update_payload: Dict[str, Any]) -> None:
    """
    Log SRM change to action log.

    Args:
        email_id: Email ID
        update_payload: Update payload with change details
    """
    timestamp = datetime.now().isoformat()

    for field_name, new_value in update_payload.get('fields_to_update', {}).items():
        old_value = update_payload.get('old_values', {}).get(field_name, '') or ''
        new_value = new_value or ''

        # Safely truncate values
        old_value_str = str(old_value)[:50] if old_value else ''
        new_value_str = str(new_value)[:50] if new_value else ''

        log_entry = (
            f"{timestamp} | CHANGE | "
            f"SRM: {update_payload.get('document_id')} | "
            f"Changed by: {update_payload.get('changed_by')} | "
            f"Field: {field_name} | "
            f"Old: {old_value_str}... | "
            f"New: {new_value_str}... | "
            f"Reason: {update_payload.get('reason_for_change')}"
        )

        logger.info(log_entry)

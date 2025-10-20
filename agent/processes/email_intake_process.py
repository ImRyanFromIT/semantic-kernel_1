"""
Email Intake Process for the SRM Archivist Agent.

Implements the email intake workflow using SK Process Framework.
"""

from enum import Enum
from typing import Dict, Any
from datetime import datetime
from pydantic import Field
import json

from semantic_kernel import Kernel
from semantic_kernel.processes.process_builder import ProcessBuilder
from semantic_kernel.functions import kernel_function
from semantic_kernel.processes.kernel_process import (
    KernelProcessStep,
    KernelProcessStepContext,
    KernelProcessStepState,
)
from semantic_kernel.processes.kernel_process.kernel_process_step_metadata import kernel_process_step_metadata

from ..models.email_record import EmailRecord, EmailStatus
from ..utils.response_handler import ResponseHandler


class EmailIntakeProcess:
    """
    Email Intake Process - processes incoming emails and routes them appropriately.
    
    Process Flow:
    1. InitializeStateStep: Load state file and check for in-progress items
    2. ResumeInProgressStep: Handle any incomplete work from previous runs
    3. FetchNewEmailsStep: Get unprocessed emails from Microsoft Graph API
    4. MassEmailGuardrailStep: Prevent accidental mass responses
    5. ClassifyEmailsStep: Use LLM to classify emails (help/dont_help/escalate)
    6. RouteEmailsStep: Direct emails to appropriate handlers
    7. RespondDontHelpStep: Send polite rejection emails
    8. EscalateEmailStep: Forward emails to human support
    """
    
    class ProcessEvents(Enum):
        """Process-level events."""
        StartProcess = "StartProcess"
        ProcessComplete = "ProcessComplete"
        ProcessError = "ProcessError"
        MassEmailDetected = "MassEmailDetected"
    
    @staticmethod
    def create_process(process_name: str = "EmailIntakeProcess") -> ProcessBuilder:
        """
        Create the Email Intake process.
        
        Args:
            process_name: Name for the process
            
        Returns:
            ProcessBuilder configured with all steps and transitions
        """
        process_builder = ProcessBuilder(process_name)
        
        # Add all steps
        initialize_step = process_builder.add_step(InitializeStateStep)
        resume_step = process_builder.add_step(ResumeInProgressStep)
        fetch_step = process_builder.add_step(FetchNewEmailsStep)
        guardrail_step = process_builder.add_step(MassEmailGuardrailStep)
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
        ).send_event_to(resume_step, parameter_name="input_data")
        
        resume_step.on_event(
            ResumeInProgressStep.OutputEvents.ResumeComplete.value
        ).send_event_to(fetch_step, parameter_name="input_data")
        
        # Handle no new emails - just stop
        fetch_step.on_event(
            FetchNewEmailsStep.OutputEvents.NoNewEmails.value
        ).stop_process()
        
        fetch_step.on_event(
            FetchNewEmailsStep.OutputEvents.EmailsFetched.value
        ).send_event_to(guardrail_step, parameter_name="input_data")
        
        guardrail_step.on_event(
            MassEmailGuardrailStep.OutputEvents.EmailsApproved.value
        ).send_event_to(classify_step, parameter_name="input_data")
        
        guardrail_step.on_event(
            MassEmailGuardrailStep.OutputEvents.MassEmailDetected.value
        ).stop_process()
        
        classify_step.on_event(
            ClassifyEmailsStep.OutputEvents.EmailsClassified.value
        ).send_event_to(route_step, parameter_name="input_data")
        
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
        
        # Completion events
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


@kernel_process_step_metadata("InitializeStateStep.V1")
class InitializeStateStep(KernelProcessStep):
    """Process step to initialize agent state."""
    
    class InputEvents(Enum):
        Initialize = "Initialize"
    
    class OutputEvents(Enum):
        StateLoaded = "StateLoaded"
        StateError = "StateError"
    
    @kernel_function
    async def initialize_state(
        self, 
        context: KernelProcessStepContext,
        input_data: Dict[str, Any]
    ) -> None:
        """Load agent state file and prepare for processing."""
        try:
            # Get state manager from injected dependencies
            state_manager = input_data.get("state_manager")
            
            # Load existing state
            records = state_manager.read_state()
            
            # Pass dependencies forward
            await context.emit_event(
                process_event=self.OutputEvents.StateLoaded.value,
                data={
                    "records": [r.to_dict() for r in records],
                    **input_data  # Pass all dependencies forward
                }
            )
            
        except Exception as e:
            await context.emit_event(
                process_event=self.OutputEvents.StateError.value,
                data={"error": str(e), **input_data}
            )


@kernel_process_step_metadata("ResumeInProgressStep.V1") 
class ResumeInProgressStep(KernelProcessStep):
    """Process step to resume in-progress items."""
    
    class InputEvents(Enum):
        Resume = "Resume"
    
    class OutputEvents(Enum):
        ResumeComplete = "ResumeComplete"
    
    @kernel_function
    async def resume_in_progress(self, context: KernelProcessStepContext, input_data: Dict[str, Any]) -> None:
        """Handle any incomplete work from previous runs."""
        try:
            state_manager = input_data.get("state_manager")
            
            # Find in-progress records
            in_progress_records = state_manager.find_in_progress_records()
            
            # Check for stale items (24+ hours old)
            stale_records = state_manager.find_stale_records(24)
            
            # Escalate stale items
            for record in stale_records:
                if record.status in [EmailStatus.IN_PROGRESS, EmailStatus.AWAITING_RESPONSE]:
                    record.update_status(EmailStatus.ESCALATED, "Stale item - no response in 24 hours")
                    state_manager.update_record(record.email_id, {"status": record.status})
            
            await context.emit_event(
                process_event=self.OutputEvents.ResumeComplete.value,
                data={
                    "in_progress_count": len(in_progress_records),
                    "escalated_stale_count": len(stale_records),
                    **input_data  # Pass dependencies forward
                }
            )
            
        except Exception as e:
            await context.emit_event(
                process_event=self.OutputEvents.ResumeComplete.value,
                data={"error": str(e), **input_data}
            )


@kernel_process_step_metadata("FetchNewEmailsStep.V1")
class FetchNewEmailsStep(KernelProcessStep):
    """Process step to fetch new emails from Microsoft Graph API."""
    
    class InputEvents(Enum):
        FetchEmails = "FetchEmails"
    
    class OutputEvents(Enum):
        EmailsFetched = "EmailsFetched"
        NoNewEmails = "NoNewEmails"
        FetchError = "FetchError"
    
    @kernel_function
    async def fetch_new_emails(self, context: KernelProcessStepContext, input_data: Dict[str, Any]) -> None:
        """Fetch unprocessed emails from mailbox."""
        try:
            # Get dependencies
            state_manager = input_data.get("state_manager")
            graph_client = input_data.get("graph_client")
            config = input_data.get("config")
            logger = input_data.get("logger")
            
            logger.info("Checking for new emails...")
            
            # Get processed email IDs
            existing_records = state_manager.read_state()
            processed_ids = [record.email_id for record in existing_records]
            
            # Fetch new emails
            new_emails = await graph_client.fetch_emails_async(
                days_back=config.email_history_window_days,
                processed_email_ids=processed_ids
            )
            
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
                if conversation_id and state_manager.has_conversation(conversation_id):
                    skipped_conversation += 1
                    continue
                
                filtered_emails.append(email)
            
            # Log filtering summary
            if skipped_self > 0 or skipped_conversation > 0:
                logger.info(f"Filtered out: {skipped_self} self-replies, {skipped_conversation} duplicate conversations")
            
            if not filtered_emails:
                logger.info("No new emails to process after filtering")
                await context.emit_event(
                    process_event=self.OutputEvents.NoNewEmails.value,
                    data=input_data
                )
                return
            
            logger.info(f"Processing {len(filtered_emails)} emails")
            
            await context.emit_event(
                process_event=self.OutputEvents.EmailsFetched.value,
                data={"new_emails": filtered_emails, **input_data}
            )
            
        except Exception as e:
            logger = input_data.get("logger")
            if logger:
                logger.error(f"Error fetching emails: {e}")
            await context.emit_event(
                process_event=self.OutputEvents.FetchError.value,
                data={"error": str(e), **input_data}
            )


@kernel_process_step_metadata("MassEmailGuardrailStep.V1")
class MassEmailGuardrailStep(KernelProcessStep):
    """Process step to prevent accidental mass responses."""
    
    class InputEvents(Enum):
        CheckEmails = "CheckEmails"
    
    class OutputEvents(Enum):
        EmailsApproved = "EmailsApproved"
        MassEmailDetected = "MassEmailDetected"
    
    @kernel_function
    async def check_mass_email_guardrail(self, context: KernelProcessStepContext, input_data: Dict[str, Any]) -> None:
        """Check if email count exceeds mass email threshold."""
        try:
            new_emails = input_data.get("new_emails", [])
            config = input_data.get("config")
            logger = input_data.get("logger")
            
            threshold = config.mass_email_threshold
            
            if len(new_emails) > threshold:
                # Mass email detected - halt processing
                logger.warning(f"Mass email detected: {len(new_emails)} emails exceeds threshold of {threshold}")
                await context.emit_event(
                    process_event=self.OutputEvents.MassEmailDetected.value,
                    data={
                        "email_count": len(new_emails),
                        "threshold": threshold,
                        "sample_subjects": [email.get("subject", "")[:50] for email in new_emails[:5]],
                        **input_data
                    }
                )
            else:
                # Safe to proceed
                await context.emit_event(
                    process_event=self.OutputEvents.EmailsApproved.value,
                    data=input_data
                )
                
        except Exception as e:
            logger = input_data.get("logger")
            if logger:
                logger.error(f"Error in mass email guardrail: {e}")
            await context.emit_event(
                process_event=self.OutputEvents.MassEmailDetected.value,
                data={"error": str(e), **input_data}
            )


@kernel_process_step_metadata("ClassifyEmailsStep.V1")
class ClassifyEmailsStep(KernelProcessStep):
    """Process step to classify emails using LLM."""
    
    class InputEvents(Enum):
        ClassifyEmails = "ClassifyEmails"
    
    class OutputEvents(Enum):
        EmailsClassified = "EmailsClassified"
        ClassificationError = "ClassificationError"
    
    @kernel_function
    async def classify_emails(
        self, 
        context: KernelProcessStepContext, 
        input_data: Dict[str, Any],
        kernel: Kernel
    ) -> None:
        """Classify each email using LLM plugin."""
        try:
            new_emails = input_data.get("new_emails", [])
            state_manager = input_data.get("state_manager")
            config = input_data.get("config")
            logger = input_data.get("logger")
            
            # Get classification plugin from kernel
            classification_plugin = kernel.get_plugin("classification")
            
            classified_emails = []
            
            for email in new_emails:
                logger.info(f"Classifying email: {email['subject']} from {email['sender']}")
                
                # Classify the email
                classification_result = await classification_plugin["classify_email"].invoke(
                    kernel=kernel,
                    subject=email["subject"],
                    sender=email["sender"], 
                    body=email["body"]
                )
                
                classification = json.loads(str(classification_result))
                
                # Validate confidence threshold
                validated_result = await classification_plugin["validate_classification"].invoke(
                    kernel=kernel,
                    classification_result=json.dumps(classification),
                    confidence_threshold=config.confidence_threshold_for_classification
                )
                
                classification = json.loads(str(validated_result))
                
                logger.info(f"Email classified as: {classification['classification']} (confidence: {classification['confidence']}%)")
                logger.info(f"Reason: {classification['reason']}")
                
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
            
            await context.emit_event(
                process_event=self.OutputEvents.EmailsClassified.value,
                data={"classified_emails": classified_emails, **input_data}
            )
            
        except Exception as e:
            logger = input_data.get("logger")
            if logger:
                logger.error(f"Error classifying emails: {e}")
            await context.emit_event(
                process_event=self.OutputEvents.ClassificationError.value,
                data={"error": str(e), **input_data}
            )


@kernel_process_step_metadata("RouteEmailsStep.V1")
class RouteEmailsStep(KernelProcessStep):
    """Process step to route emails based on classification."""
    
    class InputEvents(Enum):
        RouteEmails = "RouteEmails"
    
    class OutputEvents(Enum):
        HelpEmails = "HelpEmails"
        DontHelpEmails = "DontHelpEmails"
        EscalateEmails = "EscalateEmails"
    
    @kernel_function
    async def route_emails(self, context: KernelProcessStepContext, input_data: Dict[str, Any]) -> None:
        """Route emails to appropriate handlers based on classification."""
        try:
            classified_emails = input_data.get("classified_emails", [])
            state_manager = input_data.get("state_manager")
            logger = input_data.get("logger")
            
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
            
            # Emit events for each category (only if non-empty)
            if help_emails:
                await context.emit_event(
                    process_event=self.OutputEvents.HelpEmails.value,
                    data={"emails": help_emails, **input_data}
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
                
        except Exception as e:
            logger = input_data.get("logger")
            if logger:
                logger.error(f"Error routing emails: {e}")
            # Default to escalation for routing errors
            await context.emit_event(
                process_event=self.OutputEvents.EscalateEmails.value,
                data={"emails": classified_emails, "error": str(e), **input_data}
            )


@kernel_process_step_metadata("RespondDontHelpStep.V1")
class RespondDontHelpStep(KernelProcessStep):
    """Process step to send polite rejection emails."""
    
    class InputEvents(Enum):
        RespondDontHelp = "RespondDontHelp"
    
    class OutputEvents(Enum):
        ResponsesSent = "ResponsesSent"
    
    @kernel_function
    async def respond_dont_help(self, context: KernelProcessStepContext, input_data: Dict[str, Any]) -> None:
        """Send polite rejection emails for dont_help classification."""
        try:
            emails = input_data.get("emails", [])
            response_handler = input_data.get("response_handler")
            logger = input_data.get("logger")
            
            for email in emails:
                email_id = email["email_id"]
                reason = email.get("reason", "")
                
                logger.info(f"Sending rejection response for email {email_id}")
                
                # Send rejection response
                await response_handler.send_rejection_response(
                    email_id=email_id,
                    reason=reason
                )
            
            await context.emit_event(
                process_event=self.OutputEvents.ResponsesSent.value,
                data={"processed_count": len(emails), **input_data}
            )
            
        except Exception as e:
            logger = input_data.get("logger")
            if logger:
                logger.error(f"Error sending dont_help responses: {e}")
            await context.emit_event(
                process_event=self.OutputEvents.ResponsesSent.value,
                data={"processed_count": 0, "error": str(e), **input_data}
            )


@kernel_process_step_metadata("EscalateEmailStep.V1")
class EscalateEmailStep(KernelProcessStep):
    """Process step to escalate emails to human support."""
    
    class InputEvents(Enum):
        EscalateEmails = "EscalateEmails"
    
    class OutputEvents(Enum):
        EmailsEscalated = "EmailsEscalated"
    
    @kernel_function
    async def escalate_emails(self, context: KernelProcessStepContext, input_data: Dict[str, Any]) -> None:
        """Forward emails to human support team."""
        try:
            emails = input_data.get("emails", [])
            response_handler = input_data.get("response_handler")
            logger = input_data.get("logger")
            
            for email in emails:
                email_id = email["email_id"]
                reason = email.get("reason", "Automatic escalation")
                subject = email.get("subject")
                
                logger.info(f"Escalating email {email_id} to support team")
                
                # Send escalation
                await response_handler.send_escalation(
                    email_id=email_id,
                    reason=reason,
                    subject=subject
                )
            
            await context.emit_event(
                process_event=self.OutputEvents.EmailsEscalated.value,
                data={"escalated_count": len(emails), **input_data}
            )
            
        except Exception as e:
            logger = input_data.get("logger")
            if logger:
                logger.error(f"Error escalating emails: {e}")
            await context.emit_event(
                process_event=self.OutputEvents.EmailsEscalated.value,
                data={"escalated_count": 0, "error": str(e), **input_data}
            )


@kernel_process_step_metadata("ProcessHelpEmailsStep.V1")
class ProcessHelpEmailsStep(KernelProcessStep):
    """Process step to handle SRM help requests."""
    
    class InputEvents(Enum):
        ProcessHelp = "ProcessHelp"
    
    class OutputEvents(Enum):
        HelpProcessed = "HelpProcessed"
    
    @kernel_function
    async def process_help_emails(
        self, 
        context: KernelProcessStepContext, 
        input_data: Dict[str, Any],
        kernel: Kernel
    ) -> None:
        """Process SRM help requests using the SRM Help Process."""
        from semantic_kernel.processes.kernel_process import KernelProcessEvent
        from semantic_kernel.processes.local_runtime.local_kernel_process import start
        
        try:
            emails = input_data.get("emails", [])
            state_manager = input_data.get("state_manager")
            search_plugin = kernel.get_plugin("search")
            logger = input_data.get("logger")
            response_handler = input_data.get("response_handler")
            srm_help_process = input_data.get("srm_help_process")
            
            for email in emails:
                email_id = email["email_id"]
                logger.info(f"Processing SRM help request for email {email_id}")
                
                # Start the SRM Help Process for this email
                async with await start(
                    process=srm_help_process,
                    kernel=kernel,
                    initial_event=KernelProcessEvent(
                        id="Start",
                        data={
                            "email": email,
                            "kernel": kernel,
                            "state_manager": state_manager,
                            "search_plugin": search_plugin
                        }
                    ),
                    max_supersteps=50,
                ) as process_context:
                    # Process executes automatically
                    final_state = await process_context.get_state()
                
                # Check result and take appropriate action
                record = state_manager.find_record(email_id)
                if record:
                    from ..models.email_record import EmailStatus
                    
                    if record.status == EmailStatus.COMPLETED_SUCCESS:
                        # Success - log change and notify user
                        if record.update_payload:
                            _log_srm_change(logger, email_id, record.update_payload)
                            await response_handler.send_success_notification(
                                email_id=email_id,
                                extracted_data=record.extracted_data or {},
                                update_payload=record.update_payload
                            )
                        logger.info(f"SRM Help Process completed successfully for email {email_id}")
                    
                    elif record.status == EmailStatus.DATA_EXTRACTED:
                        # Process stopped after extraction - likely SRM not found or search failed
                        logger.warning(f"SRM Help Process incomplete for email {email_id} - escalating")
                        state_manager.update_record(email_id, {'status': EmailStatus.ESCALATING})
                        
                        # Extract SRM title if available
                        srm_title = None
                        if record.extracted_data:
                            srm_title = record.extracted_data.get('srm_title')
                        
                        await response_handler.send_escalation(
                            email_id=email_id,
                            reason="Unable to complete SRM update - SRM may not exist or match confidence too low",
                            subject=record.subject,
                            srm_title=srm_title
                        )
                    
                    else:
                        # Any other status - escalate for safety
                        logger.warning(f"SRM Help Process ended with unexpected status {record.status} for email {email_id} - escalating")
                        state_manager.update_record(email_id, {'status': EmailStatus.ESCALATING})
                        
                        # Extract SRM title if available
                        srm_title = None
                        if record.extracted_data:
                            srm_title = record.extracted_data.get('srm_title')
                        
                        await response_handler.send_escalation(
                            email_id=email_id,
                            reason=f"Process ended with status: {record.status}",
                            subject=record.subject,
                            srm_title=srm_title
                        )
            
            await context.emit_event(
                process_event=self.OutputEvents.HelpProcessed.value,
                data={"processed_count": len(emails), **input_data}
            )
            
        except Exception as e:
            logger = input_data.get("logger")
            if logger:
                logger.error(f"Error processing help emails: {e}")
            await context.emit_event(
                process_event=self.OutputEvents.HelpProcessed.value,
                data={"processed_count": 0, "error": str(e), **input_data}
            )


def _log_srm_change(logger, email_id: str, update_payload: Dict[str, Any]) -> None:
    """
    Log SRM change to action log.
    
    Args:
        logger: Logger instance
        email_id: Email ID
        update_payload: Update payload with change details
    """
    timestamp = datetime.now().isoformat()
    
    for field_name, new_value in update_payload['fields_to_update'].items():
        old_value = update_payload['old_values'].get(field_name, '') or ''
        new_value = new_value or ''
        
        # Safely truncate values (handle None)
        old_value_str = str(old_value)[:50] if old_value else ''
        new_value_str = str(new_value)[:50] if new_value else ''
        
        log_entry = (
            f"{timestamp} | CHANGE | "
            f"SRM: {update_payload['document_id']} | "
            f"Changed by: {update_payload['changed_by']} | "
            f"Field: {field_name} | "
            f"Old: {old_value_str}... | "
            f"New: {new_value_str}... | "
            f"Reason: {update_payload['reason_for_change']}"
        )
        
        logger.info(log_entry)

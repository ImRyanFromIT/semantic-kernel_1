"""
SRM Help Process for the SRM Archivist Agent.

Implements the SRM update workflow using SK Process Framework with proper state management.
"""

from typing import Dict, Any
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

from src.models.email_record import EmailStatus
from src.utils.srm_matcher import SrmMatcher


logger = logging.getLogger(__name__)


# ============================================================================
# CLARIFICATION STEP (Agent-powered multi-turn)
# ============================================================================

@kernel_process_step_metadata("ClarificationStep.V1")
class ClarificationStep(KernelProcessStep):
    """
    Process step that delegates to agent for intelligent clarification conversation.

    Agent uses tools to:
    - Send clarification questions
    - Check for replies
    - Merge replies with original context
    - Decide when to give up (max 2 attempts)
    """

    class OutputEvents:
        ClarificationSuccess: str = "ClarificationSuccess"  # Got what we need
        ClarificationFailed: str = "ClarificationFailed"    # Max attempts or timeout

    @kernel_function(name="handle_clarification")
    async def handle_clarification(
        self,
        context: KernelProcessStepContext,
        data: Dict[str, Any]
    ) -> None:
        """Delegate clarification conversation to agent."""
        email = data['email']
        issue_type = data.get('reason', 'unknown')  # 'incomplete_data', 'conflicts_detected', etc.
        issue_details = data.get('validation', {}) or data.get('conflicts', {})
        kernel = data['kernel']
        state_manager = data['state_manager']

        email_id = email.get('email_id')

        # Check if this email is already awaiting clarification (resumption)
        record = state_manager.find_record(email_id)
        if record and record.status == EmailStatus.AWAITING_CLARIFICATION:
            logger.info(f"Checking for clarification reply on {email_id}")
            # This is a resumption - check for reply
            context_info = "The clarification email has already been sent. Check for a reply."
        else:
            logger.info(f"Starting clarification for email {email_id}: {issue_type}")
            # Build context for agent (first time)
            context_info = self._build_context(email, issue_type, issue_details, data)

        # Create clarification agent
        agent, execution_settings = self._create_clarification_agent(kernel, data)

        # Agent handles conversation (may take multiple cycles)
        result = await self._run_clarification_agent(agent, execution_settings, context_info, email_id, state_manager)

        # Process result
        if result['success']:
            logger.info(f"✓ Clarification successful for {email_id}")

            # Reload email with merged context
            record = state_manager.find_record(email_id)
            updated_email = {**email, 'body': record.body}

            await context.emit_event(
                process_event=self.OutputEvents.ClarificationSuccess,
                data={**data, 'email': updated_email}
            )
        else:
            reason = result.get('reason', 'unknown')

            # If waiting for reply, don't fail - just log and exit
            # Email stays in AWAITING_CLARIFICATION status for next cycle
            if reason == 'waiting_for_reply':
                logger.info(f"⏳ Waiting for clarification reply on {email_id}")
                # Don't emit any event - process ends, email stays in awaiting state
                # Next cycle will check for reply again
                return

            # Only fail if max attempts reached, error, or user requested escalation
            logger.warning(f"✗ Clarification failed for {email_id}: {reason}")

            # Update last_error with clarification failure
            record = state_manager.find_record(email_id)

            # Check if user requested human escalation
            if 'user_requested_human_escalation' in reason.lower() or ('user requested' in reason.lower() and 'escalation' in reason.lower()):
                failure_msg = f"User requested to speak with a human representative after {record.clarification_attempts} clarification attempt(s)"
            else:
                failure_msg = f"Clarification failed after {record.clarification_attempts} attempts: {reason}"

            state_manager.update_record(email_id, {'last_error': failure_msg})

            await context.emit_event(
                process_event=self.OutputEvents.ClarificationFailed,
                data={**data, 'failure_reason': reason}
            )

    def _build_context(self, email: Dict, issue_type: str, issue_details: Dict, data: Dict) -> str:
        """Build context string for agent."""
        if issue_type == 'conflicts_detected':
            conflicts_list = issue_details.get('conflicts', [])
            return f"""SITUATION: User request contains conflicts/contradictions

EMAIL DETAILS:
- From: {email.get('sender')}
- Subject: {email.get('subject')}
- Body: {email.get('body')[:500]}...

CONFLICTS DETECTED:
{issue_details.get('conflict_details', 'Unknown conflict')}

SPECIFIC ISSUES TO CLARIFY:
{chr(10).join(f'{i+1}. {c}' for i, c in enumerate(conflicts_list))}

YOUR TASK: Send ONE email listing ALL these unclear points and asking the user to clarify each one."""

        else:  # incomplete_data
            missing = issue_details.get('missing_fields', [])
            extracted = data.get('extracted_data', {})

            return f"""SITUATION: Missing required information for SRM update

EMAIL DETAILS:
- From: {email.get('sender')}
- Subject: {email.get('subject')}
- Body: {email.get('body')[:500]}...

MISSING FIELDS: {', '.join(missing)}

EXTRACTED SO FAR:
{json.dumps(extracted, indent=2)}

YOUR TASK: Send ONE email listing ALL missing fields and asking the user to provide them."""

    def _create_clarification_agent(self, kernel: Kernel, data: Dict):
        """Create agent with clarification tools and instructions."""
        from semantic_kernel.agents import ChatCompletionAgent
        from semantic_kernel.connectors.ai.open_ai import AzureChatPromptExecutionSettings
        from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior

        # Clarification plugin already registered at startup in run_email_agent.py
        # Plugin name: "clarification"

        # Create agent
        agent = ChatCompletionAgent(
            kernel=kernel,
            name="ClarificationDetective",
            instructions="""You are helping clarify unclear or conflicting SRM update requests.

YOUR TOOLS:
- send_clarification_email: Send clarification questions to user via email
- check_for_reply: Check if they replied
- check_for_human_escalation_request: Check if reply requests human help (CALL THIS FIRST!)
- merge_reply_with_original: Merge reply into context
- record_unsatisfactory_reply: Mark reply as insufficient (increments attempt counter)
- get_clarification_attempts: Check attempt count

YOUR PROCESS:
1. Review the specific issues that need clarification (you'll be given a numbered list)
2. Check attempts with get_clarification_attempts
3. If attempts < 2: Draft ONE email that:
   - Thanks them for their request
   - Lists ALL the unclear points (number them)
   - Asks them to clarify each point
   - Includes the note about requesting human help
4. send_clarification_email with your drafted message
5. check_for_reply to see if they replied (may not have yet)
6. When reply arrives:
   a. FIRST call check_for_human_escalation_request with the reply_body
   b. If is_escalation_request is true: Report "FAILED: User requested human escalation" immediately
   c. If is_escalation_request is false: Continue to step 7
7. merge_reply_with_original
8. Evaluate: Is the information clear and complete now?
9. If clear now: Report "SUCCESS: We have enough information"
10. If still unclear:
   a. Call record_unsatisfactory_reply (this increments the attempt counter)
   b. Call get_clarification_attempts to check current count
   c. If attempts < 2: You MUST send another clarification email NOW - go to step 3 immediately
   d. If attempts >= 2: Report "FAILED: Max attempts reached"

EMAIL FORMAT:
Hello,

Thank you for submitting your SRM update request. This is an automated message from the SRM Archivist Agent, which processes SRM updates on behalf of the team.

I've reviewed your request and need clarification on the following points before I can proceed with the update:

1. [First unclear point - be specific]
2. [Second unclear point - be specific]
3. [etc...]

Please reply to this email with clarification on these items. Once I receive your response, I'll complete the SRM update automatically.

Note: If you're unable to provide this information or would prefer to work with a human representative, please reply with "connect me with a human" and your request will be escalated to the support team immediately.

Best regards,
SRM Archivist Agent
Automated SRM Management System

RULES:
- Max 2 clarification attempts total
- List ALL unclear points in ONE email (don't send multiple emails)
- Be specific about what's unclear
- Be professional but conversational
- After sending, check_for_reply may return false (means "not yet, wait for next cycle")
- CRITICAL: When you receive a reply, you MUST call check_for_human_escalation_request BEFORE doing anything else
- If check_for_human_escalation_request returns is_escalation_request: true, immediately report "FAILED: User requested human escalation" - do NOT merge, do NOT increment attempts, do NOT send another clarification
- Only proceed with merge_reply_with_original if is_escalation_request is false

EXAMPLE: Unsatisfactory Reply Flow
User replies: "I'm not sure"
1. check_for_human_escalation_request("I'm not sure") -> false, continue
2. merge_reply_with_original (merge it)
3. Evaluate: "I'm not sure" provides no clarification - still unclear
4. record_unsatisfactory_reply("Reply didn't provide clarification") -> attempts now 1/2
5. get_clarification_attempts -> attempts: 1, can_retry: true
6. Since attempts < 2, IMMEDIATELY draft and send_clarification_email with:
   "Thank you for your reply. I understand you're unsure about some details. Let me ask more specifically:
   1. [Rephrase first question more simply]
   2. [Rephrase second question with examples]
   ..."
7. After sending, report "SUCCESS: Second clarification email sent (attempt 2/2)"

EXAMPLE:
Issues: Conflicting process ownership, ambiguous contact info
You: get_clarification_attempts → {attempts: 0, can_retry: true}
You: send_clarification_email("Hello,\n\nThank you for submitting your SRM update request. This is an automated message from the SRM Archivist Agent, which processes SRM updates on behalf of the team.\n\nI've reviewed your request and need clarification on the following points before I can proceed with the update:\n\n1. Should requests go through Mike's team OR the old process? When does each apply?\n2. Should we contact platform-team@company.com OR John for urgent issues?\n\nPlease reply to this email with clarification on these items. Once I receive your response, I'll complete the SRM update automatically.\n\nNote: If you're unable to provide this information or would prefer to work with a human representative, please reply with 'connect me with a human' and your request will be escalated to the support team immediately.\n\nBest regards,\nSRM Archivist Agent\nAutomated SRM Management System")
You: check_for_reply → {has_reply: false}
You: "Waiting for user reply."

[Next cycle after user replies]
You: check_for_reply → {has_reply: true, reply_body: "idk"}
You: check_for_human_escalation_request(reply_body="idk") → {is_escalation_request: false}
You: merge_reply_with_original(reply_body="idk")
You: Evaluate: Still unclear, just says "idk"
You: record_unsatisfactory_reply(reason="User replied with 'idk', no useful information provided")
You: get_clarification_attempts → {attempts: 1, can_retry: true}
You: send_clarification_email with more specific questions
You: check_for_reply → {has_reply: false}
You: "Waiting for user reply."

[Next cycle after second reply, still unclear]
You: check_for_reply → {has_reply: true, reply_body: "still not sure"}
You: check_for_human_escalation_request(reply_body="still not sure") → {is_escalation_request: false}
You: merge_reply_with_original(reply_body="still not sure")
You: Evaluate: Still unclear
You: record_unsatisfactory_reply(reason="Second reply still unclear")
You: get_clarification_attempts → {attempts: 2, can_retry: false}
You: "FAILED: Max attempts reached"

EXAMPLE 2 - User requests human help:
You: get_clarification_attempts → {attempts: 0, can_retry: true}
You: send_clarification_email("Hello...\n\n1. Question 1\n2. Question 2\n\nNote: If you're unable to provide this information or would prefer to work with a human representative, please reply with 'connect me with a human'...")
You: check_for_reply → {has_reply: false}
You: "Waiting for user reply."

[Next cycle after user asks for human help]
You: check_for_reply → {has_reply: true, reply_body: "I'm not sure about this, can you connect me with a human representative?"}
You: check_for_human_escalation_request(reply_body="I'm not sure about this, can you connect me with a human representative?") → {is_escalation_request: true, detected_phrases: ["connect me with a human", "human representative"], message: "User requested human assistance"}
You: "FAILED: User requested human escalation"
[Do NOT call merge_reply_with_original, do NOT call record_unsatisfactory_reply, do NOT send another clarification - STOP HERE]

Respond with SUCCESS or FAILED when done. Otherwise indicate waiting.
"""
        )

        # Use centralized clarification settings
        from src.utils.execution_settings import CLARIFICATION_SETTINGS

        return agent, CLARIFICATION_SETTINGS

    async def _run_clarification_agent(self, agent, execution_settings, context_info: str, email_id: str, state_manager) -> Dict[str, Any]:
        """Run agent conversation until success/failure/waiting."""
        from semantic_kernel.contents import ChatHistory

        try:
            # Create chat history with context
            chat_history = ChatHistory()
            chat_history.add_user_message(f"""Please help clarify this SRM request.

{context_info}

Email ID: {email_id}

Start the clarification process. Use your tools to ask questions and check for replies.
Remember: Max 2 attempts, then escalate.""")

            # Invoke agent with auto function calling
            response_text = ""
            async for message in agent.invoke(chat_history, settings=execution_settings):
                content = str(message.content) if hasattr(message, 'content') else str(message)
                response_text += content

                # Log what agent is doing
                if hasattr(message, 'items'):
                    for item in message.items:
                        if hasattr(item, 'function_name'):
                            logger.info(f"  Agent calling: {item.function_name}")

            logger.info(f"Agent response: {response_text[:200]}...")

            # Parse agent's final response
            response_upper = response_text.upper()

            if "SUCCESS" in response_upper and "HAVE ENOUGH" in response_upper:
                return {'success': True}
            elif ("USER" in response_upper and "REQUESTED" in response_upper and "ESCALATION" in response_upper) or ("USER" in response_upper and "REQUESTED" in response_upper and "HUMAN" in response_upper):
                return {'success': False, 'reason': 'user_requested_human_escalation'}
            elif "FAILED" in response_upper or "MAX ATTEMPTS" in response_upper:
                return {'success': False, 'reason': 'max_attempts_or_still_unclear'}
            elif "WAITING" in response_upper or "NO REPLY YET" in response_upper:
                return {'success': False, 'reason': 'waiting_for_reply'}
            else:
                # Unclear response, check attempt count
                record = state_manager.find_record(email_id)
                if record and record.clarification_attempts >= 2:
                    return {'success': False, 'reason': 'max_attempts_reached'}
                else:
                    # Assume waiting
                    return {'success': False, 'reason': 'waiting_for_reply'}

        except Exception as e:
            logger.error(f"Error in clarification agent: {e}", exc_info=True)
            return {'success': False, 'reason': f'agent_error: {str(e)}'}


# ============================================================================
# EXTRACTION STEP STATE
# ============================================================================


# ============================================================================
# STEP STATE CLASSES
# ============================================================================

class ExtractStepState(KernelBaseModel):
    """State for extraction step."""
    email_id: str = Field(default="")
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    attempts: int = Field(default=0)


class SearchStepState(KernelBaseModel):
    """State for search step."""
    srm_title: str = Field(default="")
    matched_srm: Dict[str, Any] = Field(default_factory=dict)
    match_type: str = Field(default="")
    confidence: float = Field(default=0.0)


class UpdateStepState(KernelBaseModel):
    """State for update step."""
    document_id: str = Field(default="")
    update_payload: Dict[str, Any] = Field(default_factory=dict)
    update_result: str = Field(default="")


# ============================================================================
# PROCESS STEPS
# ============================================================================

@kernel_process_step_metadata("ExtractDataStep.V2")
class ExtractDataStep(KernelProcessStep[ExtractStepState]):
    """Extract structured data from email using LLM."""

    state: ExtractStepState = Field(default_factory=ExtractStepState)

    async def activate(self, process_state: KernelProcessStepState) -> None:
        """Initialize step state."""
        if process_state and hasattr(process_state, 'state'):
            self.state = process_state.state
        else:
            self.state = ExtractStepState()

    class OutputEvents:
        Success: str = "Success"
        Failed: str = "Failed"
        NeedsClarification: str = "NeedsClarification"

    @kernel_function(name="extract")
    async def extract(
        self,
        context: KernelProcessStepContext,
        data: Dict[str, Any],
    ):
        """Extract change request details from email."""
        try:
            # Extract inputs from event data
            email = data.get("email", {})
            state_manager = data.get("state_manager")
            kernel = data.get("kernel")

            # Update step state
            self.state.email_id = email.get("email_id", "")
            self.state.attempts += 1

            # Check if email is already awaiting clarification (resumption case)
            record = state_manager.find_record(self.state.email_id)
            if record and record.status == EmailStatus.AWAITING_CLARIFICATION:
                logger.info(f"Email {self.state.email_id} already awaiting clarification, checking for reply")
                # Skip extraction, go directly to clarification check
                await context.emit_event(
                    process_event=self.OutputEvents.NeedsClarification,
                    data={
                        "email": email,
                        "reason": "checking_for_reply",  # Special flag for resumption
                        **data
                    }
                )
                return

            logger.info(f"Extracting data from email {self.state.email_id}")

            # Get extraction plugin (will be used for both extraction and conflict detection)
            extraction_plugin = kernel.get_plugin("extraction")

            # Extract data
            result = await extraction_plugin["extract_change_request"].invoke(
                kernel=kernel,
                subject=email["subject"],
                sender=email["sender"],
                body=email["body"]
            )

            # Parse result
            extracted_data = json.loads(str(result))
            self.state.extracted_data = extracted_data

            logger.info(
                f"Extracted SRM title: {extracted_data.get('srm_title', 'N/A')}"
            )

            # Validate completeness
            validation_result = await extraction_plugin["validate_completeness"].invoke(
                kernel=kernel,
                extracted_data=json.dumps(extracted_data)
            )
            validation = json.loads(str(validation_result))

            # Update state manager
            state_manager.update_record(
                email["email_id"],
                {
                    "extracted_data": extracted_data,
                    "status": EmailStatus.DATA_EXTRACTED
                }
            )

            # Emit appropriate event
            if validation["is_complete"]:
                logger.info(
                    f"✓ Data extraction complete for email {self.state.email_id}:\n"
                    f"  SRM Title: {extracted_data.get('srm_title', 'N/A')}\n"
                    f"  Has owner_notes: {bool(extracted_data.get('new_owner_notes_content'))}\n"
                    f"  Has hidden_notes: {bool(extracted_data.get('recommendation_logic') or extracted_data.get('exclusion_criteria'))}\n"
                    f"  Reason: {extracted_data.get('reason_for_change', 'N/A')[:50]}..."
                )

                # Check for conflicts before proceeding
                logger.info(f"Checking for conflicts in email {self.state.email_id}...")

                try:
                    conflict_result = await extraction_plugin["detect_conflicts"].invoke(
                        kernel=kernel,
                        extracted_data=json.dumps(extracted_data),
                        email_subject=email.get("subject", ""),
                        email_body=email.get("body", ""),
                        sender=email.get("sender", "")
                    )

                    conflicts = json.loads(str(conflict_result))

                    if conflicts.get("has_conflicts", False) or not conflicts.get("safe_to_proceed", True):
                        # Conflicts detected - escalate
                        severity = conflicts.get("severity", "medium")
                        conflict_details = conflicts.get("conflict_details", "Unknown conflict detected")
                        conflict_list = conflicts.get("conflicts", [])

                        # Build detailed error message
                        error_msg = f"⚠ CONFLICTS DETECTED (severity: {severity})\n"
                        error_msg += f"{conflict_details}\n\n"
                        if conflict_list:
                            error_msg += "Specific issues:\n"
                            for i, conflict in enumerate(conflict_list, 1):
                                error_msg += f"  {i}. {conflict}\n"

                        logger.warning(
                            f"⚠ Conflicts detected in email {self.state.email_id}:\n"
                            f"  Severity: {severity}\n"
                            f"  Details: {conflict_details}\n"
                            f"  Issues: {', '.join(conflict_list[:3])}{'...' if len(conflict_list) > 3 else ''}\n"
                            f"  Action: Escalating for human review"
                        )

                        # Emit clarification needed event
                        logger.info(f"→ Requesting clarification for conflicts in {self.state.email_id}")
                        await context.emit_event(
                            process_event=self.OutputEvents.NeedsClarification,
                            data={
                                "email": email,
                                "extracted_data": extracted_data,
                                "conflicts": conflicts,
                                "reason": "conflicts_detected",
                                **data
                            }
                        )
                        return

                    else:
                        # No conflicts - safe to proceed
                        logger.info(f"✓ No conflicts detected for email {self.state.email_id}")

                except Exception as conflict_error:
                    # If conflict detection fails, log but don't block processing
                    # (fail-open approach for this safety check)
                    logger.error(
                        f"Error during conflict detection for email {self.state.email_id}: {conflict_error}",
                        exc_info=True
                    )
                    logger.warning("Proceeding despite conflict detection failure - review manually")

                # Proceed to search
                await context.emit_event(
                    process_event=self.OutputEvents.Success,
                    data={
                        "email": email,
                        "extracted_data": extracted_data,
                        **data  # Pass all dependencies forward
                    }
                )
            else:
                # Data incomplete - save detailed error
                missing_fields = validation.get('missing_fields', [])
                error_msg = (
                    f"Incomplete data extraction - missing required fields: {', '.join(missing_fields)}\n"
                    f"Extracted so far: {extracted_data}"
                )

                logger.warning(
                    f"✗ Incomplete data extraction for email {self.state.email_id}:\n"
                    f"  Missing: {', '.join(missing_fields)}\n"
                    f"  Extracted: srm_title={extracted_data.get('srm_title', 'N/A')}"
                )

                # Emit clarification needed event
                logger.info(f"→ Requesting clarification for incomplete data in {self.state.email_id}")
                await context.emit_event(
                    process_event=self.OutputEvents.NeedsClarification,
                    data={
                        "email": email,
                        "extracted_data": extracted_data,
                        "validation": validation,
                        "reason": "incomplete_data",
                        **data
                    }
                )

        except Exception as e:
            error_msg = f"Error extracting data from email: {str(e)}"
            logger.error(f"✗ {error_msg}", exc_info=True)

            # Save error to email record
            state_manager.update_record(
                email.get("email_id"),
                {
                    "last_error": error_msg,
                    "status": EmailStatus.IN_PROGRESS
                }
            )

            await context.emit_event(
                process_event=self.OutputEvents.Failed,
                data={"email": email, "error": str(e), "reason": "extraction_error", **data}
            )


@kernel_process_step_metadata("SearchSRMStep.V2")
class SearchSRMStep(KernelProcessStep[SearchStepState]):
    """Search for SRM using intelligent fuzzy matching."""

    state: SearchStepState = Field(default_factory=SearchStepState)

    async def activate(self, process_state: KernelProcessStepState) -> None:
        """Initialize step state."""
        if process_state and hasattr(process_state, 'state'):
            self.state = process_state.state
        else:
            self.state = SearchStepState()

    class OutputEvents:
        Found: str = "Found"
        NotFound: str = "NotFound"

    @kernel_function(name="search")
    async def search(
        self,
        context: KernelProcessStepContext,
        data: Dict[str, Any],
    ):
        """Search for SRM in index with intelligent matching."""
        try:
            # Extract inputs from event data
            email = data.get("email", {})
            extracted_data = data.get("extracted_data", {})
            state_manager = data.get("state_manager")
            kernel = data.get("kernel")

            srm_title = extracted_data.get("srm_title", "")
            if not srm_title:
                logger.warning(f"No SRM title provided for email {email.get('email_id')}")
                await context.emit_event(
                    process_event=self.OutputEvents.NotFound,
                    data={"email": email, "reason": "no_srm_title", **data}
                )
                return

            # Update step state
            self.state.srm_title = srm_title

            logger.info(f"Searching for SRM: {srm_title}")

            # Get search plugin
            search_plugin = kernel.get_plugin("search")

            # Search for SRM
            search_result = await search_plugin["search_srm"].invoke(
                kernel=kernel,
                query=srm_title,
                top_k=10
            )
            search_data = json.loads(str(search_result))

            # Log search results summary
            if search_data:
                top_3 = search_data[:3]
                candidates_str = "\n".join([
                    f"    - {r.get('Name', 'Unknown')} (SRM_ID: {r.get('SRM_ID', 'N/A')})"
                    for r in top_3
                ])
                logger.info(
                    f"Search returned {len(search_data)} candidates for '{srm_title}':\n{candidates_str}"
                )
            else:
                logger.warning(f"Search returned 0 candidates for '{srm_title}'")

            # Use intelligent matching
            matched_srm, match_type, confidence = SrmMatcher.find_best_match(
                srm_title,
                search_data,
                name_field="Name"
            )

            # Update step state
            self.state.match_type = match_type
            self.state.confidence = confidence
            if matched_srm:
                self.state.matched_srm = matched_srm

            # Generate match explanation for all cases
            match_explanation = SrmMatcher.get_match_explanation(
                match_type,
                srm_title,
                matched_srm.get("Name") if matched_srm else None,
                confidence,
                search_data,
                name_field="Name"
            )

            # Log match result with details
            logger.info(
                f"Match analysis for email {email.get('email_id')}:\n"
                f"  Requested: '{srm_title}'\n"
                f"  Type: {match_type}\n"
                f"  Confidence: {confidence:.1%}\n"
                f"  Matched: {matched_srm.get('Name') if matched_srm else 'None'}\n"
                f"  SRM_ID: {matched_srm.get('SRM_ID') if matched_srm else 'None'}"
            )

            # Check if we should proceed
            if SrmMatcher.should_proceed_with_update(match_type):
                # Safe to proceed
                logger.info(
                    f"✓ Match approved for update: {matched_srm.get('SRM_ID')} - {matched_srm.get('Name')}"
                )
                await context.emit_event(
                    process_event=self.OutputEvents.Found,
                    data={
                        "email": email,
                        "extracted_data": extracted_data,
                        "matched_srm": matched_srm,
                        "match_type": match_type,
                        "confidence": confidence,
                        **data
                    }
                )
            else:
                # Cannot proceed - save detailed error and escalate
                logger.warning(
                    f"✗ Match rejected for email {email.get('email_id')}:\n{match_explanation}"
                )

                # Save failure reason to email record for escalation
                state_manager.update_record(
                    email.get("email_id"),
                    {
                        "last_error": match_explanation,
                        "status": EmailStatus.SEARCH_ERROR
                    }
                )

                await context.emit_event(
                    process_event=self.OutputEvents.NotFound,
                    data={
                        "email": email,
                        "reason": "no_safe_match",
                        "match_type": match_type,
                        "match_explanation": match_explanation,
                        **data
                    }
                )

        except Exception as e:
            error_msg = f"Error searching for SRM '{srm_title}': {str(e)}"
            logger.error(error_msg, exc_info=True)

            # Save error to email record
            state_manager.update_record(
                email.get("email_id"),
                {
                    "last_error": error_msg,
                    "status": EmailStatus.SEARCH_ERROR
                }
            )

            await context.emit_event(
                process_event=self.OutputEvents.NotFound,
                data={"email": email, "error": str(e), "reason": "search_error", **data}
            )


@kernel_process_step_metadata("UpdateIndexStep.V2")
class UpdateIndexStep(KernelProcessStep[UpdateStepState]):
    """Update SRM document in Azure AI Search."""

    state: UpdateStepState = Field(default_factory=UpdateStepState)

    async def activate(self, process_state: KernelProcessStepState) -> None:
        """Initialize step state."""
        if process_state and hasattr(process_state, 'state'):
            self.state = process_state.state
        else:
            self.state = UpdateStepState()

    class OutputEvents:
        Success: str = "Success"
        Failed: str = "Failed"

    @kernel_function(name="update")
    async def update(
        self,
        context: KernelProcessStepContext,
        data: Dict[str, Any],
    ):
        """Update SRM document in Azure AI Search."""
        try:
            # Extract inputs from event data
            email = data.get("email", {})
            extracted_data = data.get("extracted_data", {})
            matched_srm = data.get("matched_srm", {})
            state_manager = data.get("state_manager")
            kernel = data.get("kernel")

            # Prepare update payload
            document_id = matched_srm.get('SRM_ID') or matched_srm.get('srm_id', '')
            srm_name = matched_srm.get('Name') or matched_srm.get('name', 'Unknown')

            logger.info(f"Updating SRM {document_id} ({srm_name})")

            update_payload = {
                'document_id': document_id,
                'srm_name': srm_name,
                'fields_to_update': {},
                'old_values': {},
                'new_values': {},
                'changed_by': email.get('sender', ''),
                'reason_for_change': extracted_data.get('reason_for_change', '')
            }

            # Handle owner notes update
            if extracted_data.get('new_owner_notes_content') is not None:
                update_payload['fields_to_update']['owner_notes'] = extracted_data['new_owner_notes_content']
                update_payload['old_values']['owner_notes'] = matched_srm.get('owner_notes') or ''
                update_payload['new_values']['owner_notes'] = extracted_data['new_owner_notes_content']

            # Handle hidden notes update
            if extracted_data.get('recommendation_logic') or extracted_data.get('exclusion_criteria'):
                hidden_notes = ""
                if extracted_data.get('recommendation_logic'):
                    hidden_notes += f"Recommendation Logic: {extracted_data['recommendation_logic']}\n"
                if extracted_data.get('exclusion_criteria'):
                    hidden_notes += f"Exclusion Criteria: {extracted_data['exclusion_criteria']}"
                update_payload['fields_to_update']['hidden_notes'] = hidden_notes.strip()
                update_payload['old_values']['hidden_notes'] = matched_srm.get('hidden_notes') or ''
                update_payload['new_values']['hidden_notes'] = hidden_notes.strip()

            # Update step state
            self.state.document_id = document_id
            self.state.update_payload = update_payload

            # Get search plugin
            search_plugin = kernel.get_plugin("search")

            # Apply update
            update_result = await search_plugin["update_srm_document"].invoke(
                kernel=kernel,
                document_id=document_id,
                updates=json.dumps(update_payload['fields_to_update'])
            )

            self.state.update_result = str(update_result)

            # Log successful update with details
            fields_updated = list(update_payload['fields_to_update'].keys())
            logger.info(
                f"✓ Update completed for {document_id}:\n"
                f"  SRM: {srm_name}\n"
                f"  Fields updated: {', '.join(fields_updated)}\n"
                f"  Changed by: {update_payload.get('changed_by')}\n"
                f"  Result: {str(update_result)[:100]}"
            )

            # Update state manager
            state_manager.update_record(
                email["email_id"],
                {
                    'update_payload': update_payload,
                    'matched_srm': matched_srm,
                    'update_result': str(update_result),
                    'status': EmailStatus.COMPLETED_SUCCESS,
                    'last_error': None  # Clear any previous errors
                }
            )

            # Emit success
            await context.emit_event(
                process_event=self.OutputEvents.Success,
                data={
                    "email": email,
                    "update_payload": update_payload,
                    "update_result": update_result,
                    **data
                }
            )

        except Exception as e:
            error_msg = (
                f"Error updating SRM {document_id} ({srm_name}): {str(e)}\n"
                f"Fields attempted: {list(update_payload.get('fields_to_update', {}).keys())}"
            )
            logger.error(f"✗ {error_msg}", exc_info=True)

            # Save error to email record
            state_manager.update_record(
                email.get("email_id"),
                {
                    "last_error": error_msg,
                    "status": EmailStatus.SEARCH_ERROR  # Use search_error for update failures too
                }
            )

            await context.emit_event(
                process_event=self.OutputEvents.Failed,
                data={"email": email, "error": str(e), **data}
            )


# ============================================================================
# PROCESS BUILDER
# ============================================================================

class SrmHelpProcess:
    """
    SRM Help Process - processes SRM update requests.

    Process Flow:
    1. ExtractDataStep: Extract structured data from email using LLM
    2. SearchSRMStep: Search for SRM using intelligent fuzzy matching
    3. UpdateIndexStep: Update SRM document in Azure AI Search
    """

    class ProcessEvents:
        """Process-level events."""
        StartHelp: str = "StartHelp"
        ProcessComplete: str = "ProcessComplete"

    @staticmethod
    def create_process(process_name: str = "SrmHelpProcess") -> ProcessBuilder:
        """
        Create the SRM Help Process using SK framework.

        Args:
            process_name: Name for the process

        Returns:
            ProcessBuilder configured with steps and event wiring
        """
        process = ProcessBuilder(name=process_name)

        # Add steps
        extract_step = process.add_step(ExtractDataStep)
        clarification_step = process.add_step(ClarificationStep)
        search_step = process.add_step(SearchSRMStep)
        update_step = process.add_step(UpdateIndexStep)

        # Wire events
        process.on_input_event(
            event_id=SrmHelpProcess.ProcessEvents.StartHelp
        ).send_event_to(extract_step, parameter_name="data")

        extract_step.on_event(
            ExtractDataStep.OutputEvents.Success
        ).send_event_to(search_step, parameter_name="data")

        extract_step.on_event(
            ExtractDataStep.OutputEvents.NeedsClarification
        ).send_event_to(clarification_step, parameter_name="data")

        extract_step.on_event(
            ExtractDataStep.OutputEvents.Failed
        ).stop_process()

        clarification_step.on_event(
            ClarificationStep.OutputEvents.ClarificationSuccess
        ).send_event_to(extract_step, parameter_name="data")

        clarification_step.on_event(
            ClarificationStep.OutputEvents.ClarificationFailed
        ).stop_process()

        search_step.on_event(
            SearchSRMStep.OutputEvents.Found
        ).send_event_to(update_step, parameter_name="data")

        search_step.on_event(
            SearchSRMStep.OutputEvents.NotFound
        ).stop_process()

        update_step.on_event(
            UpdateIndexStep.OutputEvents.Success
        ).stop_process()

        update_step.on_event(
            UpdateIndexStep.OutputEvents.Failed
        ).stop_process()

        return process

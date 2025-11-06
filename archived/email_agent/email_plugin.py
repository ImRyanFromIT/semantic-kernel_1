"""
Email plugin for Microsoft Graph API operations.
"""

import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Annotated
from semantic_kernel.functions import kernel_function

from src.utils.graph_client import GraphClient
from src.utils.error_handler import ErrorHandler, ErrorType
from src.utils.email_validator import validate_email_list, parse_email_recipients
from src.utils.notification_logger import NotificationLogger


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
        self.notification_logger = NotificationLogger()
        self.logger = logging.getLogger(__name__)
    
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
        self.logger.info("[START] authenticate_graph")
        try:
            success = self.graph_client.authenticate()
            if success:
                self.logger.info("[SUCCESS] authenticate_graph")
                return "Successfully authenticated with Microsoft Graph API"
            else:
                self.logger.warning("[FAILED] authenticate_graph - authentication returned False")
                return "Failed to authenticate with Microsoft Graph API"
        except Exception as e:
            self.logger.error(f"[ERROR] authenticate_graph: {e}")
            self.error_handler.handle_error(
                ErrorType.GRAPH_API_AUTH,
                e,
                "authenticate_graph",
                escalate=True
            )
            return f"Authentication failed: {e}"
    
    @kernel_function(
        description=(
            "Fetch unprocessed emails from the monitored mailbox to check for new SRM change requests. "
            "WHEN TO USE: At the start of each autonomous cycle to check for new work. Also when resuming from incomplete tasks. "
            "WHAT IT DOES: Retrieves emails from the last N days, excluding any that have already been processed. "
            "RETURNS: JSON array of emails with email_id, subject, sender, body, received_time, conversation_id. "
            "NEXT STEPS: After fetching, classify each email (help/dont_help/escalate) and process accordingly."
        ),
        name="fetch_emails"
    )
    async def fetch_emails(
        self,
        days_back: Annotated[int, "Number of days to look back for emails (default: 7)"] = 7,
        processed_email_ids: Annotated[str, "Comma-separated list of email IDs that have already been processed (to exclude them)"] = ""
    ) -> Annotated[str, "JSON array of unprocessed email objects with email_id, subject, sender, body, and metadata"]:
        """
        Fetch unprocessed emails from mailbox.

        Args:
            days_back: Number of days to look back
            processed_email_ids: Comma-separated list of processed email IDs

        Returns:
            JSON string of email list or error message
        """
        self.logger.info(f"[START] fetch_emails: days_back={days_back}, processed_count={len(processed_email_ids.split(','))}")
        try:
            processed_ids = [id.strip() for id in processed_email_ids.split(",") if id.strip()]

            # Call async version directly - we're already in an async context
            emails = await self.graph_client.fetch_emails_async(days_back, processed_ids)

            self.logger.info(f"[SUCCESS] fetch_emails: retrieved {len(emails)} emails")
            # Return as JSON string for Semantic Kernel
            import json
            return json.dumps(emails, indent=2)

        except Exception as e:
            self.logger.error(f"[ERROR] fetch_emails: {e}")
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
    async def send_email(self, 
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
            
            success = await self.graph_client.send_email_async(to_address, subject, body, cc_list)
            
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
        description="Reply to an existing email thread. Use this to send confirmations, rejections, or clarification requests to users.",
        name="reply_to_email"
    )
    async def reply_to_email(self, email_id: str, reply_body: str) -> str:
        """
        Reply to an existing email.

        Args:
            email_id: ID of email to reply to
            reply_body: Reply content

        Returns:
            Success or error message
        """
        self.logger.info(f"[START] reply_to_email: email_id={email_id}, body_length={len(reply_body)}")
        try:
            # Call async version directly - we're already in an async context
            success = await self.graph_client.reply_to_email_async(email_id, reply_body)

            if success:
                self.logger.info(f"[SUCCESS] reply_to_email: email_id={email_id}")
                return f"Reply sent successfully for email {email_id}"
            else:
                self.logger.warning(f"[FAILED] reply_to_email: email_id={email_id}")
                return f"Failed to send reply for email {email_id}"

        except Exception as e:
            self.logger.error(f"[ERROR] reply_to_email: email_id={email_id}, error={e}")
            self.error_handler.handle_error(
                ErrorType.GRAPH_API_CALL,
                e,
                "reply_to_email"
            )
            return f"Failed to reply to email: {e}"
    
    @kernel_function(
        description="Forward an email to support team for manual review. Use this when you cannot confidently process a request (ambiguous, low confidence match, or outside scope).",
        name="escalate_email"
    )
    async def escalate_email(self,
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
        self.logger.info(f"[START] escalate_email: email_id={email_id}, reason={escalation_reason}")
        try:
            support_addresses = [addr.strip() for addr in to_addresses.split(",") if addr.strip()]

            comment = (
                f"[SRM Agent Escalation]\n"
                f"Reason: {escalation_reason}\n"
                f"This email requires manual review and handling.\n"
                f"Original email ID: {email_id}"
            )

            # Call async version directly - we're already in an async context
            success = await self.graph_client.forward_email_async(email_id, support_addresses, comment)

            if success:
                self.logger.info(f"[SUCCESS] escalate_email: email_id={email_id}, recipients={len(support_addresses)}")
                return f"Email {email_id} escalated successfully to support team"
            else:
                self.logger.warning(f"[FAILED] escalate_email: email_id={email_id}")
                return f"Failed to escalate email {email_id}"

        except Exception as e:
            self.logger.error(f"[ERROR] escalate_email: email_id={email_id}, error={e}")
            self.error_handler.handle_error(
                ErrorType.GRAPH_API_CALL,
                e,
                "escalate_email"
            )
            return f"Failed to escalate email: {e}"
    
    @kernel_function(
        description=(
            "Send email notification about SRM update to specified recipients. "
            "CRITICAL FUNCTION CALLING REQUIREMENT: When user provides email addresses for notification, you MUST: "
            "1) STOP generating text immediately  "
            "2) CALL THIS FUNCTION with the provided email addresses  "
            "3) WAIT for the function to complete and return a result  "
            "4) Report ONLY what the function actually returned - DO NOT make up success messages  "
            "WRONG: Saying 'I'll send the notification' or 'Notification sent' without calling this function  "
            "RIGHT: Invoke this function, wait for result, then tell user exactly what the function returned  "
            "WHEN TO USE: After successfully calling update_srm_document() AND user provides email address(es)  "
            "PARAMETERS: recipients is comma-separated emails (only @greatvaluelab.com allowed), changes_json is the JSON returned from update_srm_document  "
            "VALIDATION: Function validates email domains automatically and returns error if non-@greatvaluelab.com addresses provided"
        ),
        name="send_update_notification"
    )
    async def send_update_notification(
        self,
        recipients: Annotated[str, "Comma-separated email addresses to notify (only @greatvaluelab.com domain allowed)"],
        changes_json: Annotated[str, "The complete JSON string returned by the update_srm_document function - contains SRM_ID, changes, before/after values"],
        requester_name: Annotated[str, "Name or email of the person who requested the change (for attribution in notification)"] = "Unknown"
    ) -> Annotated[str, "Success message with recipient list, or error message explaining what went wrong"]:
        """
        Send email notification about SRM update to specified recipients.
        
        Args:
            recipients: Comma-separated email addresses (@greatvaluelab.com only)
            changes_json: JSON string from update_srm_document with before/after values
            requester_name: Name or email of person who requested the change
            
        Returns:
            Success or error message
        """
        # Minimal trace to aid troubleshooting without noisy logs
        print(f"[notify] send_update_notification -> recipients_count={len(recipients.split(',')) if recipients else 0}")
        try:
            # Parse recipients
            
            recipient_list = parse_email_recipients(recipients)
            
            
            if not recipient_list:
                return "Error: No recipients provided"
            
            # Validate email domains
            
            valid_emails, invalid_emails = validate_email_list(recipient_list, "greatvaluelab.com")
            
            
            if invalid_emails:
                return (
                    f"Error: The following email addresses are not valid @greatvaluelab.com addresses: "
                    f"{', '.join(invalid_emails)}. "
                    f"Only @greatvaluelab.com domain is allowed for notifications."
                )
            
            if not valid_emails:
                return "Error: No valid recipients after validation"
            
            # Parse changes data
            
            try:
                changes_data = json.loads(changes_json)
                
            except json.JSONDecodeError as e:
                error_msg = f"Error: Invalid changes_json format: {e}"
                
                return error_msg
            
            # Normalize input: support multiple shapes for changes_json
            # A) Result from update_srm_document: { success, srm_id, srm_title, changes: [{field,before,after}] }
            # B) update_payload style: { document_id, fields_to_update, old_values, new_values, ... }
            # C) Raw updates mapping: { owner_notes: "...", hidden_notes: "...", srm_id?: "..." }
            normalized_srm_id = None
            normalized_srm_title = None
            normalized_changes = None
            
            if "success" in changes_data:
                # Case A: explicit update result payload
                if not changes_data.get("success"):
                    return (
                        f"Error: Cannot send notification for failed update: "
                        f"{changes_data.get('error', 'Unknown error')}"
                    )
                normalized_srm_id = (
                    changes_data.get("srm_id")
                    or changes_data.get("SRM_ID")
                    or "Unknown"
                )
                normalized_srm_title = changes_data.get("srm_title") or normalized_srm_id
                normalized_changes = changes_data.get("changes", [])
                
            elif "fields_to_update" in changes_data:
                # Case B: update_payload style
                
                doc_id = (
                    changes_data.get("document_id")
                    or changes_data.get("srm_id")
                    or changes_data.get("SRM_ID")
                    or "Unknown"
                )
                normalized_srm_id = doc_id
                normalized_srm_title = changes_data.get("srm_title") or doc_id
                old_values = changes_data.get("old_values", {})
                new_values = (
                    changes_data.get("new_values")
                    or changes_data.get("fields_to_update")
                    or {}
                )
                normalized_changes = []
                for field, new_val in new_values.items():
                    before_val = old_values.get(field, "")
                    normalized_changes.append({
                        "field": field,
                        "before": before_val,
                        "after": new_val,
                    })
            else:
                # Case C: raw updates mapping
                
                doc_id = (
                    changes_data.get("srm_id")
                    or changes_data.get("document_id")
                    or changes_data.get("SRM_ID")
                    or "Unknown"
                )
                normalized_srm_id = doc_id
                normalized_srm_title = changes_data.get("srm_title") or doc_id
                normalized_changes = []
                
                # Preferred: nested updates dict
                updates_dict = changes_data.get("updates")
                if isinstance(updates_dict, dict):
                    for field, new_val in updates_dict.items():
                        normalized_changes.append({
                            "field": field,
                            "before": "",
                            "after": new_val,
                        })
                else:
                    # Fallback: look for explicit known fields at top level
                    for field in ["owner_notes", "hidden_notes"]:
                        if field in changes_data:
                            normalized_changes.append({
                                "field": field,
                                "before": "",
                                "after": changes_data.get(field, ""),
                            })
                    # If none of the known fields were present, include other non-metadata keys
                    if not normalized_changes:
                        for field, value in changes_data.items():
                            if field not in {"srm_id", "SRM_ID", "srm_title", "document_id", "status"}:
                                normalized_changes.append({
                                    "field": field,
                                    "before": "",
                                    "after": value,
                                })
            
            srm_id = normalized_srm_id
            srm_title = normalized_srm_title
            changes = normalized_changes or []
            
            
            if not changes:
                return "Error: changes_json did not include any change details"
            
            # Build email subject
            subject = f"SRM Update Notification: {srm_id}"
            
            
            # Build email body
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            
            body_lines = [
                f"SRM Update Notification",
                f"=" * 60,
                f"",
                f"SRM ID: {srm_id}",
                f"SRM Title: {srm_title}",
                f"Updated By: {requester_name}",
                f"Timestamp: {timestamp}",
                f"",
                f"Changes Applied:",
                f"-" * 60,
            ]
            
            for change in changes:
                field_name = change.get("field", "unknown_field")
                before_value = change.get("before", "")
                after_value = change.get("after", "")
                
                # Format field name for display
                display_field = field_name.replace("_", " ").title()
                
                body_lines.append(f"")
                body_lines.append(f"Field: {display_field}")
                body_lines.append(f"")
                body_lines.append(f"  BEFORE:")
                body_lines.append(f"  {'-' * 56}")
                # Indent each line of before value
                for line in str(before_value).split('\n'):
                    body_lines.append(f"  {line}")
                body_lines.append(f"")
                body_lines.append(f"  AFTER:")
                body_lines.append(f"  {'-' * 56}")
                # Indent each line of after value
                for line in str(after_value).split('\n'):
                    body_lines.append(f"  {line}")
                body_lines.append(f"")
            
            body_lines.append(f"=" * 60)
            body_lines.append(f"")
            body_lines.append(f"This is an automated notification from the SRM Archivist Agent.")
            
            body = "\n".join(body_lines)
            
            
            # Send notification emails
            
            async def _send_email(email_addr):
                """Send email to a single recipient."""
                try:
                    
                    result = await self.graph_client.send_email_async(
                        email_addr, subject, body
                    )
                    
                    return (email_addr, result)
                except Exception as e:
                    import traceback
                    print(f"[notify] Failed to send notification to {email_addr}: {e}")
                    print(f"[notify] Traceback: {traceback.format_exc()}")
                    return (email_addr, False)
            
            # Send emails sequentially instead of concurrently
            results = []
            for addr in valid_emails:
                result = await _send_email(addr)
                results.append(result)
            
            # Count successes and failures
            success_count = sum(1 for _, success in results if success)
            failed_recipients = [addr for addr, success in results if not success]
            
            # Log notification
            if success_count > 0:
                fields_changed = [change.get("field") for change in changes]
                self.notification_logger.log_notification_sent(
                    srm_id=srm_id,
                    recipients=valid_emails[:success_count],
                    fields_changed=fields_changed,
                    sent_by=requester_name,
                    additional_info={"srm_title": srm_title}
                )
            
            if failed_recipients:
                self.notification_logger.log_notification_failed(
                    srm_id=srm_id,
                    recipients=failed_recipients,
                    error_message="Failed to send email via Graph API",
                    fields_changed=[change.get("field") for change in changes],
                    sent_by=requester_name
                )
            
            # Return result message
            print(f"[notify] completed success_count={success_count} total={len(valid_emails)}")
            if success_count == len(valid_emails):
                result_msg = f"Notification sent successfully to {success_count} recipient(s): {', '.join(valid_emails)}"
                
                return result_msg
            elif success_count > 0:
                result_msg = f"Notification sent to {success_count} recipient(s), but failed for: {', '.join(failed_recipients)}"
                
                return result_msg
            else:
                result_msg = f"Failed to send notification to all recipients: {', '.join(failed_recipients)}"
                
                return result_msg
                
        except Exception as e:
            self.error_handler.handle_error(
                ErrorType.GRAPH_API_CALL,
                e,
                "send_update_notification"
            )
            import traceback
            error_msg = f"Failed to send notification: {e}\n{traceback.format_exc()}"
            print(error_msg)
            return error_msg

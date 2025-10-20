"""
SRM Help Process V2 - Proper SK Process Framework Implementation

Uses proper state management, event-driven architecture, and process execution.
"""

from typing import Dict, Any
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

from ..models.email_record import EmailStatus
from ..utils.srm_matcher import SrmMatcher


# ============================================================================
# STEP STATES
# ============================================================================

class ExtractStepState(KernelProcessStepState):
    """State for extraction step."""
    email_id: str = Field(default="")
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    attempts: int = Field(default=0)


class SearchStepState(KernelProcessStepState):
    """State for search step."""
    srm_title: str = Field(default="")
    matched_srm: Dict[str, Any] = Field(default_factory=dict)
    match_type: str = Field(default="")
    confidence: float = Field(default=0.0)


class UpdateStepState(KernelProcessStepState):
    """State for update step."""
    document_id: str = Field(default="")
    update_payload: Dict[str, Any] = Field(default_factory=dict)
    update_result: str = Field(default="")


# ============================================================================
# PROCESS STEPS
# ============================================================================

@kernel_process_step_metadata("ExtractDataStep")
class ExtractDataStep(KernelProcessStep[ExtractStepState]):
    """Extract structured data from email using LLM."""
    
    class OutputEvents:
        Success: str = "Success"
        Failed: str = "Failed"
    
    async def activate(self, state: KernelProcessStepState):
        """Initialize step state."""
        self.state = ExtractStepState(**state.model_dump()) if state else ExtractStepState()
    
    @kernel_function
    async def extract(
        self,
        context: KernelProcessStepContext,
        data: Dict[str, Any],
        kernel: Kernel,
    ):
        """Extract change request details from email."""
        try:
            # Extract inputs from event data
            email = data.get("email", {})
            state_manager = data.get("state_manager")
            search_plugin = data.get("search_plugin")
            
            # Update step state
            self.state.email_id = email.get("email_id", "")
            self.state.attempts += 1
            
            # Get extraction plugin
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
                await context.emit_event(
                    process_event=self.OutputEvents.Success,
                    data={
                        "email": email,
                        "extracted_data": extracted_data,
                        "kernel": kernel,
                        "state_manager": state_manager,
                        "search_plugin": search_plugin
                    }
                )
            else:
                # Data incomplete - would need clarification
                await context.emit_event(
                    process_event=self.OutputEvents.Failed,
                    data={
                        "email": email,
                        "extracted_data": extracted_data,
                        "validation": validation,
                        "reason": "incomplete_data"
                    }
                )
                
        except Exception as e:
            await context.emit_event(
                process_event=self.OutputEvents.Failed,
                data={"email": email, "error": str(e), "reason": "extraction_error"}
            )


@kernel_process_step_metadata("SearchSRMStep")
class SearchSRMStep(KernelProcessStep[SearchStepState]):
    """Search for SRM using intelligent fuzzy matching."""
    
    class OutputEvents:
        Found: str = "Found"
        NotFound: str = "NotFound"
    
    async def activate(self, state: KernelProcessStepState):
        """Initialize step state."""
        self.state = SearchStepState(**state.model_dump()) if state else SearchStepState()
    
    @kernel_function
    async def search(
        self,
        context: KernelProcessStepContext,
        data: Dict[str, Any],
        kernel: Kernel,
    ):
        """Search for SRM in index with intelligent matching."""
        try:
            # Extract inputs from event data
            email = data.get("email", {})
            extracted_data = data.get("extracted_data", {})
            state_manager = data.get("state_manager")
            search_plugin = data.get("search_plugin")
            
            srm_title = extracted_data.get("srm_title", "")
            if not srm_title:
                await context.emit_event(
                    process_event=self.OutputEvents.NotFound,
                    data={"email": email, "reason": "no_srm_title"}
                )
                return
            
            # Update step state
            self.state.srm_title = srm_title
            
            # Search for SRM using proper SK plugin invocation
            search_result = await search_plugin["search_srm"].invoke(
                kernel=kernel,
                query=srm_title,
                top_k=10
            )
            search_data = json.loads(str(search_result))
            
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
            
            # Check if we should proceed
            if SrmMatcher.should_proceed_with_update(match_type):
                # Safe to proceed
                await context.emit_event(
                    process_event=self.OutputEvents.Found,
                    data={
                        "email": email,
                        "extracted_data": extracted_data,
                        "matched_srm": matched_srm,
                        "match_type": match_type,
                        "confidence": confidence,
                        "kernel": kernel,
                        "state_manager": state_manager,
                        "search_plugin": search_plugin
                    }
                )
            else:
                # Cannot proceed - escalate
                match_explanation = SrmMatcher.get_match_explanation(
                    match_type,
                    srm_title,
                    matched_srm.get("Name") if matched_srm else None,
                    confidence,
                    search_data,
                    name_field="Name"
                )
                await context.emit_event(
                    process_event=self.OutputEvents.NotFound,
                    data={
                        "email": email,
                        "reason": "no_safe_match",
                        "match_type": match_type,
                        "match_explanation": match_explanation
                    }
                )
                
        except Exception as e:
            await context.emit_event(
                process_event=self.OutputEvents.NotFound,
                data={"email": email, "error": str(e), "reason": "search_error"}
            )


@kernel_process_step_metadata("UpdateIndexStep")
class UpdateIndexStep(KernelProcessStep[UpdateStepState]):
    """Update SRM document in Azure AI Search."""
    
    class OutputEvents:
        Success: str = "Success"
        Failed: str = "Failed"
    
    async def activate(self, state: KernelProcessStepState):
        """Initialize step state."""
        self.state = UpdateStepState(**state.model_dump()) if state else UpdateStepState()
    
    @kernel_function
    async def update(
        self,
        context: KernelProcessStepContext,
        data: Dict[str, Any],
        kernel: Kernel,
    ):
        """Update SRM document in Azure AI Search."""
        try:
            # Extract inputs from event data
            email = data.get("email", {})
            extracted_data = data.get("extracted_data", {})
            matched_srm = data.get("matched_srm", {})
            state_manager = data.get("state_manager")
            search_plugin = data.get("search_plugin")
            
            # Prepare update payload
            document_id = matched_srm.get('SRM_ID') or matched_srm.get('srm_id', '')
            srm_name = matched_srm.get('Name') or matched_srm.get('name', 'Unknown')
            
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
            
            # Apply update using proper SK plugin invocation
            update_result = await search_plugin["update_srm_document"].invoke(
                kernel=kernel,
                document_id=document_id,
                updates=json.dumps(update_payload['fields_to_update'])
            )
            
            self.state.update_result = str(update_result)
            
            # Update state manager
            state_manager.update_record(
                email["email_id"],
                {
                    'update_payload': update_payload,
                    'matched_srm': matched_srm,
                    'update_result': str(update_result),
                    'status': EmailStatus.COMPLETED_SUCCESS
                }
            )
            
            # Emit success
            await context.emit_event(
                process_event=self.OutputEvents.Success,
                data={
                    "email": email,
                    "update_payload": update_payload,
                    "update_result": update_result
                }
            )
            
        except Exception as e:
            await context.emit_event(
                process_event=self.OutputEvents.Failed,
                data={"email": email, "error": str(e)}
            )


# ============================================================================
# PROCESS BUILDER
# ============================================================================

def create_srm_help_process() -> ProcessBuilder:
    """
    Create the SRM Help Process using proper SK framework.
    
    Returns:
        ProcessBuilder configured with steps and event wiring
    """
    process = ProcessBuilder(name="SrmHelpProcess")
    
    # Add steps
    extract_step = process.add_step(ExtractDataStep)
    search_step = process.add_step(SearchSRMStep)
    update_step = process.add_step(UpdateIndexStep)
    
    # Wire events with target functions
    process.on_input_event(event_id="Start").send_event_to(extract_step, parameter_name="data")
    
    extract_step.on_event(ExtractDataStep.OutputEvents.Success).send_event_to(search_step, parameter_name="data")
    extract_step.on_event(ExtractDataStep.OutputEvents.Failed).stop_process()
    
    search_step.on_event(SearchSRMStep.OutputEvents.Found).send_event_to(update_step, parameter_name="data")
    search_step.on_event(SearchSRMStep.OutputEvents.NotFound).stop_process()
    
    update_step.on_event(UpdateIndexStep.OutputEvents.Success).stop_process()
    update_step.on_event(UpdateIndexStep.OutputEvents.Failed).stop_process()
    
    return process


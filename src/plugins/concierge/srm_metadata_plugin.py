"""
SRM Metadata Plugin for maintainer operations.

Provides functions for updating SRM metadata through vector store.
"""

import json
import logging
from typing import Annotated

from semantic_kernel.functions import kernel_function

from src.memory.vector_store_base import VectorStoreBase
from src.models.srm_record import SRMRecord


logger = logging.getLogger(__name__)


class SRMMetadataPlugin:
    """
    Plugin for SRM metadata management operations.

    Provides kernel functions for searching, retrieving, and updating SRM records
    in the vector store. Used by the maintainer agent through API endpoints.
    """

    def __init__(self, vector_store: VectorStoreBase):
        """
        Initialize the plugin.

        Args:
            vector_store: Vector store instance for SRM data
        """
        self.vector_store = vector_store

    @kernel_function(
        description=(
            "Update SRM metadata fields (owner_notes, hidden_notes, etc.) in the vector store. "
            "WHEN TO USE: After confirming the user wants to make changes to an SRM. "
            "PROCESS: 1) Get current record, 2) Apply updates, 3) Upsert back to store. "
            "RETURNS: JSON with success status and before/after values."
        ),
        name="update_srm_metadata"
    )
    async def update_srm_metadata(
        self,
        srm_id: Annotated[str, "The SRM ID to update (e.g., 'SRM-001')"],
        updates: Annotated[str, "JSON string of field updates, e.g., '{\"owner_notes\": \"New text\"}'"]
    ) -> Annotated[str, "JSON response with success status, changes, and before/after values"]:
        """
        Update SRM metadata fields.

        Args:
            srm_id: ID of the SRM to update
            updates: JSON string of field:value pairs to update

        Returns:
            JSON string with update result
        """
        try:
            # Parse updates
            update_data = json.loads(updates)

            # Get current record
            record = await self.vector_store.get_by_id(srm_id)
            if not record:
                return json.dumps({
                    "success": False,
                    "error": f"SRM {srm_id} not found"
                })

            # Capture before state
            before_state = {}
            for field in update_data.keys():
                before_state[field] = getattr(record, field, "")

            # Apply updates (only allow specific fields)
            UPDATABLE_FIELDS = {"owner_notes", "hidden_notes"}
            for field, value in update_data.items():
                if field not in UPDATABLE_FIELDS:
                    logger.warning(f"Attempted to update non-updatable field: {field}")
                    continue
                setattr(record, field, value)

            # Upsert updated record
            await self.vector_store.upsert([record])

            # Build response with changes (only include actually updated fields)
            changes = []
            for field, after_value in update_data.items():
                if field in UPDATABLE_FIELDS:
                    changes.append({
                        "field": field,
                        "before": before_state.get(field, ""),
                        "after": after_value
                    })

            response = {
                "success": True,
                "srm_id": srm_id,
                "srm_name": record.name,
                "changes": changes
            }

            logger.info(f"Updated SRM {srm_id}: {list(update_data.keys())}")
            return json.dumps(response, indent=2)

        except json.JSONDecodeError as e:
            return json.dumps({
                "success": False,
                "error": f"Invalid JSON in updates: {e}"
            })
        except Exception as e:
            logger.error(f"Error updating SRM {srm_id}: {e}", exc_info=True)
            return json.dumps({
                "success": False,
                "error": f"Update failed: {e}"
            })

    @kernel_function(
        description="Search for SRM by name or keywords to find the ID",
        name="search_srm"
    )
    async def search_srm(
        self,
        query: Annotated[str, "Search query (SRM name or keywords)"],
        top_k: Annotated[int, "Number of results to return"] = 5
    ) -> Annotated[str, "JSON array of matching SRMs with ID, name, category"]:
        """
        Search for SRMs by keywords.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            JSON array of search results
        """
        try:
            results = []
            async for result in await self.vector_store.search(query, top_k=top_k):
                results.append({
                    "id": result.record.id,
                    "name": result.record.name,
                    "category": result.record.category,
                    "use_case": result.record.use_case,
                    "score": result.score
                })

            return json.dumps(results, indent=2)

        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            return json.dumps([])

    @kernel_function(
        description="Get specific SRM by ID",
        name="get_srm_by_id"
    )
    async def get_srm_by_id(
        self,
        srm_id: Annotated[str, "The SRM ID to retrieve"]
    ) -> Annotated[str, "JSON object with SRM details"]:
        """
        Get SRM by ID.

        Args:
            srm_id: SRM ID

        Returns:
            JSON object with SRM data
        """
        try:
            record = await self.vector_store.get_by_id(srm_id)
            if not record:
                return json.dumps({
                    "success": False,
                    "error": f"SRM {srm_id} not found"
                })

            return json.dumps({
                "success": True,
                "srm": {
                    "id": record.id,
                    "name": record.name,
                    "category": record.category,
                    "use_case": record.use_case,
                    "owner_notes": record.owner_notes,
                    "hidden_notes": record.hidden_notes
                }
            }, indent=2)

        except Exception as e:
            logger.error(f"Get by ID error: {e}", exc_info=True)
            return json.dumps({
                "success": False,
                "error": str(e)
            })

    @kernel_function(
        description="Update multiple SRMs matching filter criteria",
        name="batch_update_srms"
    )
    async def batch_update_srms(
        self,
        filter_json: Annotated[str, "JSON filter criteria (e.g., '{\"team\": \"Database Services Team\"}')"],
        updates: Annotated[str, "JSON string of field updates"]
    ) -> Annotated[str, "JSON response with updated count and IDs"]:
        """
        Batch update SRMs matching filter.

        Args:
            filter_json: JSON filter criteria
            updates: JSON field updates

        Returns:
            JSON with results
        """
        try:
            # Parse inputs
            filter_data = json.loads(filter_json)
            update_data = json.loads(updates)

            # Get all SRMs (search with broad query)
            all_results = []
            async for result in await self.vector_store.search("", top_k=200):
                all_results.append(result.record)

            # Filter records
            matching_records = []
            for record in all_results:
                matches = True
                if "team" in filter_data:
                    if record.owning_team != filter_data["team"]:
                        matches = False
                if "type" in filter_data:
                    if record.category != filter_data["type"]:
                        matches = False

                if matches:
                    matching_records.append(record)

            # Update records (max 20 for safety)
            MAX_BATCH_SIZE = 20
            if len(matching_records) > MAX_BATCH_SIZE:
                return json.dumps({
                    "success": False,
                    "error": f"Too many matches ({len(matching_records)}). Max batch size is {MAX_BATCH_SIZE}."
                })

            # Apply updates
            UPDATABLE_FIELDS = {"owner_notes", "hidden_notes"}
            updated_ids = []
            failures = []

            for record in matching_records:
                try:
                    for field, value in update_data.items():
                        if field in UPDATABLE_FIELDS:
                            setattr(record, field, value)

                    await self.vector_store.upsert([record])
                    updated_ids.append(record.id)
                except Exception as e:
                    failures.append({
                        "srm_id": record.id,
                        "error": str(e)
                    })

            return json.dumps({
                "success": True,
                "updated_count": len(updated_ids),
                "updated_ids": updated_ids,
                "failures": failures
            }, indent=2)

        except Exception as e:
            logger.error(f"Batch update error: {e}", exc_info=True)
            return json.dumps({
                "success": False,
                "error": str(e)
            })

    @kernel_function(
        description="Create temporary SRM (not persisted to CSV, session-scoped)",
        name="create_temp_srm"
    )
    async def create_temp_srm(
        self,
        srm_data_json: Annotated[str, "JSON with name, category, owning_team, use_case"]
    ) -> Annotated[str, "JSON response with temp SRM ID and details"]:
        """
        Create temporary SRM in memory.

        NOTE: This requires access to app.state which is only available
        in the chatbot context. This function will be called via API.

        Args:
            srm_data_json: JSON with SRM fields

        Returns:
            JSON with created SRM
        """
        # This is a placeholder - actual implementation is in the API endpoint
        # since it needs access to app.state.temp_srms
        return json.dumps({
            "success": False,
            "error": "create_temp_srm must be called via API endpoint"
        })

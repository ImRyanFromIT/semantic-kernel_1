"""
API Client Plugin for CLI Concierge.

Makes HTTP requests to the chatbot concierge API endpoints.
"""

import httpx
import json
import logging
from typing import Annotated

from semantic_kernel.functions import kernel_function


logger = logging.getLogger(__name__)


class ConciergeAPIClientPlugin:
    """
    Plugin that makes HTTP calls to chatbot concierge API.

    All SRM operations are performed by calling the chatbot service,
    which manages the vector store. This plugin is stateless and makes
    HTTP requests only.
    """

    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        Initialize API client plugin.

        Args:
            base_url: Base URL of chatbot service (hardcoded for demo)
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = 30.0

    @staticmethod
    def normalize_srm_id(srm_id: str) -> str:
        """
        Normalize SRM ID to standard format: SRM-XXX (uppercase, zero-padded).

        Handles variations like:
        - "srm-37" -> "SRM-037"
        - "SRM-37" -> "SRM-037"
        - "srm-037" -> "SRM-037"
        - "37" -> "SRM-037"
        - "037" -> "SRM-037"

        Args:
            srm_id: SRM ID in any format

        Returns:
            Normalized SRM ID (e.g., "SRM-037")
        """
        # Remove whitespace and convert to uppercase
        srm_id = srm_id.strip().upper()

        # Extract numeric part
        import re
        match = re.search(r'(\d+)', srm_id)
        if not match:
            # No number found, return as-is (will likely fail in API)
            return srm_id

        number = int(match.group(1))

        # Format as SRM-XXX with zero-padding to 3 digits
        return f"SRM-{number:03d}"

    @kernel_function(
        description=(
            "Search for SRM by name or keywords. "
            "Use this when the user mentions an SRM by name but you don't have the ID. "
            "Returns list of matching SRMs with IDs, names, and categories. "
            "Example: User says 'update the storage SRM' - use this to find the SRM ID first."
        ),
        name="search_srm"
    )
    async def search_srm(
        self,
        query: Annotated[str, "Search query (SRM name or keywords like 'storage', 'VM capacity')"],
        top_k: Annotated[int, "Number of results to return (default: 5)"] = 5
    ) -> Annotated[str, "JSON array of matching SRMs with id, name, category, and score"]:
        """
        Search for SRMs via chatbot API.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            JSON string with search results
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/concierge/search",
                    json={"query": query, "top_k": top_k}
                )

                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    logger.info(f"Search for '{query}' returned {len(results)} results")
                    return json.dumps(results, indent=2)
                else:
                    error_msg = f"Search API returned status {response.status_code}"
                    logger.error(error_msg)
                    return json.dumps({"error": error_msg})

        except Exception as e:
            logger.error(f"Search API call failed: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @kernel_function(
        description=(
            "Get specific SRM details by ID. "
            "Use this to see current values before updating. "
            "Returns full SRM record with id, name, category, owner_notes, hidden_notes."
        ),
        name="get_srm_by_id"
    )
    async def get_srm_by_id(
        self,
        srm_id: Annotated[str, "The SRM ID to retrieve (e.g., 'SRM-001', 'srm-37', or just '37')"]
    ) -> Annotated[str, "JSON object with SRM details"]:
        """
        Get SRM by ID via chatbot API.

        Args:
            srm_id: SRM ID (will be normalized to SRM-XXX format)

        Returns:
            JSON string with SRM data
        """
        try:
            # Normalize ID to standard format (SRM-XXX)
            normalized_id = self.normalize_srm_id(srm_id)
            logger.info(f"Normalized '{srm_id}' to '{normalized_id}'")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/concierge/get",
                    json={"srm_id": normalized_id}
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("error"):
                        return json.dumps({"error": data["error"]})
                    return json.dumps(data.get("srm", {}), indent=2)
                else:
                    error_msg = f"Get API returned status {response.status_code}"
                    logger.error(error_msg)
                    return json.dumps({"error": error_msg})

        except Exception as e:
            logger.error(f"Get API call failed: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @kernel_function(
        description=(
            "Update SRM metadata fields like owner_notes or hidden_notes. "
            "IMPORTANT: Only call this AFTER user confirms they want to make the update. "
            "Returns success status with before/after values for changed fields."
        ),
        name="update_srm_metadata"
    )
    async def update_srm_metadata(
        self,
        srm_id: Annotated[str, "The SRM ID to update (e.g., 'SRM-001', 'srm-37', or just '37')"],
        updates: Annotated[str, "JSON string of fields to update, e.g., '{\"owner_notes\": \"Updated notes\"}'"]
    ) -> Annotated[str, "JSON response with success status, srm_id, and changes array"]:
        """
        Update SRM metadata via chatbot API.

        Args:
            srm_id: SRM ID to update (will be normalized to SRM-XXX format)
            updates: JSON string of field updates

        Returns:
            JSON string with update result
        """
        try:
            # Normalize ID to standard format (SRM-XXX)
            normalized_id = self.normalize_srm_id(srm_id)
            logger.info(f"Normalized '{srm_id}' to '{normalized_id}' for update")

            # Parse updates to dict for API
            updates_dict = json.loads(updates)

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/concierge/update",
                    json={
                        "srm_id": normalized_id,
                        "updates": updates_dict
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Update SRM {srm_id}: success={data.get('success')}")
                    return json.dumps(data, indent=2)
                else:
                    error_msg = f"Update API returned status {response.status_code}"
                    logger.error(error_msg)
                    return json.dumps({
                        "success": False,
                        "error": error_msg
                    })

        except json.JSONDecodeError as e:
            return json.dumps({
                "success": False,
                "error": f"Invalid JSON in updates: {e}"
            })
        except Exception as e:
            logger.error(f"Update API call failed: {e}", exc_info=True)
            return json.dumps({
                "success": False,
                "error": str(e)
            })

    @kernel_function(
        description=(
            "Get system statistics including total SRM count and temp SRM count. "
            "Use this when responding to help command to show current state."
        ),
        name="get_stats"
    )
    async def get_stats(self) -> Annotated[str, "JSON object with system statistics"]:
        """
        Get system statistics from chatbot API.

        Returns:
            JSON string with stats (total_srms, temp_srms, chatbot_url, status)
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/api/concierge/stats"
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Stats retrieved: {data.get('total_srms')} total, {data.get('temp_srms')} temp")
                    return json.dumps(data, indent=2)
                else:
                    error_msg = f"Stats API returned status {response.status_code}"
                    logger.error(error_msg)
                    return json.dumps({"error": error_msg})

        except Exception as e:
            logger.error(f"Stats API call failed: {e}", exc_info=True)
            return json.dumps({"error": str(e)})

    @kernel_function(
        description=(
            "Batch update multiple SRMs matching filter criteria. "
            "Supports filtering by team, type. Max 20 SRMs per batch. "
            "IMPORTANT: ALWAYS get confirmation from user before calling this. "
            "Show user which SRMs will be updated and ask for explicit 'yes'."
        ),
        name="batch_update_srms"
    )
    async def batch_update_srms(
        self,
        filter_json: Annotated[str, "JSON filter criteria (e.g., '{\"team\": \"Database Services Team\"}')"],
        updates_json: Annotated[str, "JSON string of field updates"]
    ) -> Annotated[str, "JSON response with updated count and IDs"]:
        """
        Batch update SRMs matching filter.

        Args:
            filter_json: JSON filter criteria
            updates_json: JSON field updates

        Returns:
            JSON string with batch update results
        """
        try:
            # Parse to validate JSON
            filter_data = json.loads(filter_json)
            updates_data = json.loads(updates_json)

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/concierge/batch/update",
                    json={
                        "filter": filter_data,
                        "updates": updates_data
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"Batch update: {data.get('updated_count')} SRMs updated")
                    return json.dumps(data, indent=2)
                else:
                    error_msg = f"Batch update API returned status {response.status_code}"
                    logger.error(error_msg)
                    return json.dumps({
                        "success": False,
                        "error": error_msg
                    })

        except json.JSONDecodeError as e:
            return json.dumps({
                "success": False,
                "error": f"Invalid JSON: {e}"
            })
        except Exception as e:
            logger.error(f"Batch update API call failed: {e}", exc_info=True)
            return json.dumps({
                "success": False,
                "error": str(e)
            })

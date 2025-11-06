"""
API Client Plugin for CLI Maintainer.

Makes HTTP requests to the chatbot maintainer API endpoints.
"""

import httpx
import json
import logging
from typing import Annotated

from semantic_kernel.functions import kernel_function


logger = logging.getLogger(__name__)


class MaintainerAPIClientPlugin:
    """
    Plugin that makes HTTP calls to chatbot maintainer API.

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
                    f"{self.base_url}/api/maintainer/search",
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
        srm_id: Annotated[str, "The SRM ID to retrieve (e.g., 'SRM-001')"]
    ) -> Annotated[str, "JSON object with SRM details"]:
        """
        Get SRM by ID via chatbot API.

        Args:
            srm_id: SRM ID

        Returns:
            JSON string with SRM data
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/maintainer/get",
                    json={"srm_id": srm_id}
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
        srm_id: Annotated[str, "The SRM ID to update (e.g., 'SRM-001')"],
        updates: Annotated[str, "JSON string of fields to update, e.g., '{\"owner_notes\": \"Updated notes\"}'"]
    ) -> Annotated[str, "JSON response with success status, srm_id, and changes array"]:
        """
        Update SRM metadata via chatbot API.

        Args:
            srm_id: SRM ID to update
            updates: JSON string of field updates

        Returns:
            JSON string with update result
        """
        try:
            # Parse updates to dict for API
            updates_dict = json.loads(updates)

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/maintainer/update",
                    json={
                        "srm_id": srm_id,
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

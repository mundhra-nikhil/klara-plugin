"""Microsoft Graph API client for M365 integration."""

from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger_with_context
from src.configs.config import settings
from .auth_service import microsoft_auth_service

logger = get_logger_with_context()


class GraphClient:
    """
    Microsoft Graph API client wrapper for SharePoint and OneDrive operations.

    Provides methods for:
    - Site and drive listing
    - Document access and management
    - File upload/download
    - Metadata operations
    """

    # Graph API endpoints
    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
    DEFAULT_TIMEOUT = 30.0
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0

    def __init__(self, access_token: Optional[str] = None):
        """
        Initialize Microsoft Graph client.

        Args:
            access_token: Microsoft Graph access token (optional, can be set later)
        """
        self.access_token = access_token
        self._client: Optional[httpx.AsyncClient] = None
        self._token_expiry: Optional[datetime] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with valid token."""
        if self._client is None or self._is_token_expired():
            await self._refresh_client()
        return self._client

    def _is_token_expired(self) -> bool:
        """Check if current token is expired or will expire soon."""
        if not self._token_expiry:
            return False
        # Refresh if token expires within 5 minutes
        return datetime.now(timezone.utc) >= self._token_expiry - timedelta(minutes=5)

    async def _refresh_client(self):
        """Refresh HTTP client with new access token."""
        if not self.access_token:
            raise ValueError("No access token available. Please authenticate first.")

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        self._client = httpx.AsyncClient(
            base_url=self.GRAPH_API_BASE,
            headers=headers,
            timeout=self.DEFAULT_TIMEOUT,
        )

        # Set token expiry (default 1 hour if not specified)
        self._token_expiry = datetime.now(timezone.utc) + timedelta(minutes=55)

    async def close(self):
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make authenticated request to Microsoft Graph API with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE, PATCH)
            endpoint: Graph API endpoint (without base URL)
            **kwargs: Additional arguments for httpx request

        Returns:
            JSON response data

        Raises:
            httpx.HTTPStatusError: If request fails after retries
            ValueError: If response is invalid
        """
        client = await self._get_client()

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await client.request(method, endpoint, **kwargs)

                # Handle rate limiting (429)
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", self.RETRY_DELAY))
                    logger.warning("rate_limit_detected", function="_make_request",
                                retry_after=retry_after, attempt=attempt + 1)
                    await asyncio.sleep(retry_after)
                    continue

                # Handle other errors
                response.raise_for_status()
                return response.json()

            except httpx.HTTPStatusError as e:
                if e.response.status_code in (401, 403):
                    logger.error("authentication_error", function="_make_request",
                               status_code=e.response.status_code)
                    raise ValueError(f"Authentication failed: {e.response.status_code}")

                if attempt < self.MAX_RETRIES - 1:
                    logger.warning("request_failed_retrying", function="_make_request",
                                 status_code=e.response.status_code, attempt=attempt + 1)
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                raise

            except Exception as e:
                if attempt < self.MAX_RETRIES - 1:
                    logger.warning("request_error_retrying", function="_make_request",
                                 error=str(e), attempt=attempt + 1)
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                raise

        raise ValueError("Max retries exceeded")

    async def get_user_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Fetch user profile from Microsoft Graph.

        Args:
            user_id: Microsoft user ID or email

        Returns:
            User profile data including display name, email, etc.
        """
        logger.info("fetching_user_profile", function="get_user_profile", user_id=user_id)

        try:
            response = await self._make_request("GET", f"/users/{user_id}")
            logger.info("user_profile_fetched", function="get_user_profile", user_id=user_id)
            return response

        except Exception as e:
            logger.error("user_profile_fetch_failed", function="get_user_profile",
                        user_id=user_id, error=str(e))
            raise

    async def get_sites(self, search: Optional[str] = None) -> Dict[str, Any]:
        """
        Get SharePoint sites accessible to authenticated user.

        Args:
            search: Optional search query to filter sites

        Returns:
            Dict with 'value' array of site objects
        """
        logger.info("fetching_sharepoint_sites", function="get_sites", search=search)

        try:
            endpoint = "/sites?search=*"
            if search:
                endpoint = f"/sites?search={search}"

            response = await self._make_request("GET", endpoint)
            logger.info("sharepoint_sites_fetched", function="get_sites",
                       count=len(response.get("value", [])))
            return response

        except Exception as e:
            logger.error("sharepoint_sites_fetch_failed", function="get_sites", error=str(e))
            raise

    async def get_site_by_id(self, site_id: str) -> Dict[str, Any]:
        """
        Get specific SharePoint site by ID.

        Args:
            site_id: SharePoint site ID (hostname + relative path)

        Returns:
            Site details
        """
        logger.info("fetching_site_by_id", function="get_site_by_id", site_id=site_id)

        try:
            response = await self._make_request("GET", f"/sites/{site_id}")
            logger.info("site_fetched", function="get_site_by_id", site_id=site_id)
            return response

        except Exception as e:
            logger.error("site_fetch_failed", function="get_site_by_id",
                        site_id=site_id, error=str(e))
            raise

    async def get_site_drives(self, site_id: str) -> Dict[str, Any]:
        """
        Get document libraries (drives) for a SharePoint site.

        Args:
            site_id: SharePoint site ID

        Returns:
            Dict with 'value' array of drive objects
        """
        logger.info("fetching_site_drives", function="get_site_drives", site_id=site_id)

        try:
            response = await self._make_request("GET", f"/sites/{site_id}/drives")
            logger.info("site_drives_fetched", function="get_site_drives",
                       site_id=site_id, count=len(response.get("value", [])))
            return response

        except Exception as e:
            logger.error("site_drives_fetch_failed", function="get_site_drives",
                        site_id=site_id, error=str(e))
            raise

    async def get_drive_items(self, drive_id: str, item_id: str = "root") -> Dict[str, Any]:
        """
        Get documents/items in a SharePoint drive.

        Args:
            drive_id: Drive ID
            item_id: Item ID (default: "root" for top level)

        Returns:
            Dict with 'value' array of drive items
        """
        logger.info("fetching_drive_items", function="get_drive_items",
                   drive_id=drive_id, item_id=item_id)

        try:
            response = await self._make_request("GET", f"/drives/{drive_id}/items/{item_id}/children")
            logger.info("drive_items_fetched", function="get_drive_items",
                       drive_id=drive_id, count=len(response.get("value", [])))
            return response

        except Exception as e:
            logger.error("drive_items_fetch_failed", function="get_drive_items",
                        drive_id=drive_id, error=str(e))
            raise

    async def get_drive_item(self, drive_id: str, item_id: str) -> Dict[str, Any]:
        """
        Get specific drive item metadata.

        Args:
            drive_id: Drive ID
            item_id: Item ID

        Returns:
            Drive item metadata
        """
        logger.info("fetching_drive_item", function="get_drive_item",
                   drive_id=drive_id, item_id=item_id)

        try:
            response = await self._make_request("GET", f"/drives/{drive_id}/items/{item_id}")
            logger.info("drive_item_fetched", function="get_drive_item",
                       drive_id=drive_id, item_id=item_id)
            return response

        except Exception as e:
            logger.error("drive_item_fetch_failed", function="get_drive_item",
                        drive_id=drive_id, item_id=item_id, error=str(e))
            raise

    async def get_download_url(self, drive_id: str, item_id: str) -> str:
        """
        Get download URL for a document.

        Args:
            drive_id: Drive ID
            item_id: Item ID

        Returns:
            Download URL for the document
        """
        logger.info("getting_download_url", function="get_download_url",
                   drive_id=drive_id, item_id=item_id)

        try:
            item = await self.get_drive_item(drive_id, item_id)
            download_url = item.get("@microsoft.graph.downloadUrl")

            if not download_url:
                raise ValueError("No download URL available for this item")

            logger.info("download_url_obtained", function="get_download_url",
                       drive_id=drive_id, item_id=item_id)
            return download_url

        except Exception as e:
            logger.error("download_url_failed", function="get_download_url",
                        drive_id=drive_id, item_id=item_id, error=str(e))
            raise

    async def download_file(self, drive_id: str, item_id: str) -> bytes:
        """
        Download file content from SharePoint.

        Args:
            drive_id: Drive ID
            item_id: Item ID

        Returns:
            File content as bytes
        """
        logger.info("downloading_file", function="download_file",
                   drive_id=drive_id, item_id=item_id)

        try:
            download_url = await self.get_download_url(drive_id, item_id)

            client = await self._get_client()
            response = await client.get(download_url)
            response.raise_for_status()

            logger.info("file_downloaded", function="download_file",
                       drive_id=drive_id, item_id=item_id, size=len(response.content))
            return response.content

        except Exception as e:
            logger.error("file_download_failed", function="download_file",
                        drive_id=drive_id, item_id=item_id, error=str(e))
            raise

    async def upload_file(
        self,
        drive_id: str,
        folder_item_id: str,
        filename: str,
        content: bytes
    ) -> Dict[str, Any]:
        """
        Upload file to SharePoint.

        Args:
            drive_id: Drive ID
            folder_item_id: Target folder item ID
            filename: Name for the uploaded file
            content: File content as bytes

        Returns:
            Uploaded item metadata
        """
        logger.info("uploading_file", function="upload_file",
                   drive_id=drive_id, folder_item_id=folder_item_id, filename=filename)

        try:
            upload_url = f"/drives/{drive_id}/items/{folder_item_id}:/{filename}:/content"

            client = await self._get_client()
            response = await client.put(
                upload_url,
                content=content,
                headers={"Content-Type": "application/octet-stream"}
            )
            response.raise_for_status()

            logger.info("file_uploaded", function="upload_file",
                       drive_id=drive_id, filename=filename)
            return response.json()

        except Exception as e:
            logger.error("file_upload_failed", function="upload_file",
                        drive_id=drive_id, filename=filename, error=str(e))
            raise

    async def update_file_metadata(
        self,
        drive_id: str,
        item_id: str,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update file metadata.

        Args:
            drive_id: Drive ID
            item_id: Item ID
            metadata: Metadata fields to update

        Returns:
            Updated item metadata
        """
        logger.info("updating_file_metadata", function="update_file_metadata",
                   drive_id=drive_id, item_id=item_id)

        try:
            response = await self._make_request(
                "PATCH",
                f"/drives/{drive_id}/items/{item_id}",
                json=metadata
            )

            logger.info("file_metadata_updated", function="update_file_metadata",
                       drive_id=drive_id, item_id=item_id)
            return response

        except Exception as e:
            logger.error("file_metadata_update_failed", function="update_file_metadata",
                        drive_id=drive_id, item_id=item_id, error=str(e))
            raise

    async def search_files(
        self,
        site_id: str,
        search_query: str
    ) -> Dict[str, Any]:
        """
        Search for files across SharePoint site.

        Args:
            site_id: Site ID to search within
            search_query: Search query string

        Returns:
            Search results
        """
        logger.info("searching_files", function="search_files",
                   site_id=site_id, query=search_query)

        try:
            response = await self._make_request(
                "GET",
                f"/sites/{site_id}/drive/root/search(q='{search_query}')"
            )

            logger.info("file_search_completed", function="search_files",
                       site_id=site_id, query=search_query,
                       count=len(response.get("value", [])))
            return response

        except Exception as e:
            logger.error("file_search_failed", function="search_files",
                        site_id=site_id, query=search_query, error=str(e))
            raise

    async def get_file_versions(self, drive_id: str, item_id: str) -> Dict[str, Any]:
        """
        Get version history for a file.

        Args:
            drive_id: Drive ID
            item_id: Item ID

        Returns:
            Version history
        """
        logger.info("fetching_file_versions", function="get_file_versions",
                   drive_id=drive_id, item_id=item_id)

        try:
            response = await self._make_request("GET", f"/drives/{drive_id}/items/{item_id}/versions")
            logger.info("file_versions_fetched", function="get_file_versions",
                       drive_id=drive_id, item_id=item_id,
                       count=len(response.get("value", [])))
            return response

        except Exception as e:
            logger.error("file_versions_fetch_failed", function="get_file_versions",
                        drive_id=drive_id, item_id=item_id, error=str(e))
            raise

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


import asyncio
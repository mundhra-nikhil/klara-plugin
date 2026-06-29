"""SharePoint document access service for Klara integration."""

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone
from urllib.parse import quote

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger_with_context
from .graph_client import GraphClient
from .auth_service import microsoft_auth_service

logger = get_logger_with_context()


class SharePointService:
    """
    SharePoint document management service for Klara.

    Provides high-level operations for:
    - Site and library discovery
    - Document access and upload
    - Metadata management
    - Search operations
    """

    def __init__(self, access_token: str):
        """
        Initialize SharePoint service.

        Args:
            access_token: Microsoft Graph access token with SharePoint permissions
        """
        self.access_token = access_token
        self._graph_client: Optional[GraphClient] = None

    async def _get_graph_client(self) -> GraphClient:
        """Get or create Graph client."""
        if self._graph_client is None:
            self._graph_client = GraphClient(access_token=self.access_token)
        return self._graph_client

    async def close(self):
        """Clean up resources."""
        if self._graph_client:
            await self._graph_client.close()

    async def get_accessible_sites(self, search_query: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get all SharePoint sites accessible to the authenticated user.

        Args:
            search_query: Optional search term to filter sites

        Returns:
            List of site dictionaries with id, name, description, url
        """
        logger.info("fetching_accessible_sites", function="get_accessible_sites",
                   search_query=search_query)

        try:
            client = await self._get_graph_client()
            response = await client.get_sites(search=search_query)

            sites = []
            for site in response.get("value", []):
                sites.append({
                    "id": site.get("id"),
                    "name": site.get("name"),
                    "display_name": site.get("displayName", site.get("name")),
                    "description": site.get("description", ""),
                    "web_url": site.get("webUrl"),
                })

            logger.info("accessible_sites_fetched", function="get_accessible_sites",
                       count=len(sites))
            return sites

        except Exception as e:
            logger.error("accessible_sites_fetch_failed", function="get_accessible_sites",
                        error=str(e))
            raise

    async def get_document_libraries(self, site_id: str) -> List[Dict[str, Any]]:
        """
        Get document libraries (drives) for a SharePoint site.

        Args:
            site_id: SharePoint site ID

        Returns:
            List of drive/library dictionaries
        """
        logger.info("fetching_document_libraries", function="get_document_libraries",
                   site_id=site_id)

        try:
            client = await self._get_graph_client()
            response = await client.get_site_drives(site_id)

            libraries = []
            for drive in response.get("value", []):
                # Filter to document libraries only
                if drive.get("driveType") == "documentLibrary":
                    libraries.append({
                        "id": drive.get("id"),
                        "name": drive.get("name"),
                        "description": drive.get("description", ""),
                        "web_url": drive.get("webUrl"),
                        "drive_type": drive.get("driveType"),
                    })

            logger.info("document_libraries_fetched", function="get_document_libraries",
                       site_id=site_id, count=len(libraries))
            return libraries

        except Exception as e:
            logger.error("document_libraries_fetch_failed", function="get_document_libraries",
                        site_id=site_id, error=str(e))
            raise

    async def list_documents(
        self,
        drive_id: str,
        folder_path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List documents in a SharePoint document library.

        Args:
            drive_id: Drive ID
            folder_path: Optional folder path (default: root)

        Returns:
            List of document metadata dictionaries
        """
        logger.info("listing_documents", function="list_documents",
                   drive_id=drive_id, folder_path=folder_path)

        try:
            client = await self._get_graph_client()

            # Use folder path if provided, otherwise use root
            item_id = "root"
            if folder_path:
                # For folder paths, we'd need to resolve the path to an item ID
                # For now, using root as default
                pass

            response = await client.get_drive_items(drive_id, item_id)

            documents = []
            for item in response.get("value", []):
                # Filter to documents only (not folders)
                if item.get("file"):  # Has file property means it's a file
                    documents.append({
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "size": item.get("size", 0),
                        "mime_type": self._extract_mime_type(item.get("name", "")),
                        "created_at": item.get("createdDateTime"),
                        "modified_at": item.get("lastModifiedDateTime"),
                        "web_url": item.get("webUrl"),
                        "drive_id": drive_id,
                    })

            logger.info("documents_listed", function="list_documents",
                       drive_id=drive_id, count=len(documents))
            return documents

        except Exception as e:
            logger.error("document_list_failed", function="list_documents",
                        drive_id=drive_id, error=str(e))
            raise

    async def get_document_metadata(
        self,
        drive_id: str,
        item_id: str
    ) -> Dict[str, Any]:
        """
        Get detailed metadata for a specific document.

        Args:
            drive_id: Drive ID
            item_id: Document item ID

        Returns:
            Document metadata dictionary
        """
        logger.info("fetching_document_metadata", function="get_document_metadata",
                   drive_id=drive_id, item_id=item_id)

        try:
            client = await self._get_graph_client()
            item = await client.get_drive_item(drive_id, item_id)

            metadata = {
                "id": item.get("id"),
                "name": item.get("name"),
                "size": item.get("size", 0),
                "mime_type": self._extract_mime_type(item.get("name", "")),
                "created_at": item.get("createdDateTime"),
                "modified_at": item.get("lastModifiedDateTime"),
                "web_url": item.get("webUrl"),
                "drive_id": drive_id,
                "description": item.get("description", ""),
                "file": item.get("file", {}),
            }

            logger.info("document_metadata_fetched", function="get_document_metadata",
                       drive_id=drive_id, item_id=item_id)
            return metadata

        except Exception as e:
            logger.error("document_metadata_fetch_failed", function="get_document_metadata",
                        drive_id=drive_id, item_id=item_id, error=str(e))
            raise

    async def download_document(
        self,
        drive_id: str,
        item_id: str
    ) -> Tuple[bytes, str]:
        """
        Download document content from SharePoint.

        Args:
            drive_id: Drive ID
            item_id: Document item ID

        Returns:
            Tuple of (document content as bytes, filename)
        """
        logger.info("downloading_document", function="download_document",
                   drive_id=drive_id, item_id=item_id)

        try:
            client = await self._get_graph_client()

            # Get metadata first to get filename
            metadata = await client.get_drive_item(drive_id, item_id)
            filename = metadata.get("name", "document.docx")

            # Download content
            content = await client.download_file(drive_id, item_id)

            logger.info("document_downloaded", function="download_document",
                       drive_id=drive_id, item_id=item_id, size=len(content))
            return content, filename

        except Exception as e:
            logger.error("document_download_failed", function="download_document",
                        drive_id=drive_id, item_id=item_id, error=str(e))
            raise

    async def upload_document(
        self,
        drive_id: str,
        folder_item_id: str,
        filename: str,
        content: bytes
    ) -> Dict[str, Any]:
        """
        Upload document to SharePoint.

        Args:
            drive_id: Drive ID
            folder_item_id: Target folder item ID
            filename: Name for the uploaded file
            content: File content as bytes

        Returns:
            Uploaded document metadata
        """
        logger.info("uploading_document", function="upload_document",
                   drive_id=drive_id, folder_item_id=folder_item_id, filename=filename)

        try:
            client = await self._get_graph_client()
            result = await client.upload_file(drive_id, folder_item_id, filename, content)

            logger.info("document_uploaded", function="upload_document",
                       drive_id=drive_id, filename=filename)
            return result

        except Exception as e:
            logger.error("document_upload_failed", function="upload_document",
                        drive_id=drive_id, filename=filename, error=str(e))
            raise

    async def search_documents(
        self,
        site_id: str,
        search_query: str,
        file_extensions: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for documents across SharePoint site.

        Args:
            site_id: Site ID to search within
            search_query: Search query string
            file_extensions: Optional list of file extensions to filter (e.g., ['.docx', '.pdf'])

        Returns:
            List of matching documents
        """
        logger.info("searching_documents", function="search_documents",
                   site_id=site_id, query=search_query)

        try:
            client = await self._get_graph_client()
            response = await client.search_files(site_id, search_query)

            documents = []
            for item in response.get("value", []):
                filename = item.get("name", "")
                # Filter by file extension if specified
                if file_extensions:
                    if not any(filename.lower().endswith(ext.lower()) for ext in file_extensions):
                        continue

                documents.append({
                    "id": item.get("id"),
                    "name": filename,
                    "size": item.get("size", 0),
                    "web_url": item.get("webUrl"),
                    "drive_id": item.get("parentReference", {}).get("driveId") if item.get("parentReference") else None,
                })

            logger.info("document_search_completed", function="search_documents",
                       site_id=site_id, query=search_query, count=len(documents))
            return documents

        except Exception as e:
            logger.error("document_search_failed", function="search_documents",
                        site_id=site_id, query=search_query, error=str(e))
            raise

    async def get_document_versions(
        self,
        drive_id: str,
        item_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get version history for a document.

        Args:
            drive_id: Drive ID
            item_id: Document item ID

        Returns:
            List of version dictionaries
        """
        logger.info("fetching_document_versions", function="get_document_versions",
                   drive_id=drive_id, item_id=item_id)

        try:
            client = await self._get_graph_client()
            response = await client.get_file_versions(drive_id, item_id)

            versions = []
            for version in response.get("value", []):
                versions.append({
                    "id": version.get("id"),
                    "last_modified": version.get("lastModifiedDateTime"),
                    "size": version.get("size", 0),
                    "version_label": version.get("version", ""),
                })

            logger.info("document_versions_fetched", function="get_document_versions",
                       drive_id=drive_id, item_id=item_id, count=len(versions))
            return versions

        except Exception as e:
            logger.error("document_versions_fetch_failed", function="get_document_versions",
                        drive_id=drive_id, item_id=item_id, error=str(e))
            raise

    async def create_share_link(
        self,
        drive_id: str,
        item_id: str,
        link_type: str = "view"
    ) -> str:
        """
        Create a sharing link for a document.

        Args:
            drive_id: Drive ID
            item_id: Document item ID
            link_type: Type of link ('view' or 'edit')

        Returns:
            Sharing link URL
        """
        logger.info("creating_share_link", function="create_share_link",
                   drive_id=drive_id, item_id=item_id, link_type=link_type)

        try:
            client = await self._get_graph_client()

            # Create sharing link request
            link_request = {
                "type": link_type,
                "scope": "anonymous"  # Create anonymous link
            }

            response = await client._make_request(
                "POST",
                f"/drives/{drive_id}/items/{item_id}/createLink",
                json=link_request
            )

            share_link = response.get("link", {}).get("webUrl")

            if not share_link:
                raise ValueError("Failed to create share link")

            logger.info("share_link_created", function="create_share_link",
                       drive_id=drive_id, item_id=item_id)
            return share_link

        except Exception as e:
            logger.error("share_link_creation_failed", function="create_share_link",
                        drive_id=drive_id, item_id=item_id, error=str(e))
            raise

    def _extract_mime_type(self, filename: str) -> str:
        """
        Extract MIME type from filename.

        Args:
            filename: File name with extension

        Returns:
            MIME type string
        """
        filename_lower = filename.lower()

        mime_types = {
            ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ".doc": "application/msword",
            ".pdf": "application/pdf",
            ".txt": "text/plain",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
            ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            ".ppt": "application/vnd.ms-powerpoint",
        }

        for ext, mime_type in mime_types.items():
            if filename_lower.endswith(ext):
                return mime_type

        return "application/octet-stream"

    async def get_word_online_edit_url(
        self,
        drive_id: str,
        item_id: str
    ) -> str:
        """
        Get Word Online editing URL for a document.

        Args:
            drive_id: Drive ID
            item_id: Document item ID

        Returns:
            Word Online edit URL
        """
        logger.info("getting_word_online_edit_url", function="get_word_online_edit_url",
                   drive_id=drive_id, item_id=item_id)

        try:
            # Get metadata to construct Word Online URL
            client = await self._get_graph_client()
            item = await client.get_drive_item(drive_id, item_id)

            # Construct Word Online URL
            web_url = item.get("webUrl")
            if web_url:
                # Convert to Word Online edit URL
                word_url = web_url.replace(
                    "sharepoint.com",
                    "wordonline.officeapps.live.com"
                )
                word_url += "?action=edit"
                return word_url

            raise ValueError("Cannot construct Word Online URL")

        except Exception as e:
            logger.error("word_online_url_failed", function="get_word_online_edit_url",
                        drive_id=drive_id, item_id=item_id, error=str(e))
            raise

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


async def get_document_from_sharepoint(
    site_id: str,
    drive_id: str,
    item_id: str,
    access_token: str
) -> bytes:
    """
    Convenience function to retrieve a document from SharePoint via MS Graph.

    Args:
        site_id: SharePoint site ID
        drive_id: Drive ID
        item_id: Document item ID
        access_token: Microsoft Graph access token

    Returns:
        Document content as bytes
    """
    logger.info("sharepoint_document_fetch", function="get_document_from_sharepoint",
               site_id=site_id, drive_id=drive_id, item_id=item_id)

    try:
        sharepoint_service = SharePointService(access_token)
        content, _ = await sharepoint_service.download_document(drive_id, item_id)
        await sharepoint_service.close()

        logger.info("sharepoint_document_fetched", function="get_document_from_sharepoint",
                   site_id=site_id, item_id=item_id, size=len(content))
        return content

    except Exception as e:
        logger.error("sharepoint_document_fetch_failed", function="get_document_from_sharepoint",
                    site_id=site_id, item_id=item_id, error=str(e))
        raise
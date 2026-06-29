"""Storage provider abstraction layer for Klara documents."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path
import os

from src.core.logger import get_logger_with_context

logger = get_logger_with_context()


class StorageProvider(ABC):
    """
    Abstract base class for document storage providers.

    Defines the interface that both local storage and SharePoint storage must implement.
    """

    @abstractmethod
    async def get_document(self, document_id: str) -> Tuple[bytes, str]:
        """
        Retrieve document content and filename.

        Args:
            document_id: Document identifier

        Returns:
            Tuple of (document content as bytes, filename)
        """
        pass

    @abstractmethod
    async def save_document(
        self,
        content: bytes,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save document content.

        Args:
            content: Document content as bytes
            filename: Document filename
            metadata: Optional metadata to store with document

        Returns:
            Document identifier
        """
        pass

    @abstractmethod
    async def update_document(
        self,
        document_id: str,
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update existing document content.

        Args:
            document_id: Document identifier
            content: New document content
            metadata: Optional metadata updates
        """
        pass

    @abstractmethod
    async def delete_document(self, document_id: str) -> None:
        """
        Delete document.

        Args:
            document_id: Document identifier
        """
        pass

    @abstractmethod
    async def get_document_url(self, document_id: str) -> str:
        """
        Get URL for accessing document.

        Args:
            document_id: Document identifier

        Returns:
            URL for document access
        """
        pass

    @abstractmethod
    async def get_document_metadata(self, document_id: str) -> Dict[str, Any]:
        """
        Get document metadata.

        Args:
            document_id: Document identifier

        Returns:
            Document metadata dictionary
        """
        pass

    @abstractmethod
    async def document_exists(self, document_id: str) -> bool:
        """
        Check if document exists.

        Args:
            document_id: Document identifier

        Returns:
            True if document exists, False otherwise
        """
        pass

    @abstractmethod
    def get_storage_type(self) -> str:
        """
        Get storage provider type identifier.

        Returns:
            Storage type string (e.g., 'local', 'sharepoint')
        """
        pass


class LocalStorageProvider(StorageProvider):
    """
    Local file system storage provider.

    Stores documents on local filesystem with document ID-based file organization.
    """

    def __init__(self, base_path: str = "/uploads"):
        """
        Initialize local storage provider.

        Args:
            base_path: Base directory for document storage
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info("local_storage_provider_initialized", function="__init__",
                   base_path=str(base_path))

    def _get_file_path(self, document_id: str) -> Path:
        """Get file path for document ID."""
        return self.base_path / f"{document_id}.docx"

    def _get_metadata_path(self, document_id: str) -> Path:
        """Get metadata file path for document ID."""
        return self.base_path / f"{document_id}.metadata.json"

    async def get_document(self, document_id: str) -> Tuple[bytes, str]:
        """Retrieve document content and filename from local storage."""
        file_path = self._get_file_path(document_id)

        if not await self.document_exists(document_id):
            raise FileNotFoundError(f"Document not found: {document_id}")

        logger.info("local_document_get", function="get_document", document_id=document_id)

        content = file_path.read_bytes()
        filename = f"{document_id}.docx"

        # Try to get original filename from metadata
        metadata_path = self._get_metadata_path(document_id)
        if metadata_path.exists():
            try:
                import json
                metadata = json.loads(metadata_path.read_text())
                original_filename = metadata.get("original_filename")
                if original_filename:
                    filename = original_filename
            except Exception as e:
                logger.warning("failed_to_read_metadata", function="get_document",
                             document_id=document_id, error=str(e))

        return content, filename

    async def save_document(
        self,
        content: bytes,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save document to local storage."""
        import uuid
        import json

        document_id = str(uuid.uuid4())
        file_path = self._get_file_path(document_id)

        logger.info("local_document_save", function="save_document",
                   document_id=document_id, filename=filename)

        # Save document content
        file_path.write_bytes(content)

        # Save metadata
        if metadata is None:
            metadata = {}

        metadata["original_filename"] = filename
        metadata["storage_type"] = "local"
        metadata["created_at"] = datetime.utcnow().isoformat()
        metadata["size"] = len(content)

        metadata_path = self._get_metadata_path(document_id)
        metadata_path.write_text(json.dumps(metadata, indent=2))

        logger.info("local_document_saved", function="save_document",
                   document_id=document_id)
        return document_id

    async def update_document(
        self,
        document_id: str,
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update document in local storage."""
        file_path = self._get_file_path(document_id)

        if not await self.document_exists(document_id):
            raise FileNotFoundError(f"Document not found: {document_id}")

        logger.info("local_document_update", function="update_document",
                   document_id=document_id)

        # Save updated content
        file_path.write_bytes(content)

        # Update metadata if provided
        if metadata:
            metadata_path = self._get_metadata_path(document_id)
            if metadata_path.exists():
                try:
                    import json
                    existing_metadata = json.loads(metadata_path.read_text())
                    existing_metadata.update(metadata)
                    existing_metadata["updated_at"] = datetime.utcnow().isoformat()
                    existing_metadata["size"] = len(content)
                    metadata_path.write_text(json.dumps(existing_metadata, indent=2))
                except Exception as e:
                    logger.warning("failed_to_update_metadata", function="update_document",
                                 document_id=document_id, error=str(e))

        logger.info("local_document_updated", function="update_document",
                   document_id=document_id)

    async def delete_document(self, document_id: str) -> None:
        """Delete document from local storage."""
        file_path = self._get_file_path(document_id)
        metadata_path = self._get_metadata_path(document_id)

        logger.info("local_document_delete", function="delete_document",
                   document_id=document_id)

        if file_path.exists():
            file_path.unlink()

        if metadata_path.exists():
            metadata_path.unlink()

        logger.info("local_document_deleted", function="delete_document",
                   document_id=document_id)

    async def get_document_url(self, document_id: str) -> str:
        """Get URL for accessing local document."""
        # For local storage, return API endpoint URL
        return f"/api/v1/documents/{document_id}/file"

    async def get_document_metadata(self, document_id: str) -> Dict[str, Any]:
        """Get document metadata from local storage."""
        metadata_path = self._get_metadata_path(document_id)

        if not metadata_path.exists():
            return {
                "document_id": document_id,
                "storage_type": "local",
            }

        try:
            import json
            metadata = json.loads(metadata_path.read_text())
            metadata["document_id"] = document_id
            return metadata
        except Exception as e:
            logger.error("failed_to_read_metadata", function="get_document_metadata",
                        document_id=document_id, error=str(e))
            return {
                "document_id": document_id,
                "storage_type": "local",
                "error": str(e),
            }

    async def document_exists(self, document_id: str) -> bool:
        """Check if document exists in local storage."""
        file_path = self._get_file_path(document_id)
        return file_path.exists()

    def get_storage_type(self) -> str:
        """Get storage provider type."""
        return "local"


class SharePointStorageProvider(StorageProvider):
    """
    SharePoint storage provider using Microsoft Graph API.

    Stores documents in SharePoint/OneDrive for Business with cloud-native access.
    """

    def __init__(
        self,
        access_token: str,
        site_id: str,
        drive_id: str,
        folder_item_id: str = "root"
    ):
        """
        Initialize SharePoint storage provider.

        Args:
            access_token: Microsoft Graph access token
            site_id: SharePoint site ID
            drive_id: Document library (drive) ID
            folder_item_id: Target folder item ID (default: root)
        """
        from src.services.integrations.microsoft_graph.sharepoint_service import SharePointService

        self.access_token = access_token
        self.site_id = site_id
        self.drive_id = drive_id
        self.folder_item_id = folder_item_id
        self._sharepoint_service: Optional[SharePointService] = None

        logger.info("sharepoint_storage_provider_initialized", function="__init__",
                   site_id=site_id, drive_id=drive_id)

    async def _get_sharepoint_service(self) -> SharePointService:
        """Get or create SharePoint service."""
        if self._sharepoint_service is None:
            self._sharepoint_service = SharePointService(self.access_token)
        return self._sharepoint_service

    async def get_document(self, document_id: str) -> Tuple[bytes, str]:
        """Retrieve document content and filename from SharePoint."""
        logger.info("sharepoint_document_get", function="get_document",
                   document_id=document_id, drive_id=self.drive_id)

        service = await self._get_sharepoint_service()
        content, filename = await service.download_document(self.drive_id, document_id)

        return content, filename

    async def save_document(
        self,
        content: bytes,
        filename: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Save document to SharePoint."""
        logger.info("sharepoint_document_save", function="save_document",
                   filename=filename, drive_id=self.drive_id)

        service = await self._get_sharepoint_service()
        result = await service.upload_document(
            self.drive_id,
            self.folder_item_id,
            filename,
            content
        )

        # Return SharePoint item ID
        item_id = result.get("id")
        logger.info("sharepoint_document_saved", function="save_document",
                   item_id=item_id, filename=filename)
        return item_id

    async def update_document(
        self,
        document_id: str,
        content: bytes,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update document in SharePoint."""
        logger.info("sharepoint_document_update", function="update_document",
                   document_id=document_id, drive_id=self.drive_id)

        service = await self._get_sharepoint_service()

        # In SharePoint, updating means uploading new version
        # Use the existing filename
        item_metadata = await service.get_document_metadata(self.drive_id, document_id)
        filename = item_metadata.get("name", f"{document_id}.docx")

        await service.upload_document(
            self.drive_id,
            self.folder_item_id,
            filename,
            content
        )

        logger.info("sharepoint_document_updated", function="update_document",
                   document_id=document_id)

    async def delete_document(self, document_id: str) -> None:
        """Delete document from SharePoint."""
        logger.info("sharepoint_document_delete", function="delete_document",
                   document_id=document_id, drive_id=self.drive_id)

        service = await self._get_sharepoint_service()

        # SharePoint deletion would be implemented here
        # For now, raise NotImplementedError
        raise NotImplementedError("SharePoint document deletion not yet implemented")

    async def get_document_url(self, document_id: str) -> str:
        """Get URL for accessing SharePoint document."""
        service = await self._get_sharepoint_service()
        metadata = await service.get_document_metadata(self.drive_id, document_id)
        return metadata.get("web_url", "")

    async def get_document_metadata(self, document_id: str) -> Dict[str, Any]:
        """Get document metadata from SharePoint."""
        logger.info("sharepoint_document_metadata", function="get_document_metadata",
                   document_id=document_id, drive_id=self.drive_id)

        service = await self._get_sharepoint_service()
        metadata = await service.get_document_metadata(self.drive_id, document_id)

        # Add storage provider metadata
        metadata["storage_type"] = "sharepoint"
        metadata["document_id"] = document_id
        metadata["site_id"] = self.site_id
        metadata["drive_id"] = self.drive_id

        return metadata

    async def document_exists(self, document_id: str) -> bool:
        """Check if document exists in SharePoint."""
        try:
            service = await self._get_sharepoint_service()
            await service.get_document_metadata(self.drive_id, document_id)
            return True
        except Exception:
            return False

    def get_storage_type(self) -> str:
        """Get storage provider type."""
        return "sharepoint"

    async def get_word_online_url(self, document_id: str) -> str:
        """Get Word Online editing URL for document."""
        service = await self._get_sharepoint_service()
        return await service.get_word_online_edit_url(self.drive_id, document_id)

    async def close(self):
        """Clean up resources."""
        if self._sharepoint_service:
            await self._sharepoint_service.close()


def get_storage_provider_for_document(
    document: Dict[str, Any],
    access_token: Optional[str] = None
) -> StorageProvider:
    """
    Factory function to get appropriate storage provider for a document.

    Args:
        document: Document metadata dictionary
        access_token: Optional access token for SharePoint

    Returns:
        Storage provider instance

    Raises:
        ValueError: If storage type is unsupported or missing required parameters
    """
    storage_type = document.get("storage_type", "local")

    if storage_type == "local":
        return LocalStorageProvider()

    elif storage_type == "sharepoint":
        if not access_token:
            raise ValueError("Access token required for SharePoint storage")

        site_id = document.get("sharepoint_site_id")
        drive_id = document.get("sharepoint_drive_id")
        folder_item_id = document.get("sharepoint_folder_id", "root")

        if not site_id or not drive_id:
            raise ValueError("SharePoint storage requires site_id and drive_id")

        return SharePointStorageProvider(
            access_token=access_token,
            site_id=site_id,
            drive_id=drive_id,
            folder_item_id=folder_item_id
        )

    else:
        raise ValueError(f"Unsupported storage type: {storage_type}")
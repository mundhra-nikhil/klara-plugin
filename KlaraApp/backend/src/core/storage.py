"""Azure Blob Storage abstraction layer."""

from datetime import datetime, timedelta, timezone

from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from src.configs.config import settings


def _get_blob_service_client() -> BlobServiceClient:
    return BlobServiceClient.from_connection_string(settings.azure_storage_connection_string)


async def generate_upload_sas_url(container_name: str, blob_path: str, document_id: str = None) -> str:
    """Generate a SAS URL for uploading a blob."""
    if (
        not settings.azure_storage_connection_string
        or "your-connection-string" in settings.azure_storage_connection_string.lower()
    ):
        base = f"http://localhost:8000/api/v1/documents/upload-local?container={container_name}&blob_path={blob_path}"
        if document_id:
            base += f"&document_id={document_id}"
        return base
    try:
        blob_service = _get_blob_service_client()
        account_name = blob_service.account_name

        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=container_name,
            blob_name=blob_path,
            permission=BlobSasPermissions(write=True, create=True),
            expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        return f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_path}?{sas_token}"
    except Exception:
        base = f"http://localhost:8000/api/v1/documents/upload-local?container={container_name}&blob_path={blob_path}"
        if document_id:
            base += f"&document_id={document_id}"
        return base


async def generate_download_sas_url(container_name: str, blob_path: str) -> str:
    """Generate a SAS URL for downloading a blob."""
    if (
        not settings.azure_storage_connection_string
        or "your-connection-string" in settings.azure_storage_connection_string.lower()
    ):
        return f"https://mockstorage.blob.core.windows.net/{container_name}/{blob_path}?mock_sas"
    try:
        blob_service = _get_blob_service_client()
        account_name = blob_service.account_name

        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=container_name,
            blob_name=blob_path,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        return f"https://{account_name}.blob.core.windows.net/{container_name}/{blob_path}?{sas_token}"
    except Exception:
        return f"https://mockstorage.blob.core.windows.net/{container_name}/{blob_path}?mock_sas"

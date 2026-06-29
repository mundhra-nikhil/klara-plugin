import msal
import httpx
import logging
from typing import List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from src.configs.config import settings
from src.services.config.system_config_service import system_config_service

logger = logging.getLogger(__name__)

class SharePointService:
    async def _get_credentials(self, db: AsyncSession) -> Tuple[str, str, str]:
        # Try DB first
        config = await system_config_service.get_config(db, "ms365_integration")
        if config and config.value:
            t = config.value.get("tenantId", "")
            c = config.value.get("clientId", "")
            s = config.value.get("clientSecret", "")
            if t and c and s:
                return t, c, s
                
        # Fallback to .env
        t = settings.microsoft_tenant_id
        c = settings.microsoft_client_id
        s = settings.microsoft_client_secret
        
        # If they are dummy values from default .env, ignore them
        if t == "your-tenant-id" or c == "your-client-id":
            return "", "", ""
            
        return t, c, s

    async def get_access_token(self, db: AsyncSession) -> str:
        tenant_id, client_id, client_secret = await self._get_credentials(db)
        
        if not tenant_id or not client_id or not client_secret:
            return "mock-token"
            
        authority = f"https://login.microsoftonline.com/{tenant_id}"
        app = msal.ConfidentialClientApplication(
            client_id,
            authority=authority,
            client_credential=client_secret,
        )
            
        result = app.acquire_token_silent(["https://graph.microsoft.com/.default"], account=None)
        if not result:
            logger.info("No suitable token exists in cache. Let's get a new one from AAD.")
            result = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
            
        if "access_token" in result:
            return result["access_token"]
        else:
            logger.error(f"Failed to acquire token: {result.get('error')} - {result.get('error_description')}")
            raise Exception("Could not authenticate with Microsoft Graph API. Check your credentials in settings.")

    async def list_files(self, db: AsyncSession, site_id: str) -> List[Dict[str, Any]]:
        """List .doc and .docx files from the given SharePoint site ID."""
        tenant_id, client_id, client_secret = await self._get_credentials(db)
        is_configured = bool(tenant_id and client_id and client_secret)
        
        if not is_configured:
            # Return mock data for UI development if not configured
            return [
                {
                    "id": "mock-1",
                    "name": "MSA_Template_v2.docx",
                    "url": "https://sharepoint.com/docs/msa_template_v2.docx",
                    "size": 1572864,
                    "lastModified": "2026-06-25T10:00:00Z"
                },
                {
                    "id": "mock-2",
                    "name": "Vendor_Agreement_Draft.docx",
                    "url": "https://sharepoint.com/docs/vendor_agreement.docx",
                    "size": 524288,
                    "lastModified": "2026-06-26T08:30:00Z"
                },
                {
                    "id": "mock-3",
                    "name": "Q3_Financial_Report.docx",
                    "url": "https://sharepoint.com/docs/q3_report.docx",
                    "size": 3145728,
                    "lastModified": "2026-06-20T14:15:00Z"
                }
            ]

        token = await self.get_access_token(db)
        headers = {"Authorization": f"Bearer {token}"}
        
        # In a real implementation, you'd want to query a specific document library.
        # Here we query the default drive of the site, searching for Word documents.
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/root/search(q='.docx')"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            if response.status_code >= 400:
                error_body = response.text
                raise Exception(f"Microsoft Graph API Error {response.status_code}: {error_body}")
            response.raise_for_status()
            data = response.json()
            
            files = []
            for item in data.get("value", []):
                # Filter strictly for Word docs if search was loose
                if item.get("name", "").endswith((".docx", ".doc")):
                    files.append({
                        "id": item["id"],
                        "name": item["name"],
                        "url": item.get("webUrl", ""),
                        "size": item.get("size", 0),
                        "lastModified": item.get("lastModifiedDateTime", "")
                    })
            return files

    async def download_file(self, db: AsyncSession, site_id: str, file_id: str) -> bytes:
        """Download file bytes from Graph API."""
        tenant_id, client_id, client_secret = await self._get_credentials(db)
        is_configured = bool(tenant_id and client_id and client_secret)
        
        if not is_configured:
            # Return dummy bytes in mock mode
            return b"MOCK_WORD_DOCUMENT_BYTES"
            
        token = await self.get_access_token(db)
        headers = {"Authorization": f"Bearer {token}"}
        
        url = f"https://graph.microsoft.com/v1.0/sites/{site_id}/drive/items/{file_id}/content"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            return response.content

sharepoint_service = SharePointService()

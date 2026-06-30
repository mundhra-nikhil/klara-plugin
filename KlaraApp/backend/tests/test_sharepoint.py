import pytest
from unittest.mock import patch, MagicMock
from src.services.sharepoint_service import SharePointService

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_msal_client():
    with patch('src.services.sharepoint_service.msal.ConfidentialClientApplication') as mock:
        yield mock

@pytest.mark.asyncio
async def test_sharepoint_service_mock_mode_when_unconfigured(mock_db):
    mock_db.execute.return_value.scalar_one_or_none.return_value = None
    with patch('src.services.config.system_config_service.SystemConfigService.get_config', return_value=None):
        service = SharePointService()
        tenant_id, client_id, client_secret = await service._get_credentials(mock_db)
        
        # If .env is unconfigured (your-tenant-id), it returns empty
        # Wait, get_credentials will fall back to .env settings. 
        # Since it returns "", "", "" for unconfigured .env:
        assert tenant_id == ""
        assert client_id == ""

@pytest.mark.asyncio
async def test_sharepoint_service_live_mode_when_configured(mock_db, mock_msal_client):
    mock_config = MagicMock()
    mock_config.value = {
        'tenantId': 'real-tenant',
        'clientId': 'real-client',
        'clientSecret': 'real-secret'
    }
    with patch('src.services.config.system_config_service.SystemConfigService.get_config', return_value=mock_config):
        service = SharePointService()
        tenant_id, client_id, client_secret = await service._get_credentials(mock_db)
        
        assert tenant_id == 'real-tenant'
        assert client_id == 'real-client'
        
        # Test get_access_token
        mock_msal_client.return_value.acquire_token_silent.return_value = None
        mock_msal_client.return_value.acquire_token_for_client.return_value = {"access_token": "token"}
        token = await service.get_access_token(mock_db)
        assert token == "token"

@pytest.mark.asyncio
async def test_get_sites_returns_mock_data_in_mock_mode(mock_db):
    with patch('src.services.config.system_config_service.SystemConfigService.get_config', return_value=None):
        service = SharePointService()
        files = await service.list_files(mock_db, "site_id")
        assert len(files) == 3
        assert files[0]["name"] == "MSA_Template_v2.docx"


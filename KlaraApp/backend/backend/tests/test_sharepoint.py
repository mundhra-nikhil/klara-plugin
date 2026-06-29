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

def test_sharepoint_service_mock_mode_when_unconfigured(mock_db):
    # Setup db to return None for MS365 config
    mock_db.query().filter().first.return_value = None
    
    service = SharePointService(db=mock_db)
    
    # Assert
    assert service.tenant_id == 'mock-tenant'
    assert service.client_id == 'mock-client'
    assert service.is_mock_mode is True

def test_sharepoint_service_live_mode_when_configured(mock_db, mock_msal_client):
    # Setup db to return valid MS365 config
    mock_config = MagicMock()
    mock_config.config_value = {
        'tenant_id': 'real-tenant',
        'client_id': 'real-client',
        'client_secret': 'real-secret'
    }
    mock_db.query().filter().first.return_value = mock_config
    
    service = SharePointService(db=mock_db)
    
    # Assert
    assert service.tenant_id == 'real-tenant'
    assert service.client_id == 'real-client'
    assert service.is_mock_mode is False
    mock_msal_client.assert_called_once_with(
        "real-client",
        authority="https://login.microsoftonline.com/real-tenant",
        client_credential="real-secret"
    )

@pytest.mark.asyncio
async def test_get_sites_returns_mock_data_in_mock_mode(mock_db):
    mock_db.query().filter().first.return_value = None
    service = SharePointService(db=mock_db)
    
    sites = await service.get_sites("test query")
    assert len(sites) == 2
    assert sites[0]["name"] == "Legal Department (Mock)"

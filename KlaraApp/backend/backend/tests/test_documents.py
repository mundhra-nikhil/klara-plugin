"""Document submission & lifecycle tests."""

import pytest
import uuid
from app import app
from src.utils.dependencies import get_current_user
from src.models.dto.schemas.auth import UserClaims
from src.models.enum.user_role import UserRole
from src.models.enum.document_type import DocumentType

def set_auth(role: UserRole):
    mock_user = UserClaims(
        id=uuid.uuid4(),
        email=f"test_{role.value}@epiqglobal.com",
        display_name=f"Test {role.value.capitalize()}",
        role=role.value,
        azure_ad_oid="mock-oid",
        department_id=None
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    return mock_user

def clear_auth():
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_list_clients_all_roles(client):
    roles = [
        UserRole.INTAKE_COORDINATOR,
        UserRole.DOC_SPECIALIST,
        UserRole.QC_OPERATOR,
        UserRole.PROOFREADER,
        UserRole.MANAGER,
        UserRole.ADMIN
    ]
    for role in roles:
        set_auth(role)
        try:
            response = await client.get("/api/v1/clients")
            assert response.status_code == 200, f"Role {role} failed to list clients"
            data = response.json()
            assert isinstance(data, list)
        finally:
            clear_auth()


@pytest.mark.asyncio
async def test_list_departments_all_roles(client):
    roles = [
        UserRole.INTAKE_COORDINATOR,
        UserRole.DOC_SPECIALIST,
        UserRole.QC_OPERATOR,
        UserRole.PROOFREADER,
        UserRole.MANAGER,
        UserRole.ADMIN
    ]
    for role in roles:
        set_auth(role)
        try:
            response = await client.get("/api/v1/config/departments")
            assert response.status_code == 200, f"Role {role} failed to list departments"
            data = response.json()
            assert isinstance(data, list)
        finally:
            clear_auth()


@pytest.mark.asyncio
async def test_list_documents_all_roles(client):
    roles = [
        UserRole.INTAKE_COORDINATOR,
        UserRole.DOC_SPECIALIST,
        UserRole.QC_OPERATOR,
        UserRole.PROOFREADER,
        UserRole.MANAGER,
        UserRole.ADMIN
    ]
    for role in roles:
        set_auth(role)
        try:
            response = await client.get("/api/v1/documents")
            assert response.status_code == 200, f"Role {role} failed to list documents"
            data = response.json()
            assert "data" in data
            assert isinstance(data["data"], list)
        finally:
            clear_auth()


@pytest.mark.asyncio
async def test_create_document_all_roles(client):
    # Fetch a client ID first
    set_auth(UserRole.ADMIN)
    try:
        clients_res = await client.get("/api/v1/clients")
        assert clients_res.status_code == 200
        clients = clients_res.json()
        assert len(clients) > 0, "No clients seeded"
        client_id = clients[0]["id"]
    finally:
        clear_auth()

    roles = [
        UserRole.INTAKE_COORDINATOR,
        UserRole.DOC_SPECIALIST,
        UserRole.QC_OPERATOR,
        UserRole.PROOFREADER,
        UserRole.MANAGER,
        UserRole.ADMIN
    ]

    for role in roles:
        set_auth(role)
        try:
            payload = {
                "client_id": client_id,
                "title": f"Test Document by {role.value}",
                "document_type": DocumentType.FORMATTING.value,
                "priority": 3,
                "deadline": None,
                "metadata": {"test": True}
            }
            response = await client.post("/api/v1/documents", json=payload)
            assert response.status_code == 202, f"Role {role} failed to create document"
            data = response.json()
            assert "id" in data
            assert data["status"] in ["received", "pending", "RECEIVED", "PENDING"]
        finally:
            clear_auth()

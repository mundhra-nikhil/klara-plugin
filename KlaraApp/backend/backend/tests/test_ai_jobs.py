"""AI Analysis job submission and lifecycle tests."""

import pytest
import uuid
from app import app
from src.utils.dependencies import get_current_user
from src.models.dto.schemas.auth import UserClaims
from src.models.enum.user_role import UserRole
from src.models.enum.document_type import DocumentType
from src.models.enum.job_type import AIJobType

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
async def test_create_ai_job_all_roles(client):
    # Fetch client & submit document first
    set_auth(UserRole.ADMIN)
    try:
        clients_res = await client.get("/api/v1/clients")
        assert clients_res.status_code == 200
        clients = clients_res.json()
        assert len(clients) > 0, "No clients seeded"
        client_id = clients[0]["id"]

        doc_payload = {
            "client_id": client_id,
            "title": "Test Doc for AI Job",
            "document_type": DocumentType.FORMATTING.value,
            "priority": 3,
            "deadline": None,
            "metadata": {}
        }
        doc_res = await client.post("/api/v1/documents", json=doc_payload)
        assert doc_res.status_code == 202
        document_id = doc_res.json()["id"]
    finally:
        clear_auth()

    # Trigger jobs with each allowed role
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
            job_payload = {
                "document_id": document_id,
                "job_type": AIJobType.FORMATTING_CHECK.value
            }
            response = await client.post("/api/v1/ai-jobs", json=job_payload)
            assert response.status_code == 202, f"Role {role} failed to trigger AI job"
            data = response.json()
            assert "id" in data
            assert data["document_id"] == document_id
            assert data["status"] in ["pending", "running", "completed"]
        finally:
            clear_auth()

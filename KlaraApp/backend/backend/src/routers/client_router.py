from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.db_setup import get_db
from src.utils.dependencies import require_roles, get_current_user
from src.models.enum.user_role import UserRole
from src.services.clients import client_service
from src.models.dto.schemas.clients import (
    ClientResponse,
    CreateClientRequest,
    UpdateClientRequest,
)
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()
router = APIRouter()


@router.get("", response_model=list[ClientResponse])
async def list_clients(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all clients."""
    logger.info("Entering list_clients", function="list_clients", action="entry")
    result = await client_service.list_clients(db)
    logger.info("Exiting list_clients", function="list_clients", action="exit", client_count=len(result))
    return result


@router.post("", response_model=ClientResponse, status_code=201)
async def create_client(
    body: CreateClientRequest,
    current_user=Depends(require_roles([UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new client."""
    logger.info("Entering create_client", function="create_client", action="entry", client_name=body.name)
    result = await client_service.create_client(db, body, actor_id=current_user.id)
    logger.info("Exiting create_client", function="create_client", action="exit", client_id=str(result.id))
    return result


@router.get("/{client_id}", response_model=ClientResponse)
async def get_client(
    client_id: UUID,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve client details."""
    logger.info("Entering get_client", function="get_client", action="entry", client_id=str(client_id))
    result = await client_service.get_client(db, client_id)
    logger.info("Exiting get_client", function="get_client", action="exit", client_id=str(client_id))
    return result


@router.put("/{client_id}", response_model=ClientResponse)
async def update_client(
    client_id: UUID,
    body: UpdateClientRequest,
    current_user=Depends(require_roles([UserRole.ADMIN, UserRole.MANAGER, UserRole.INTAKE_COORDINATOR])),
    db: AsyncSession = Depends(get_db),
):
    """Update client details."""
    logger.info("Entering update_client", function="update_client", action="entry", client_id=str(client_id))
    result = await client_service.update_client(db, client_id, body, actor_id=current_user.id)
    logger.info("Exiting update_client", function="update_client", action="exit", client_id=str(client_id))
    return result


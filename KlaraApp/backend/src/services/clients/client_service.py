"""Client CRUD and blob container initialization service."""

from uuid import UUID
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.dao.client import Client
from src.models.enum.job_status import AuditAction, ActorType
from src.utils.audit_helpers import create_audit_log
from src.models.dto.schemas.clients import (
    ClientResponse,
    CreateClientRequest,
    UpdateClientRequest,
)
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()


async def list_clients(db: AsyncSession) -> List[ClientResponse]:
    logger.info("Entering list_clients", function="list_clients", action="entry")
    stmt = select(Client).where(Client.is_active == True).order_by(Client.name)
    result = await db.execute(stmt)
    clients = result.scalars().all()
    logger.info("Exiting list_clients", function="list_clients", action="exit", client_count=len(clients))
    return [ClientResponse.model_validate(c) for c in clients]


async def create_client(
    db: AsyncSession,
    body: CreateClientRequest,
    actor_id: UUID,
) -> ClientResponse:
    logger.info("Entering create_client", function="create_client", action="entry", client_name=body.name, actor_id=str(actor_id))
    
    logger.info("Creating client record", function="create_client", step="create_record")
    client = Client(
        name=body.name,
        code=body.code,
        blob_container_name=body.blob_container_name,
        qa_rule_profile=body.qa_rule_profile or {},
    )
    db.add(client)
    await db.flush()
    logger.info("Client created", function="create_client", step="client_created", client_id=str(client.id))

    logger.info("Creating audit log", function="create_client", step="audit_log")
    await create_audit_log(
        db,
        entity_type="clients",
        entity_id=client.id,
        action=AuditAction.CREATE,
        actor_id=actor_id,
        actor_type=ActorType.HUMAN,
        new_values={"name": body.name, "code": body.code},
    )

    logger.info("Exiting create_client", function="create_client", action="exit", client_id=str(client.id))
    return ClientResponse.model_validate(client)


async def get_client(db: AsyncSession, client_id: UUID) -> ClientResponse:
    logger.info("Entering get_client", function="get_client", action="entry", client_id=str(client_id))
    client = await db.get(Client, client_id)
    if not client:
        from src.utils.dependencies import NotFoundError
        raise NotFoundError(f"Client {client_id} not found")
    logger.info("Exiting get_client", function="get_client", action="exit", client_id=str(client_id))
    return ClientResponse.model_validate(client)


async def update_client(
    db: AsyncSession,
    client_id: UUID,
    body: UpdateClientRequest,
    actor_id: UUID,
) -> ClientResponse:
    logger.info("Entering update_client", function="update_client", action="entry", client_id=str(client_id), actor_id=str(actor_id))
    client = await db.get(Client, client_id)
    if not client:
        from src.utils.dependencies import NotFoundError
        raise NotFoundError(f"Client {client_id} not found")

    old_values = {}
    new_values = {}
    for field, value in body.model_dump(exclude_unset=True).items():
        old_val = getattr(client, field)
        old_values[field] = old_val
        new_values[field] = value
        setattr(client, field, value)

    if new_values:
        await create_audit_log(
            db,
            entity_type="clients",
            entity_id=client.id,
            action=AuditAction.UPDATE,
            actor_id=actor_id,
            actor_type=ActorType.HUMAN,
            old_values=old_values,
            new_values=new_values,
        )
    await db.flush()
    # `updated_at` is server-side (onupdate=func.now()); flushing a real change
    # expires it, so refresh before serializing or pydantic triggers lazy IO
    # outside the async greenlet (MissingGreenlet -> 500).
    await db.refresh(client)
    logger.info("Exiting update_client", function="update_client", action="exit", client_id=str(client.id))
    return ClientResponse.model_validate(client)


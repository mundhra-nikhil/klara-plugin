from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.repositories.db_setup import get_db
from src.utils.dependencies import require_roles, get_current_user
from src.models.enum.user_role import UserRole
from src.services.config import validation_rule_service, department_service
from src.models.dto.schemas.responses import (
    ValidationRuleResponse,
    CreateValidationRuleRequest,
    UpdateValidationRuleRequest,
    DepartmentResponse,
    CreateDepartmentRequest,
)
from src.models.dto.schemas.system_config import SystemConfigResponse, SetSystemConfigRequest
from src.services.config.system_config_service import system_config_service
from src.core.logger import get_logger_with_context

logger = get_logger_with_context()
router = APIRouter()


@router.get("/poc-rules")
async def list_poc_rules(
    current_user=Depends(get_current_user),
):
    """Return the canonical 18-rule POC Checklist for Formatting Pleadings.

    Serves the single source of truth (src/services/ai_jobs/poc_rules.py) so the
    Rules dashboard can display the real checklist the AI engine evaluates —
    grouped by the three engine tracks — for manual verification. Available to
    any authenticated user since all roles view the Rules screen."""
    from src.services.ai_jobs.poc_rules import rules_for_api

    return {"data": rules_for_api()}


@router.get("/validation-rules", response_model=List[ValidationRuleResponse])
async def list_validation_rules(
    client_id: Optional[UUID] = Query(None),
    current_user=Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN, UserRole.INTAKE_COORDINATOR])),
    db: AsyncSession = Depends(get_db),
):
    """List client-specific QA validation rules."""
    logger.info("Entering list_validation_rules", function="list_validation_rules", action="entry", client_id=str(client_id) if client_id else None)
    result = await validation_rule_service.list_validation_rules(db, client_id=client_id)
    logger.info("Exiting list_validation_rules", function="list_validation_rules", action="exit", rule_count=len(result))
    return result


@router.post("/validation-rules", response_model=ValidationRuleResponse, status_code=201)
async def create_validation_rule(
    body: CreateValidationRuleRequest,
    current_user=Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN, UserRole.INTAKE_COORDINATOR])),
    db: AsyncSession = Depends(get_db),
):
    """Create a client-specific QA validation rule."""
    logger.info("Entering create_validation_rule", function="create_validation_rule", action="entry", rule_name=body.name)
    result = await validation_rule_service.create_validation_rule(db, body, actor_id=current_user.id)
    logger.info("Exiting create_validation_rule", function="create_validation_rule", action="exit", rule_id=str(result.id))
    return result


@router.put("/validation-rules/{rule_id}", response_model=ValidationRuleResponse)
async def update_validation_rule(
    rule_id: UUID,
    body: UpdateValidationRuleRequest,
    current_user=Depends(require_roles([UserRole.MANAGER, UserRole.ADMIN, UserRole.INTAKE_COORDINATOR])),
    db: AsyncSession = Depends(get_db),
):
    """Update a client-specific QA validation rule."""
    logger.info("Entering update_validation_rule", function="update_validation_rule", action="entry", rule_id=str(rule_id))
    result = await validation_rule_service.update_validation_rule(db, rule_id, body, actor_id=current_user.id)
    logger.info("Exiting update_validation_rule", function="update_validation_rule", action="exit", rule_id=str(rule_id))
    return result


# --- Departments ---

@router.get("/departments", response_model=List[DepartmentResponse])
async def list_departments(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all departments."""
    logger.info("Entering list_departments", function="list_departments", action="entry")
    result = await department_service.list_departments(db)
    logger.info("Exiting list_departments", function="list_departments", action="exit", department_count=len(result))
    return result


@router.post("/departments", response_model=DepartmentResponse, status_code=201)
async def create_department(
    body: CreateDepartmentRequest,
    current_user=Depends(require_roles([UserRole.ADMIN])),
    db: AsyncSession = Depends(get_db),
):
    """Create a new department."""
    logger.info("Entering create_department", function="create_department", action="entry", department_name=body.name)
    result = await department_service.create_department(db, body, actor_id=current_user.id)
    logger.info("Exiting create_department", function="create_department", action="exit", department_id=str(result.id))
    return result


# --- System Config ---

@router.get("/ms365", response_model=SystemConfigResponse)
async def get_ms365_config(
    db: AsyncSession = Depends(get_db),
):
    """Get MS365 integration configuration."""
    logger.info("Entering get_ms365_config")
    from fastapi import HTTPException
    config = await system_config_service.get_config(db, "ms365_integration")
    if not config:
        raise HTTPException(status_code=404, detail="MS365 config not found")
    return config

@router.post("/ms365", response_model=SystemConfigResponse)
async def set_ms365_config(
    body: SetSystemConfigRequest,
    db: AsyncSession = Depends(get_db),
):
    """Set MS365 integration configuration."""
    logger.info("Entering set_ms365_config")
    result = await system_config_service.set_config(db, "ms365_integration", body)
    return result

@router.delete("/ms365")
async def delete_ms365_config(
    db: AsyncSession = Depends(get_db),
):
    """Delete MS365 integration configuration."""
    logger.info("Entering delete_ms365_config")
    from fastapi import HTTPException
    success = await system_config_service.delete_config(db, "ms365_integration")
    if not success:
        raise HTTPException(status_code=404, detail="MS365 config not found")
    return {"message": "MS365 config deleted successfully"}


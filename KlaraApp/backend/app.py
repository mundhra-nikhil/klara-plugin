"""FastAPI entry point — router registration and application setup."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from src.configs.config import settings
from src.repositories.db_setup import engine
from src.core.state import init_state, cleanup_state
from src.core.logger import setup_logging, get_logger_with_context
from src.utils.middleware.correlation_id import CorrelationIdMiddleware
from src.utils.middleware.audit_middleware import AuditMiddleware
from src.utils.middleware.error_handlers import http_exception_handler, generic_exception_handler
from src.routers.auth_router import router as auth_router
from src.routers.document_router import router as document_router
from src.routers.ai_job_router import router as ai_job_router
from src.routers.qc_router import router as qc_router
from src.routers.user_router import router as user_router
from src.routers.admin_router import router as admin_router
from src.routers.report_router import router as report_router
from src.routers.config_router import router as config_router
from src.routers.client_router import router as client_router
from src.routers.word_features_router import router as word_features_router
from src.routers.sharepoint_router import router as sharepoint_router

logger = get_logger_with_context()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Application startup initiated")
    setup_logging()
    logger.info("Logging configured")
    await init_state()
    logger.info("Application state initialized")
    yield
    # Shutdown
    logger.info("Application shutdown initiated")
    await cleanup_state()
    logger.info("Application state cleaned up")
    await engine.dispose()
    logger.info("Database engine disposed")


app = FastAPI(
    title="EPIQ GRSS AI-Driven QA/QC Platform",
    description="Backend API for document processing with AI-powered quality assurance",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=f"{settings.api_v1_prefix}/docs",
    redoc_url=f"{settings.api_v1_prefix}/redoc",
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
)

# Exception handlers
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Middleware (order matters — outermost first)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuditMiddleware)
app.add_middleware(CorrelationIdMiddleware)

# Register routers
app.include_router(auth_router, prefix=f"{settings.api_v1_prefix}/auth", tags=["Auth"])
app.include_router(document_router, prefix=f"{settings.api_v1_prefix}/documents", tags=["Documents"])
app.include_router(ai_job_router, prefix=f"{settings.api_v1_prefix}/ai-jobs", tags=["AI Jobs"])
app.include_router(qc_router, prefix=f"{settings.api_v1_prefix}/qc", tags=["QC"])
app.include_router(client_router, prefix=f"{settings.api_v1_prefix}/clients", tags=["Clients"])
app.include_router(user_router, prefix=f"{settings.api_v1_prefix}/admin/users", tags=["Users"])
app.include_router(admin_router, prefix=f"{settings.api_v1_prefix}/admin", tags=["Admin"])
app.include_router(report_router, prefix=f"{settings.api_v1_prefix}/reports", tags=["Reports"])
app.include_router(config_router, prefix=f"{settings.api_v1_prefix}/config", tags=["Config"])
app.include_router(word_features_router, prefix=f"{settings.api_v1_prefix}", tags=["Word Features"])
app.include_router(sharepoint_router, prefix=f"{settings.api_v1_prefix}/sharepoint", tags=["SharePoint"])


@app.get("/health/live")
async def liveness():
    logger.info("Liveness check", function="liveness", action="check")
    return {"status": "ok"}


@app.get("/health/ready")
async def readiness():
    logger.info("Entering readiness check", function="readiness", action="entry")
    from src.repositories.db_setup import AsyncSessionLocal
    from src.core.state import redis_client
    from sqlalchemy import text

    checks = {}
    try:
        logger.info("Checking database connection", function="readiness", step="check_database")
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
        logger.info("Database check passed", function="readiness", step="database_ok")
    except Exception as e:
        logger.error("Database check failed", function="readiness", step="database_error", error=str(e))
        checks["database"] = f"error: {str(e)}"

    try:
        logger.info("Checking Redis connection", function="readiness", step="check_redis")
        await redis_client.ping()
        checks["redis"] = "ok"
        logger.info("Redis check passed", function="readiness", step="redis_ok")
    except Exception as e:
        logger.error("Redis check failed", function="readiness", step="redis_error", error=str(e))
        checks["redis"] = f"error: {str(e)}"

    all_ok = all(v == "ok" for v in checks.values())
    logger.info("Exiting readiness check", function="readiness", action="exit", status="ok" if all_ok else "degraded", checks=checks)
    return {"status": "ok" if all_ok else "degraded", "checks": checks}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )



"""Periodic tasks (report generation, cleanup)."""

from src.celery_app.celery import app


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Generate daily reports at midnight
    sender.add_periodic_task(
        86400.0,
        generate_daily_reports.s(),
        name='generate-daily-reports',
    )

    # Cleanup expired sessions every hour
    sender.add_periodic_task(
        3600.0,
        cleanup_expired_sessions.s(),
        name='cleanup-expired-sessions',
    )


@app.task
def generate_daily_reports():
    """Generate daily compliance and throughput reports."""
    pass


@app.task
def cleanup_expired_sessions():
    """Clean up expired sessions and tokens from Redis."""
    pass

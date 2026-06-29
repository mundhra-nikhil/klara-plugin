"""Application-wide constants, limits, and enums."""

# API
API_V1_PREFIX = "/api/v1"
MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 20

# File upload
MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024  # 100MB
ALLOWED_MIME_TYPES = [
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]

# AI Jobs
MAX_CONCURRENT_AI_JOBS_PER_CLIENT = 50
AI_JOB_MAX_RETRIES = 3
AI_JOB_RETRY_BACKOFF_MAX = 60

# Cache TTLs (seconds)
SESSION_CACHE_TTL = 900           # 15 min
FINDINGS_CACHE_TTL = 300          # 5 min
CLIENT_RULES_CACHE_TTL = 1800     # 30 min
CHECKLIST_CACHE_TTL = 3600        # 60 min
REPORT_CACHE_TTL = 900            # 15 min
RATE_LIMIT_WINDOW = 60            # 1 min

# Rate limiting
API_RATE_LIMIT_PER_USER = 100     # requests per minute

# Priority levels
PRIORITY_CRITICAL = 1
PRIORITY_HIGH = 2
PRIORITY_NORMAL = 3
PRIORITY_LOW = 4

# Correlation ID header
CORRELATION_ID_HEADER = "X-Correlation-ID"

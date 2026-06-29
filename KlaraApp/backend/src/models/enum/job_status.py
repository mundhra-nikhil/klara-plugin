import enum


class AIJobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class AuditAction(str, enum.Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    AI_CHANGE = "AI_CHANGE"
    STATUS_CHANGE = "STATUS_CHANGE"


class ActorType(str, enum.Enum):
    HUMAN = "human"
    AI_SYSTEM = "ai_system"
    SCHEDULER = "scheduler"


class FindingType(str, enum.Enum):
    FORMATTING = "formatting"
    SPELLING = "spelling"
    CONSISTENCY = "consistency"
    COMPLIANCE = "compliance"
    STYLE = "style"
    METADATA = "metadata"

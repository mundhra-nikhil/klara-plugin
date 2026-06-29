import enum


class UserRole(str, enum.Enum):
    INTAKE_COORDINATOR = "intake_coordinator"
    DOC_SPECIALIST = "doc_specialist"
    QC_OPERATOR = "qc_operator"
    PROOFREADER = "proofreader"
    MANAGER = "manager"
    ADMIN = "admin"

import enum


class DocumentStatus(str, enum.Enum):
    RECEIVED   = "RECEIVED"
    QUEUED     = "QUEUED"
    PROCESSING = "PROCESSING"
    QC_REVIEW  = "QC_REVIEW"
    COMPLETED  = "COMPLETED"
    REJECTED   = "REJECTED"

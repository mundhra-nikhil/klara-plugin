import enum


class AIJobType(str, enum.Enum):
    FORMATTING_CHECK = "formatting_check"
    PROOFREADING = "proofreading"
    COMPLIANCE_AUDIT = "compliance_audit"
    STYLE_VALIDATION = "style_validation"
    PDF_COMPARISON = "pdf_comparison"

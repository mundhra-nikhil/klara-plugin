import enum


class DocumentType(str, enum.Enum):
    PDF_CONVERSION = "pdf_conversion"
    FORMATTING = "formatting"
    PROOFREADING = "proofreading"
    TOA_TOC = "toa_toc"
    COMPARISON = "comparison"
    OTHER = "other"

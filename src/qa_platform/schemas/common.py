from enum import Enum
import uuid


class SourceType(str, Enum):
    PRD = "PRD"
    JIRA = "JIRA"
    OPENAPI = "OPENAPI"
    DESIGN_DOC = "DESIGN_DOC"
    USER_STORY = "USER_STORY"


class RequirementType(str, Enum):
    FUNCTIONAL = "FUNCTIONAL"
    NON_FUNCTIONAL = "NON_FUNCTIONAL"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    ACCESSIBILITY = "ACCESSIBILITY"


class AmbiguitySeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKING = "BLOCKING"


class ProcessingStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8].upper()}"

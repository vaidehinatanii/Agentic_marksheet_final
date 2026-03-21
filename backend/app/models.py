"""Pydantic models for data validation and schema definition."""
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class SubjectStatus(str, Enum):
    """Subject result status."""
    OK = "OK"
    AB = "AB"
    COMPARTMENT = "COMPARTMENT"
    NON_NUMERIC = "NON_NUMERIC"
    UNKNOWN = "UNKNOWN"


class SubjectCategory(str, Enum):
    """Subject category for computation."""
    ENGLISH = "ENGLISH"
    MATH = "MATH"
    SCIENCE = "SCIENCE"
    SOCIAL_SCIENCE = "SOCIAL_SCIENCE"
    SECOND_LANGUAGE = "SECOND_LANGUAGE"
    ADDITIONAL = "ADDITIONAL"
    OTHER = "OTHER"


class ResultStatus(str, Enum):
    """Overall result status."""
    PASS = "PASS"
    COMPARTMENT = "COMPARTMENT"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class SubjectExtract(BaseModel):
    """Raw extracted subject data from OpenAI Vision."""
    subject_name: Optional[str] = None
    obtained_marks: Optional[float] = None
    max_marks: Optional[float] = None
    status: SubjectStatus = SubjectStatus.UNKNOWN


class MarksheetExtract(BaseModel):
    """Complete marksheet extraction schema."""
    student_name: Optional[str] = None
    board: str = "CBSE"
    exam_session: Optional[str] = None
    roll_no: Optional[str] = None
    dob: Optional[str] = None
    school: Optional[str] = None
    result_status: ResultStatus = ResultStatus.UNKNOWN
    seat_no: Optional[str] = None
    subjects: List[SubjectExtract] = Field(default_factory=list)

    @field_validator("subjects")
    @classmethod
    def validate_main_five_subjects(cls, v: List[SubjectExtract]) -> List[SubjectExtract]:
        """Ensure exactly 5 main subjects."""
        if len(v) > 5:
            return v[:5]
        return v


class SubjectNormalized(BaseModel):
    """Normalized subject with category."""
    raw_name: Optional[str] = None
    normalized_name: str
    category: Literal["ENGLISH", "MATH", "SCIENCE", "SOCIAL_SCIENCE", "SECOND_LANGUAGE", "ADDITIONAL", "OTHER"]
    obtained_marks: Optional[float] = None
    max_marks: Optional[float] = None
    status: SubjectStatus = SubjectStatus.UNKNOWN
    needs_review: bool = False


class MarksheetRecord(BaseModel):
    """Complete processed marksheet record."""
    id: str
    filename: str
    status: Literal["pending", "processing", "completed", "error", "needs_review"] = "pending"
    error_message: Optional[str] = None

    # Extracted fields
    student_name: Optional[str] = None
    board: str = "CBSE"
    exam_session: Optional[str] = None
    roll_no: Optional[str] = None
    dob: Optional[str] = None
    school: Optional[str] = None
    result_status: ResultStatus = ResultStatus.UNKNOWN
    seat_no: Optional[str] = None

    # Normalized subjects
    subjects: List[SubjectNormalized] = Field(default_factory=list)

    # Computed fields
    overall_percent: Optional[float] = None
    pcm_percent: Optional[float] = None
    needs_review: bool = False
    review_reasons: List[str] = Field(default_factory=list)


class JobStatus(str, Enum):
    """Batch job lifecycle status."""
    queued = "queued"
    processing = "processing"
    completed = "completed"
    error = "error"
    cancelled = "cancelled"


class Job(BaseModel):
    """Batch processing job."""
    id: str
    status: JobStatus = JobStatus.queued
    progress: float = 0.0
    total_files: int = 0
    completed_files: int = 0
    failed_files: int = 0
    records: List[MarksheetRecord] = Field(default_factory=list)
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


# OpenAI Structured Output Schema
# Note: OpenAI's strict mode requires ALL properties to be in the required array
# We use number/string types and check for validity in application logic
OPENAI_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "student_name": {"type": "string"},
        "board": {"type": "string", "enum": ["CBSE"]},
        "exam_session": {"type": "string"},
        "roll_no": {"type": "string"},
        "dob": {"type": "string"},
        "school": {"type": "string"},
        "result_status": {
            "type": "string",
            "enum": ["PASS", "COMPARTMENT", "FAIL", "UNKNOWN"]
        },
        "seat_no": {"type": "string"},
        "subjects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "subject_name": {"type": "string"},
                    "obtained_marks": {"type": "number"},
                    "max_marks": {"type": "number"},
                    "status": {
                        "type": "string",
                        "enum": ["OK", "AB", "COMPARTMENT", "NON_NUMERIC", "UNKNOWN"]
                    }
                },
                "required": ["subject_name", "status", "obtained_marks", "max_marks"],
                "additionalProperties": False
            }
        }
    },
    "required": ["student_name", "board", "exam_session", "roll_no", "dob", "school", "result_status", "seat_no", "subjects"],
    "additionalProperties": False
}


from typing_extensions import TypedDict


class GraphState(TypedDict):
    """LangGraph workflow state."""
    job_id: str
    files: List[dict]
    images: List[dict]
    extractions: List[dict]
    records: List[MarksheetRecord]
    errors: List[str]
    current_step: str
    progress: float
    needs_interrupt: bool

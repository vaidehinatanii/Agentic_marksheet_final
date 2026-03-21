"""OpenAI client for vision-based marksheet extraction."""
import asyncio
import logging
from typing import Optional, Dict, Any
from openai import AsyncOpenAI, RateLimitError, APITimeoutError, APIStatusError
from app.config import get_settings
from app.models import OPENAI_EXTRACTION_SCHEMA

settings = get_settings()
logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0  # seconds
REQUEST_TIMEOUT = 90.0  # seconds


# System prompt for CBSE marksheet extraction
EXTRACTION_SYSTEM_PROMPT = """You are an expert data extraction system for CBSE Class 10/12 marksheets.

IMPORTANT - READ THE LAYOUT INSTRUCTIONS CAREFULLY:

CBSE MARKSHEET LAYOUT:
1. TOP SECTION: Contains "CENTRAL BOARD OF SECONDARY EDUCATION" header
2. STUDENT NAME is usually at the TOP, often labeled as:
   - "Name of Candidate"
   - "Candidate's Name"
   - "Student Name"
   - Look for this FIRST - it's typically the first or second name field at the top
3. MOTHER'S NAME is usually labeled as:
   - "Mother's Name"
   - "Mother Name"
   - DO NOT extract mother's name as student_name
4. FATHER'S NAME is usually labeled as:
   - "Father's Name"
   - "Parent's Name"
   - DO NOT extract father's name as student_name

STUDENT NAME EXTRACTION RULES:
- Look for labels like "Name of Candidate", "Candidate's Name", "Student Name"
- The student name is usually the FIRST name field at the top left or center
- It is NOT "Mother's Name" or "Father's Name"
- If you see multiple names, the FIRST name shown is typically the student's name
- Student name is usually followed by Father's Name, then Mother's Name

SUBJECT MARKS EXTRACTION RULES:
1. Look for the marks table - usually a grid with columns:
   - Subject Code (optional)
   - Subject Name
   - Theory Marks / Internal Assessment
   - Practical Marks
   - Total Marks (THIS IS WHAT WE NEED)
2. Extract the TOTAL/AGGREGATE marks, NOT theory or practical separately
3. Read each subject name carefully - common CBSE subjects are:
   - ENGLISH, ENGLISH CORE, ENGLISH ELECTIVE
   - MATHEMATICS, MATHEMATICS BASIC, MATHEMATICS STANDARD
   - SCIENCE, SCIENCE & TECHNOLOGY
   - SOCIAL SCIENCE
   - HINDI, HINDI COURSE A, HINDI COURSE B
   - SANSKRIT, FRENCH, GERMAN (second languages)
4. For each subject, read BOTH the obtained marks AND maximum marks
5. Maximum marks are usually at the top of the column (80, 100, etc.)

DATA FORMAT RULES:
- ALL fields must be provided (use "" for text, 0 for numbers if not found)
- student_name: Find "Name of Candidate" or "Candidate's Name" - this is the student's name
- board: Always "CBSE"
- exam_session: Look for "Examination", "Session", "Year of Exam" (e.g., "March 2024")
- roll_no: Look for "Roll No", "Roll Number"
- dob: Look for "Date of Birth", "DOB"
- school: Look for "School Name", "Name of School"
- result_status: Look for "Result", "Qualifying Status" - values are PASS, COMPARTMENT, FAIL
- seat_no: Look for "Seat No" (may not be present)

SUBJECT STATUS CODES:
- OK: Subject has valid marks
- AB: Marked as "AB", "Absent", or "---" (absent for exam)
- COMPARTMENT: Marked as "Compartment", "COMP"
- NON_NUMERIC: Marked as "***", "NA", "N/A", or non-numeric symbols
- UNKNOWN: Cannot determine

NUMERIC VALUES:
- obtained_marks: The marks the student actually got (use 0 if AB/Compartment/missing)
- max_marks: The maximum possible marks (usually 100, 80, 70 - found at top of marks column)

CRITICAL:
- Extract ALL subjects shown (usually 5 or 6 subjects maximum)
- Read marks carefully - 80, 85, 90 are common scores
- Don't confuse subject codes with marks
- Don't confuse grades with marks (we need numeric marks, not grades like A1, B2, etc.)

Return the data strictly according to the provided JSON schema."""

EXTRACTION_USER_PROMPT = """Extract the student information and subject marks from this CBSE marksheet image.

IMPORTANT REMINDERS:
1. Student Name: Look for "Name of Candidate" or "Candidate's Name" - NOT Mother's Name
2. Extract ALL subjects with their TOTAL marks (not theory/practical separately)
3. Read marks carefully - common scores are 80, 85, 90, 95, etc.
4. Include maximum marks for each subject (usually shown at top of column)

Please extract all data now."""


class OpenAIExtractionService:
    """Service for extracting data from marksheets using OpenAI Vision API."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.primary_model = settings.openai_primary_model
        self.fallback_model = settings.openai_fallback_model

    async def extract(
        self,
        image_base64: str,
        use_fallback: bool = False
    ) -> Dict[str, Any]:
        """
        Extract data from marksheet image with retry and exponential backoff.
        Retries on rate limits (429), server errors (5xx), and timeouts.
        Returns structured data as dict.
        """
        model = self.fallback_model if use_fallback else self.primary_model

        for attempt in range(MAX_RETRIES):
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": EXTRACTION_SYSTEM_PROMPT
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": EXTRACTION_USER_PROMPT
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": image_base64
                                    }
                                }
                            ]
                        }
                    ],
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "marksheet_extraction",
                            "strict": True,
                            "schema": OPENAI_EXTRACTION_SCHEMA
                        }
                    },
                    max_tokens=4096,
                    timeout=REQUEST_TIMEOUT
                )

                content = response.choices[0].message.content
                if content:
                    import json
                    return json.loads(content)
                return {}

            except (RateLimitError, APITimeoutError) as e:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(
                    "OpenAI %s on attempt %d/%d, retrying in %.1fs: %s",
                    type(e).__name__, attempt + 1, MAX_RETRIES, delay, e
                )
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(delay)
                else:
                    raise

            except APIStatusError as e:
                if e.status_code >= 500:
                    delay = RETRY_BASE_DELAY * (2 ** attempt)
                    logger.warning(
                        "OpenAI server error %d on attempt %d/%d, retrying in %.1fs",
                        e.status_code, attempt + 1, MAX_RETRIES, delay
                    )
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(delay)
                    else:
                        raise
                else:
                    logger.error("OpenAI client error %d: %s", e.status_code, e)
                    raise

            except Exception as e:
                logger.error("OpenAI extraction error: %s", e)
                raise

        return {}

    async def extract_with_fallback(
        self,
        image_base64: str
    ) -> tuple[Dict[str, Any], bool]:
        """
        Extract with automatic fallback on failure.
        Returns (extracted_data, used_fallback).
        """
        try:
            result = await self.extract(image_base64, use_fallback=False)
            if self._validate_extraction(result):
                return result, False
        except Exception:
            pass

        # Try with fallback model
        try:
            result = await self.extract(image_base64, use_fallback=True)
            return result, True
        except Exception as e:
            logger.error("Fallback extraction also failed: %s", e)
            return {}, True

    def _validate_extraction(self, data: Dict[str, Any]) -> bool:
        """Check if extraction has minimum required fields."""
        if not data:
            return False

        # Must have student name
        if not data.get("student_name"):
            logger.debug("Extraction validation failed: missing student_name")
            return False

        # Must have at least 1 subject
        subjects = data.get("subjects", [])
        if not subjects or len(subjects) < 1:
            logger.debug("Extraction validation failed: no subjects found")
            return False

        return True

    async def close(self):
        """Close the client connection."""
        await self.client.close()


# Singleton instance
_extraction_service: Optional[OpenAIExtractionService] = None


def get_extraction_service() -> OpenAIExtractionService:
    """Get extraction service singleton."""
    global _extraction_service
    if _extraction_service is None:
        _extraction_service = OpenAIExtractionService()
    return _extraction_service

"""Subject normalization and computation services."""
import logging
from typing import Optional, List, Dict
from rapidfuzz import process, fuzz
from app.models import SubjectNormalized, SubjectStatus, MarksheetRecord
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Subject name mappings for fuzzy matching
SUBJECT_MAPPINGS = {
    "ENGLISH": [
        "ENGLISH CORE", "ENGLISH ELECTIVE", "ENGLISH LANGUAGE",
        "ENGLISH", "ENG", "ENGLISH CORE FUNCTIONAL", "ENGLISH COMMUNICATIVE"
    ],
    "MATHEMATICS": [
        "MATHEMATICS", "MATHS", "MATHEMATICS CORE", "MATHEMATICS (CORE)",
        "MATHEMATICS (SCIENCE)", "APPLIED MATHEMATICS", "MATH",
        "MATHEMATICS (041)", "MATH", "MATHEMATICS BASIC"
    ],
    "SCIENCE": [
        "SCIENCE", "SCIENCE AND TECHNOLOGY", "GENERAL SCIENCE",
        "SCIENCE THEORY", "COMBINED SCIENCE"
    ],
    "PHYSICS": [
        "PHYSICS", "PHYSICS (042)", "PHYSICS THEORY", "PHYSICS (SCIENCE)",
        "PHYSICS CORE"
    ],
    "CHEMISTRY": [
        "CHEMISTRY", "CHEMISTRY (043)", "CHEMISTRY THEORY",
        "CHEMISTRY (SCIENCE)", "CHEMISTRY CORE"
    ],
    "BIOLOGY": [
        "BIOLOGY", "BIOLOGY (044)", "BIOLOGY THEORY", "BOTANY",
        "ZOOLOGY", "BIOLOGY (SCIENCE)"
    ],
    "SOCIAL SCIENCE": [
        "SOCIAL SCIENCE", "SOCIAL STUDIES", "SOCIAL STUDY",
        "SST", "SOCIAL SCI", "HISTORY & CIVICS"
    ],
    "HISTORY": [
        "HISTORY", "HISTORY (027)", "INDIAN HISTORY"
    ],
    "GEOGRAPHY": [
        "GEOGRAPHY", "GEOGRAPHY (029)", "PHYSICAL GEOGRAPHY"
    ],
    "CIVICS": [
        "CIVICS", "POLITICAL SCIENCE", "CIVICS AND GOVERNANCE"
    ],
    "POLITICAL SCIENCE": [
        "POLITICAL SCIENCE", "POL SCIENCE", "POLITICAL SCIENCE (028)"
    ],
    "ECONOMICS": [
        "ECONOMICS", "ECONOMICS (030)"
    ],
    "HINDI": [
        "HINDI", "HINDI CORE", "HINDI ELECTIVE", "HINDI LANGUAGE",
        "HINDI COURSE A", "HINDI COURSE B"
    ],
    "SECOND LANGUAGE": [
        "HINDI", "SANSKRIT", "FRENCH", "GERMAN", "SPANISH",
        "URDU", "PUNJABI", "BENGALI", "TAMIL", "TELUGU",
        "MALAYALAM", "KANNADA", "MARATHI", "GUJARATI",
        "REGIONAL LANGUAGE", "MODERN INDIAN LANGUAGE"
    ],
    "SANSKRIT": [
        "SANSKRIT", "SANSKRIT ELECTIVE", "SANSKRIT CORE"
    ],
    "COMPUTER SCIENCE": [
        "COMPUTER SCIENCE", "CS", "COMPUTER SCIENCE (083)",
        "COMPUTER SCIENCE (NEW)", "INFORMATICS PRACTICES",
        "COMPUTER APPLICATIONS", "INFORMATICS", "FOUNDATION OF IT"
    ],
    "ART": [
        "ART", "PAINTING", "DRAWING", "FINE ARTS", "VISUAL ART"
    ],
    "MUSIC": [
        "MUSIC", "VOCAL MUSIC", "INSTRUMENTAL MUSIC", "MUSIC THEORY"
    ],
    "PHYSICAL EDUCATION": [
        "PHYSICAL EDUCATION", "P.E.", "PHYSICAL EDUCATION (048)",
        "HEALTH & PHYSICAL EDUCATION"
    ],
    "WORK EXPERIENCE": [
        "WORK EXPERIENCE", "WORK EDUCATION", "PRE-VOCATIONAL EDUCATION"
    ],
    "GENERAL KNOWLEDGE": [
        "GENERAL KNOWLEDGE", "GK", "CURRENT AFFAIRS"
    ],
    "MORAL SCIENCE": [
        "MORAL SCIENCE", "VALUE EDUCATION", "MORAL EDUCATION"
    ],
    "ACCOUNTANCY": [
        "ACCOUNTANCY", "ACCOUNTS", "ACCOUNTANCY (055)"
    ],
    "BUSINESS STUDIES": [
        "BUSINESS STUDIES", "BUSINESS STUDIES (054)", "BUSINESS"
    ],
    "ADDITIONAL": [
        "ADDITIONAL SUBJECT", "SIXTH SUBJECT", "OPTIONAL SUBJECT",
        "EXTRA SUBJECT", "ADDITIONAL"
    ]
}

# All possible subject names for fuzzy matching
ALL_SUBJECT_NAMES = []
for canonical, variants in SUBJECT_MAPPINGS.items():
    for variant in variants:
        ALL_SUBJECT_NAMES.append((variant, canonical))


def normalize_subject_name(raw_name: Optional[str]) -> tuple[str, str]:
    """
    Normalize subject name to canonical form.
    Returns (normalized_name, category).
    """
    if not raw_name:
        return "UNKNOWN", "OTHER"

    raw_upper = raw_name.upper().strip()

    # Direct match
    for canonical, variants in SUBJECT_MAPPINGS.items():
        if raw_upper in [v.upper() for v in variants]:
            return canonical, _get_category(canonical)

    # Fuzzy match
    result = process.extractOne(
        raw_upper,
        [name for name, _ in ALL_SUBJECT_NAMES],
        scorer=fuzz.WRatio
    )

    if result and result[1] > settings.fuzzy_match_threshold:
        matched_name = result[0]
        # Find canonical name
        for name, canonical in ALL_SUBJECT_NAMES:
            if name.upper() == matched_name.upper():
                return canonical, _get_category(canonical)

    # No match found - try to determine category from name
    logger.debug("No fuzzy match for subject '%s', using raw name", raw_name)
    category = _get_category(raw_name)
    return raw_name, category


def _get_category(subject_name: str) -> str:
    """Get subject category from normalized name."""
    subject_upper = subject_name.upper().strip()

    # Check for English
    if "ENGLISH" in subject_upper or subject_upper in ["ENG", "ENGLISH LANGUAGE"]:
        return "ENGLISH"

    # Check for Mathematics
    if any(x in subject_upper for x in ["MATHEMATICS", "MATH", "MATHS"]):
        return "MATH"

    # Check for Science (Physics, Chemistry, Biology, or general Science)
    if any(x in subject_upper for x in ["SCIENCE", "PHYSICS", "CHEMISTRY", "BIOLOGY"]):
        # If it's specifically Physics/Chem/Bio, still categorize as SCIENCE
        # but the normalized name will preserve the specific subject
        return "SCIENCE"

    # Check for Social Science
    if any(x in subject_upper for x in ["SOCIAL", "HISTORY", "GEOGRAPHY", "CIVICS", "POLITICAL SCIENCE", "ECONOMICS"]):
        return "SOCIAL_SCIENCE"

    # Check for Second Language (Hindi, Sanskrit, regional languages)
    if any(x in subject_upper for x in ["HINDI", "SANSKRIT", "FRENCH", "GERMAN", "SPANISH",
        "URDU", "PUNJABI", "BENGALI", "TAMIL", "TELUGU", "MALAYALAM",
        "KANNADA", "MARATHI", "GUJARATI", "REGIONAL LANGUAGE"]):
        return "SECOND_LANGUAGE"

    # Check for Additional subject
    if "ADDITIONAL" in subject_upper or "SIXTH" in subject_upper or "EXTRA" in subject_upper:
        return "ADDITIONAL"

    # Check for commerce subjects
    if any(x in subject_upper for x in ["ACCOUNTANCY", "ACCOUNTS", "BUSINESS"]):
        return "ADDITIONAL"

    # Check for other common subjects that might be electives
    if any(x in subject_upper for x in ["COMPUTER", "INFORMATICS", "ART", "MUSIC", "PHYSICAL EDUCATION"]):
        return "ADDITIONAL"

    return "OTHER"


def normalize_subjects(extracted_subjects: List[Dict]) -> List[SubjectNormalized]:
    """
    Normalize extracted subjects to SubjectNormalized objects.
    Supports up to 6 subjects (main 5 + additional).
    """
    normalized = []

    for i, subj in enumerate(extracted_subjects[:6]):  # Max 6 subjects (5 main + 1 additional)
        # Get obtained_marks - might be missing key (not just None)
        obtained = subj.get("obtained_marks")
        if obtained is not None and obtained < 0:
            # Negative values indicate missing/invalid
            obtained = None

        max_marks = subj.get("max_marks")
        if max_marks is not None and max_marks <= 0:
            max_marks = None

        status_str = subj.get("status", "UNKNOWN")

        # Parse status
        try:
            status = SubjectStatus(status_str)
        except ValueError:
            status = SubjectStatus.UNKNOWN

        # For AB or COMPARTMENT status, ensure obtained is None
        # OpenAI now returns 0 for missing marks, convert to None based on status
        if status in [SubjectStatus.AB, SubjectStatus.COMPARTMENT, SubjectStatus.NON_NUMERIC]:
            obtained = None
        elif obtained == 0 and status == SubjectStatus.OK:
            # If status is OK but marks are 0, keep it as 0 (actual zero marks)
            pass

        # Determine if needs review
        needs_review = (
            status != SubjectStatus.OK or
            obtained is None or
            max_marks is None
        )

        norm_name, category = normalize_subject_name(subj.get("subject_name"))

        # Mark subjects beyond 5th as additional
        if i >= 5:
            category = "ADDITIONAL"

        normalized.append(SubjectNormalized(
            raw_name=subj.get("subject_name"),
            normalized_name=norm_name,
            category=category,
            obtained_marks=obtained,
            max_marks=max_marks,
            status=status,
            needs_review=needs_review
        ))

    # Ensure at least 6 subjects (5 main + 1 additional placeholder)
    while len(normalized) < 6:
        normalized.append(SubjectNormalized(
            raw_name=None,
            normalized_name="EXTRA",
            category="OTHER",
            obtained_marks=None,
            max_marks=None,
            status=SubjectStatus.UNKNOWN,
            needs_review=True
        ))

    return normalized


def get_core_subjects(subjects: List[SubjectNormalized]) -> Dict[str, Optional[SubjectNormalized]]:
    """
    Extract core subjects: English, Math, Science, Social Science, Second Language.
    Returns dict with keys for each subject type.
    """
    result = {
        "english": None,
        "math": None,
        "science": None,
        "social_science": None,
        "second_language": None
    }

    for subject in subjects:
        cat = subject.category.upper()
        if cat == "ENGLISH" and result["english"] is None:
            result["english"] = subject
        elif cat == "MATH" and result["math"] is None:
            result["math"] = subject
        elif cat == "SCIENCE" and result["science"] is None:
            result["science"] = subject
        elif cat == "SOCIAL_SCIENCE" and result["social_science"] is None:
            result["social_science"] = subject
        elif cat == "SECOND_LANGUAGE" and result["second_language"] is None:
            result["second_language"] = subject

    return result


def compute_best_five_percent(subjects: List[SubjectNormalized]) -> Optional[float]:
    """
    Compute Best of 5 percentage with English, Math, and Science MANDATORY.

    Algorithm:
    1. English, Math, Science MUST be included if available and valid
    2. From remaining subjects, pick top 2 by percentage to complete Best 5
    3. If mandatory subjects are missing/invalid, marks them for review

    Returns None if insufficient data.
    """
    core = get_core_subjects(subjects)

    # Collect valid subjects with their percentages
    valid_subjects = []

    for subject in subjects[:6]:  # Consider all 6 subjects
        if (subject.obtained_marks is not None and
            subject.max_marks is not None and
            subject.max_marks > 0 and
            subject.status == SubjectStatus.OK):

            percent = (subject.obtained_marks / subject.max_marks) * 100
            is_mandatory = subject.category.upper() in ["ENGLISH", "MATH", "SCIENCE"]
            valid_subjects.append({
                "subject": subject,
                "percent": percent,
                "is_mandatory": is_mandatory,
                "category": subject.category.upper()
            })

    if len(valid_subjects) < 5:
        return None

    # Separate mandatory and elective subjects
    mandatory_included = {s["category"]: s for s in valid_subjects if s["is_mandatory"]}
    electives = [s for s in valid_subjects if not s["is_mandatory"]]

    # Sort electives by percentage (descending)
    electives.sort(key=lambda x: x["percent"], reverse=True)

    # Build Best 5: mandatory subjects + top electives
    best_five = list(mandatory_included.values())

    # Add electives until we have 5
    for elective in electives:
        if len(best_five) >= 5:
            break
        best_five.append(elective)

    # If we still don't have 5, we can't compute
    if len(best_five) < 5:
        return None

    # Calculate percentage
    total_obtained = sum(s["subject"].obtained_marks for s in best_five)
    total_max = sum(s["subject"].max_marks for s in best_five)

    if total_max == 0:
        return None

    percent = (total_obtained / total_max) * 100
    return round(percent, 2)


def compute_core_percent(subjects: List[SubjectNormalized]) -> Optional[float]:
    """
    Compute percentage of core subjects (English, Math, Science, Social Science).
    Returns None if any core subject is missing/invalid.
    """
    core = get_core_subjects(subjects)

    # Compute for English, Math, Science, Social Science
    core_subjs = ["english", "math", "science", "social_science"]
    percents = []

    for subj_name in core_subjs:
        subj = core[subj_name]
        if not subj:
            return None
        if (subj.obtained_marks is None or
            subj.max_marks is None or
            subj.max_marks == 0 or
            subj.status != SubjectStatus.OK):
            return None

        subj_percent = (subj.obtained_marks / subj.max_marks) * 100
        percents.append(subj_percent)

    return round(sum(percents) / len(percents), 2)


def compute_review_reasons(subjects: List[SubjectNormalized]) -> List[str]:
    """Generate list of reasons why a record needs review."""
    reasons = []

    for i, subject in enumerate(subjects):
        if subject.normalized_name == "EXTRA":
            continue

        if subject.status != SubjectStatus.OK:
            subj_name = subject.normalized_name or f"Subject {i+1}"
            reasons.append(f"{subj_name}: {subject.status.value}")

        if subject.obtained_marks is None:
            subj_name = subject.normalized_name or f"Subject {i+1}"
            reasons.append(f"{subj_name}: Missing obtained marks")

        if subject.max_marks is None:
            subj_name = subject.normalized_name or f"Subject {i+1}"
            reasons.append(f"{subj_name}: Missing max marks")

    return reasons


def update_record_computations(record: MarksheetRecord) -> MarksheetRecord:
    """
    Update record with computed percentages and review flags.
    Returns the updated record.
    """
    # Compute percentages
    record.overall_percent = compute_best_five_percent(record.subjects)
    record.pcm_percent = compute_core_percent(record.subjects)  # Reuse field for core %

    # Check if needs review
    review_reasons = compute_review_reasons(record.subjects)

    # Add special review reasons
    if record.overall_percent is None:
        review_reasons.append("Cannot compute Best 5 percentage")

    if record.pcm_percent is None:
        core = get_core_subjects(record.subjects)
        if any(core[s] for s in ["english", "math", "science", "social_science"]):
            review_reasons.append("Cannot compute Core (Eng, Math, Sci, SS) percentage")

    record.review_reasons = review_reasons
    record.needs_review = len(review_reasons) > 0

    return record

"""LangGraph nodes for marksheet processing workflow."""
import os
import uuid
import asyncio
import logging
import zipfile
from typing import List, Dict, Any
from pathlib import Path
from app.models import (
    MarksheetRecord, GraphState, SubjectNormalized,
    SubjectStatus, ResultStatus
)
from app.services.preprocess import (
    preprocess_image, image_to_base64, process_file_to_image
)
from app.services.openai_client import get_extraction_service
from app.services.normalize import (
    normalize_subjects, update_record_computations
)
from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


# Temp directory for uploads
TEMP_DIR = Path("/tmp/marksheet_uploads")
TEMP_DIR.mkdir(exist_ok=True)


ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.pdf', '.zip'}


def is_allowed_file(filename: str) -> bool:
    """Check if file type is allowed."""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def validate_zip_safety(zip_path: Path) -> bool:
    """
    Validate zip file for zip slip vulnerability.
    Returns True if safe, False otherwise.
    """
    with zipfile.ZipFile(zip_path, 'r') as zf:
        for info in zf.infolist():
            # Check for path traversal
            if '..' in info.filename or info.filename.startswith('/'):
                return False

            # Check for excessive file size
            if info.file_size > settings.max_upload_size:
                return False

    return True


async def ingest_node(state: GraphState) -> GraphState:
    """
    Ingest uploaded files, extract from ZIP if needed.
    Enumerates valid files for processing.
    """
    files_to_process = []
    errors = []

    for file_info in state["files"]:
        file_path = file_info.get('path')
        filename = file_info.get('name', '')

        if not file_path or not is_allowed_file(filename):
            continue

        file_path = Path(file_path)

        if filename.lower().endswith('.zip'):
            # Process ZIP file
            try:
                if not validate_zip_safety(file_path):
                    errors.append(f"ZIP file {filename} failed security validation")
                    continue

                with zipfile.ZipFile(file_path, 'r') as zf:
                    for info in zf.infolist():
                        member_name = info.filename
                        if is_allowed_file(member_name):
                            # Extract member
                            extract_path = TEMP_DIR / f"{state['job_id']}_{member_name}"
                            with open(extract_path, 'wb') as f:
                                f.write(zf.read(info.filename))

                            files_to_process.append({
                                'name': member_name,
                                'path': str(extract_path),
                                'size': info.file_size
                            })
            except Exception as e:
                errors.append(f"Error processing ZIP {filename}: {str(e)}")

        else:
            # Single file
            files_to_process.append({
                'name': filename,
                'path': str(file_path),
                'size': file_path.stat().st_size if file_path.exists() else 0
            })

    logger.info("Ingest complete: %d files to process", len(files_to_process))
    state["images"] = files_to_process
    state["current_step"] = "canonicalize"
    state["progress"] = 10.0
    state["errors"] = state.get("errors", []) + errors
    return state


async def canonicalize_node(state: GraphState) -> GraphState:
    """
    Convert all files to images (PDF -> image).
    """
    image_list = []
    errors = state.get("errors", [])

    for img_info in state["images"]:
        try:
            file_path = Path(img_info['path'])
            if not file_path.exists():
                errors.append(f"File not found: {img_info['name']}")
                continue

            with open(file_path, 'rb') as f:
                file_bytes = f.read()

            # Convert to image bytes
            image_bytes, mime_type = await process_file_to_image(
                file_bytes,
                img_info['name']
            )

            image_list.append({
                'name': img_info['name'],
                'bytes': image_bytes,
                'mime_type': mime_type
            })

        except Exception as e:
            errors.append(f"Error canonicalizing {img_info['name']}: {str(e)}")

    logger.info("Canonicalize complete: %d images ready", len(image_list))
    state["images"] = image_list
    state["current_step"] = "preprocess"
    state["progress"] = 20.0
    state["errors"] = errors
    return state


async def preprocess_node(state: GraphState) -> GraphState:
    """
    Preprocess images for better OCR.
    Process all images concurrently with semaphore.
    """
    semaphore = asyncio.Semaphore(settings.concurrent_limit)
    images = state["images"]
    errors = state.get("errors", [])

    async def process_one(img: dict) -> dict:
        async with semaphore:
            try:
                processed_bytes = preprocess_image(img['bytes'])
                return {
                    'name': img['name'],
                    'bytes': processed_bytes,
                    'base64': image_to_base64(processed_bytes)
                }
            except Exception as e:
                errors.append(f"Error preprocessing {img['name']}: {str(e)}")
                return img

    tasks = [process_one(img) for img in images]
    processed_images = await asyncio.gather(*tasks)

    state["images"] = [p for p in processed_images if p.get('base64')]
    state["current_step"] = "extract"
    state["progress"] = 30.0
    state["errors"] = errors
    return state


async def extract_node(state: GraphState) -> GraphState:
    """
    Extract data using OpenAI Vision API.
    Process images in batches for better performance.
    """
    extraction_service = get_extraction_service()
    images = state["images"]
    errors = state.get("errors", [])

    batch_size = settings.batch_size
    total_images = len(images)
    all_extractions = []

    # Calculate progress range for this step (30% to 65%)
    progress_start = 30.0
    progress_end = 65.0
    progress_per_batch = (progress_end - progress_start) / max(1, (total_images + batch_size - 1) // batch_size)

    async def extract_one(img: dict) -> dict:
        """Extract data from a single image."""
        try:
            data, used_fallback = await extraction_service.extract_with_fallback(
                img['base64']
            )
            return {
                'name': img['name'],
                'data': data,
                'used_fallback': used_fallback,
                'success': bool(data)
            }
        except Exception as e:
            return {
                'name': img['name'],
                'data': None,
                'used_fallback': False,
                'success': False,
                'error': str(e)
            }

    # Process images in batches
    current_batch = 0
    for i in range(0, total_images, batch_size):
        batch = images[i:i + batch_size]
        current_batch += 1

        # Create tasks for this batch
        tasks = [extract_one(img) for img in batch]

        # Process batch concurrently
        results = await asyncio.gather(*tasks)

        # Collect results
        for result in results:
            all_extractions.append(result)
            if not result.get('success'):
                errors.append(f"Extraction failed for {result['name']}")

        # Update progress after each batch
        batch_progress = progress_start + (current_batch * progress_per_batch)
        state["progress"] = min(batch_progress, progress_end)
        state["current_step"] = f"extract (batch {current_batch}/{(total_images + batch_size - 1) // batch_size})"

    successful = sum(1 for e in all_extractions if e.get("success"))
    logger.info("Extraction complete: %d/%d successful", successful, total_images)
    state["extractions"] = all_extractions
    state["current_step"] = "validate"
    state["progress"] = progress_end
    state["errors"] = errors
    return state


async def validate_and_route_node(state: GraphState) -> GraphState:
    """
    Validate extractions and determine if repair is needed.
    Route to repair or continue based on validation.
    """
    extractions = state["extractions"]

    for extraction in extractions:
        data = extraction.get('data', {})

        # Check if repair needed
        needs_repair_flag = False

        if not data.get('student_name'):
            needs_repair_flag = True

        subjects = data.get('subjects', [])
        if len(subjects) < 5:
            needs_repair_flag = True

        # Check if subjects have max marks
        valid_subjects = 0
        for subj in subjects:
            if subj.get('max_marks') is not None:
                valid_subjects += 1

        if valid_subjects < 3:
            needs_repair_flag = True

        extraction['needs_repair'] = needs_repair_flag

    state["extractions"] = extractions
    state["current_step"] = "normalize"
    state["progress"] = 70.0
    return state


async def repair_node(state: GraphState) -> GraphState:
    """
    Repair failed extractions using fallback model.
    Only processes extractions marked as needs_repair.
    """
    extraction_service = get_extraction_service()
    extractions = state["extractions"]
    images = state["images"]

    for extraction in extractions:
        if extraction.get('needs_repair'):
            # Try extraction with fallback
            try:
                img = next((i for i in images if i['name'] == extraction['name']), None)
                if img:
                    data, _ = await extraction_service.extract_with_fallback(img['base64'])
                    if data:
                        extraction['data'] = data
                        extraction['repaired'] = True
            except Exception:
                extraction['repaired'] = False

    state["extractions"] = extractions
    state["current_step"] = "normalize"
    state["progress"] = 75.0
    return state


async def normalize_node(state: GraphState) -> GraphState:
    """
    Normalize subjects and create MarksheetRecord objects.
    """
    records = []
    extractions = state["extractions"]

    for extraction in extractions:
        data = extraction.get('data', {})

        if not data:
            # Create error record
            record = MarksheetRecord(
                id=str(uuid.uuid4()),
                filename=extraction['name'],
                status="error",
                error_message="Extraction failed - no data returned"
            )
            records.append(record)
            continue

        # Normalize subjects
        raw_subjects = data.get('subjects', [])
        normalized_subjects = normalize_subjects(raw_subjects)

        # Parse result status
        result_status_str = data.get('result_status', 'UNKNOWN')
        try:
            result_status = ResultStatus(result_status_str)
        except ValueError:
            result_status = ResultStatus.UNKNOWN

        # Create record
        record = MarksheetRecord(
            id=str(uuid.uuid4()),
            filename=extraction['name'],
            status="completed" if not extraction.get('needs_repair') else "needs_review",
            student_name=data.get('student_name'),
            board=data.get('board', 'CBSE'),
            exam_session=data.get('exam_session'),
            roll_no=data.get('roll_no'),
            dob=data.get('dob'),
            school=data.get('school'),
            result_status=result_status,
            seat_no=data.get('seat_no'),
            subjects=normalized_subjects
        )

        # Compute percentages
        record = update_record_computations(record)

        records.append(record)

    completed_count = sum(1 for r in records if r.status == "completed")
    review_count = sum(1 for r in records if r.status == "needs_review")
    logger.info("Normalize complete: %d completed, %d needs review", completed_count, review_count)
    state["records"] = records
    state["current_step"] = "compute"
    state["progress"] = 85.0
    return state


async def compute_node(state: GraphState) -> GraphState:
    """
    Final computation step.
    """
    # Already done in normalize_node, but we can add any additional computations here
    state["current_step"] = "checkpoint"
    state["progress"] = 95.0
    return state


async def checkpoint_interrupt_node(state: GraphState) -> GraphState:
    """
    Human-in-the-loop checkpoint.
    Returns state for UI review.
    """
    state["current_step"] = "completed"
    state["progress"] = 100.0
    state["needs_interrupt"] = True
    return state


async def cleanup_node(state: GraphState) -> GraphState:
    """
    Clean up temporary files.
    """
    # Clean up temp files
    cleaned = 0
    for img in state["images"]:
        if 'path' in img:
            try:
                path = Path(img['path'])
                if path.exists() and path.is_relative_to(TEMP_DIR):
                    path.unlink()
                    cleaned += 1
            except Exception:
                pass
    logger.info("Cleanup: removed %d temporary files", cleaned)

    # Clear image data from state to free memory
    for img in state["images"]:
        if 'bytes' in img:
            del img['bytes']
        if 'base64' in img:
            del img['base64']

    state["images"] = []
    state["current_step"] = "cleanup_complete"
    return state


# Node mappings
NODES = {
    "ingest": ingest_node,
    "canonicalize": canonicalize_node,
    "preprocess": preprocess_node,
    "extract": extract_node,
    "validate": validate_and_route_node,
    "repair": repair_node,
    "normalize": normalize_node,
    "compute": compute_node,
    "checkpoint": checkpoint_interrupt_node,
    "cleanup": cleanup_node
}

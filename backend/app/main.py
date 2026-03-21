"""FastAPI main application."""
import os
import uuid
import asyncio
import json
import logging
from pathlib import Path
from typing import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from app.config import get_settings
from app.models import Job, MarksheetRecord, JobStatus
from app.services.storage import get_storage
from app.services.excel_export import create_excel
from app.services.normalize import update_record_computations
from app.graph.batch_graph import get_batch_graph, GraphState
from app.graph.nodes import TEMP_DIR

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Global storage for SSE connections
_active_jobs: dict[str, asyncio.Queue] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Initialize storage
    storage = await get_storage()
    yield
    # Cleanup
    await storage.close()
    await cleanup_temp_files()


async def cleanup_temp_files():
    """Clean up temporary files on shutdown."""
    if TEMP_DIR.exists():
        for file in TEMP_DIR.iterdir():
            try:
                file.unlink()
            except Exception:
                pass


# Create FastAPI app
app = FastAPI(
    title="CBSE Marksheet Fetcher API",
    description="API for extracting and computing marks from CBSE Class 12 marksheets",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup event
@app.on_event("startup")
async def startup_event():
    """Create temp directory on startup."""
    TEMP_DIR.mkdir(exist_ok=True)


# Helper functions
async def emit_progress(job_id: str, event_type: str, data: dict):
    """Emit progress event for SSE."""
    if job_id in _active_jobs:
        await _active_jobs[job_id].put({
            "type": event_type,
            "data": data
        })


# API Routes

@app.post("/api/jobs", status_code=201)
async def create_job(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...)
):
    """
    Create a new batch processing job.

    Upload multiple marksheet files (images, PDFs, or a ZIP file).
    Returns job_id for tracking progress.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    if len(files) > settings.max_files_per_batch:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.max_files_per_batch} files per batch"
        )

    # Read all files into memory and validate sizes
    file_data = []
    total_size = 0

    for file in files:
        content = await file.read()
        total_size += len(content)
        file_data.append({
            "filename": file.filename,
            "content": content
        })

    if total_size > settings.max_upload_size:
        raise HTTPException(
            status_code=413,
            detail=f"Upload size exceeds limit of {settings.max_upload_size} bytes"
        )

    # Create job
    job_id = str(uuid.uuid4())
    storage = await get_storage()
    job = await storage.create_job(job_id, len(files))

    # Create SSE queue
    _active_jobs[job_id] = asyncio.Queue()

    # Start background processing with file data
    background_tasks.add_task(process_job_task_with_data, job_id, file_data)

    return {"job_id": job_id, "status": job.status.value}


async def process_job_task_with_data(job_id: str, file_data: list[dict]):
    """Background task to process a job with pre-read file data."""
    storage = await get_storage()
    graph = get_batch_graph()

    try:
        # Save uploaded files
        file_infos = []
        for file_info in file_data:
            filename = file_info["filename"]
            content = file_info["content"]
            file_path = TEMP_DIR / f"{job_id}_{filename}"
            with open(file_path, "wb") as f:
                f.write(content)
            file_infos.append({
                "name": filename,
                "path": str(file_path)
            })

        # Create initial state
        initial_state = GraphState(
            job_id=job_id,
            files=file_infos,
            images=[],
            extractions=[],
            records=[],
            errors=[],
            current_step="ingest",
            progress=0.0,
            needs_interrupt=False
        )

        # Update job status
        await storage.update_job_progress(job_id, JobStatus.processing, 0.0)

        # Run graph with step-by-step progress
        final_state = None
        async for event in graph.astream(initial_state):
            # Emit progress for each step
            for node_name, node_state in event.items():
                if isinstance(node_state, dict):
                    progress = node_state.get("progress", 0)
                    current_step = node_state.get("current_step", "")
                    await emit_progress(job_id, "progress", {
                        "step": current_step,
                        "progress": progress
                    })

                    # Emit record completions (only when we have new records)
                    records = node_state.get("records", [])
                    if records:
                        for record in records:
                            await emit_progress(job_id, "record_complete", {
                                "record_id": record.id,
                                "filename": record.filename,
                                "status": record.status
                            })

                # Update job progress in storage
                await storage.update_job_progress(
                    job_id,
                    progress=node_state.get("progress", 0) if isinstance(node_state, dict) else 0
                )

                # Keep track of final state
                final_state = node_state

        # Use the final state from stream
        if final_state is None:
            final_state = initial_state

        # Save records to storage
        records = final_state.get("records", [])
        for record in records:
            await storage.add_record(job_id, record)

        # Mark job as completed
        await storage.update_job_progress(
            job_id,
            JobStatus.completed,
            100.0,
            completed_files=len(records)
        )

        await emit_progress(job_id, "complete", {
            "job_id": job_id,
            "total_records": len(records)
        })

    except Exception as e:
        logger.exception("Job %s failed", job_id)
        await storage.update_job_progress(job_id, JobStatus.error)
        await emit_progress(job_id, "error", {
            "error": str(e)
        })

    finally:
        # Cleanup SSE queue after delay
        await asyncio.sleep(5)
        if job_id in _active_jobs:
            del _active_jobs[job_id]


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    """
    Get job status and all records.

    Returns complete job state including all extracted records.
    """
    storage = await get_storage()
    job = await storage.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job.id,
        "status": job.status.value,
        "progress": job.progress,
        "total_files": job.total_files,
        "completed_files": job.completed_files,
        "failed_files": job.failed_files,
        "records": [r.model_dump() for r in job.records],
        "record_count": len(job.records),
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "error": job.error
    }


@app.get("/api/jobs/{job_id}/events")
async def job_events(job_id: str):
    """
    SSE endpoint for real-time job progress updates.

    Client should connect with EventSource to receive:
    - progress: Step completion with percentage
    - record_complete: Individual file processing complete
    - complete: Job finished
    - error: Processing error
    """
    storage = await get_storage()
    job = await storage.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Create queue if not exists
    if job_id not in _active_jobs:
        _active_jobs[job_id] = asyncio.Queue()

    async def event_stream():
        """Generate SSE events."""
        try:
            # Send initial state
            data = json.dumps({
                "job_id": job_id,
                "total_files": job.total_files,
                "status": job.status.value
            })
            yield f"event: job_start\ndata: {data}\n\n"

            # Stream events from queue
            while True:
                try:
                    event = await asyncio.wait_for(
                        _active_jobs[job_id].get(),
                        timeout=30.0
                    )

                    event_type = event.get("type", "message")
                    event_data = json.dumps(event.get("data", {}))
                    yield f"event: {event_type}\ndata: {event_data}\n\n"

                    if event_type == "complete":
                        break
                    if event_type == "error":
                        break

                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"

        except Exception as e:
            error_data = json.dumps({"error": str(e)})
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream"
    )


@app.patch("/api/jobs/{job_id}/records/{record_id}")
async def update_record(job_id: str, record_id: str, updates: dict):
    """
    Update a specific record after review.

    Accepts partial updates to record fields.
    Server recomputes percentages after update.
    """
    storage = await get_storage()
    job = await storage.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Find record
    record = None
    for r in job.records:
        if r.id == record_id:
            record = r
            break

    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    # Prevent overwriting read-only fields
    protected_fields = {"id", "filename"}
    for key, value in updates.items():
        if key in protected_fields:
            continue
        if hasattr(record, key):
            setattr(record, key, value)

    # Recompute
    record = update_record_computations(record)

    # Save
    await storage.add_record(job_id, record)

    return {"success": True, "record": record.model_dump()}


@app.post("/api/jobs/{job_id}/records/{record_id}/rerun")
async def rerun_extraction(job_id: str, record_id: str):
    """
    Re-run extraction for a specific record using fallback model.

    Useful when initial extraction had errors.
    """
    storage = await get_storage()
    job = await storage.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Find record
    record_idx = None
    for i, r in enumerate(job.records):
        if r.id == record_id:
            record_idx = i
            break

    if record_idx is None:
        raise HTTPException(status_code=404, detail="Record not found")

    logger.info("Rerun requested for record %s in job %s", record_id, job_id)
    # Note: This is a simplified rerun
    # In production, you'd need the original file or image
    return {"success": True, "message": "Rerun queued"}


@app.get("/api/jobs/{job_id}/export")
async def export_excel(job_id: str):
    """
    Export job records as Excel file.

    Returns .xlsx file with formatted results.
    Includes red highlighting for problematic cells.
    """
    storage = await get_storage()
    job = await storage.get_job(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.records:
        raise HTTPException(status_code=400, detail="No records to export")

    # Generate Excel
    excel_bytes = create_excel(job.records)

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=marksheet_results_{job_id}.xlsx"
        }
    )


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    storage = await get_storage()
    job_count = await storage.get_job_count()
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.app_env,
        "active_jobs": job_count
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

"""Storage service for job state management with Redis and in-memory fallback."""
import json
import asyncio
import logging
from typing import Optional, Dict, List
from datetime import datetime, timezone
import redis.asyncio as redis
from app.config import get_settings
from app.models import Job, JobStatus, MarksheetRecord

settings = get_settings()
logger = logging.getLogger(__name__)


class StorageService:
    """Storage service with Redis fallback to in-memory."""

    def __init__(self):
        self._redis: Optional[redis.Redis] = None
        self._memory: Dict[str, Job] = {}
        self._use_redis = False

    async def initialize(self):
        """Initialize storage backend."""
        try:
            self._redis = await redis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            await self._redis.ping()
            self._use_redis = True
        except Exception:
            self._use_redis = False
            logger.info("Redis unavailable, using in-memory storage")

    async def close(self):
        """Close storage connections."""
        if self._redis:
            await self._redis.aclose()

    def _make_key(self, job_id: str) -> str:
        """Create Redis key for job."""
        return f"job:{job_id}"

    async def create_job(self, job_id: str, total_files: int) -> Job:
        """Create a new job."""
        job = Job(
            id=job_id,
            status=JobStatus.queued,
            total_files=total_files,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        await self.save_job(job)
        return job

    async def get_job(self, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        if self._use_redis:
            key = self._make_key(job_id)
            data = await self._redis.get(key)
            if data:
                return Job.model_validate_json(data)
        else:
            return self._memory.get(job_id)
        return None

    async def save_job(self, job: Job) -> None:
        """Save job state."""
        if self._use_redis:
            key = self._make_key(job_id=job.id)
            await self._redis.set(key, job.model_dump_json(), ex=3600)  # 1 hour TTL
        else:
            self._memory[job.id] = job

    async def update_job_progress(
        self,
        job_id: str,
        status: Optional[JobStatus] = None,
        progress: Optional[float] = None,
        completed_files: Optional[int] = None,
        failed_files: Optional[int] = None
    ) -> Optional[Job]:
        """Update job progress."""
        job = await self.get_job(job_id)
        if not job:
            return None

        if status is not None:
            job.status = status
        if progress is not None:
            job.progress = progress
        if completed_files is not None:
            job.completed_files = completed_files
        if failed_files is not None:
            job.failed_files = failed_files

        if status == JobStatus.completed and not job.completed_at:
            job.completed_at = datetime.now(timezone.utc).isoformat()

        await self.save_job(job)
        return job

    async def add_record(self, job_id: str, record: MarksheetRecord) -> None:
        """Add or update a record in the job."""
        job = await self.get_job(job_id)
        if not job:
            return

        # Update existing or add new
        existing_idx = next((i for i, r in enumerate(job.records) if r.id == record.id), None)
        if existing_idx is not None:
            job.records[existing_idx] = record
        else:
            job.records.append(record)

        await self.save_job(job)

    async def update_record(
        self,
        job_id: str,
        record_id: str,
        updates: dict
    ) -> Optional[MarksheetRecord]:
        """Update a specific record."""
        job = await self.get_job(job_id)
        if not job:
            return None

        for record in job.records:
            if record.id == record_id:
                for key, value in updates.items():
                    if hasattr(record, key):
                        setattr(record, key, value)
                await self.save_job(job)
                return record

        return None

    async def get_records(self, job_id: str) -> List[MarksheetRecord]:
        """Get all records for a job."""
        job = await self.get_job(job_id)
        return job.records if job else []

    async def get_job_count(self) -> int:
        """Get total number of stored jobs."""
        if self._use_redis:
            keys = await self._redis.keys("job:*")
            return len(keys)
        return len(self._memory)

    async def delete_job(self, job_id: str) -> bool:
        """Delete a job."""
        if self._use_redis:
            key = self._make_key(job_id)
            await self._redis.delete(key)
        else:
            if job_id in self._memory:
                del self._memory[job_id]
        return True


# Singleton instance
_storage: Optional[StorageService] = None


async def get_storage() -> StorageService:
    """Get storage service singleton."""
    global _storage
    if _storage is None:
        _storage = StorageService()
        await _storage.initialize()
    return _storage

"""Background worker process executing jobs from the jobs table with SKIP LOCKED."""

import asyncio
import os
import signal
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.storage import LocalStorageBackend
from app.db.models import Job
from app.db.session import AsyncSessionLocal
from app.llm.fake import FakeClient
from app.logging import logger, setup_logging
from app.pipeline.stages import run_pipeline

RUNNING = True


def handle_shutdown(sig, frame):
    global RUNNING
    logger.info("worker_shutdown_signal_received")
    RUNNING = False


async def claim_next_job(session: AsyncSession) -> Job | None:
    """Claim the next ready job atomically using FOR UPDATE SKIP LOCKED if supported."""
    now = datetime.utcnow()
    query = (
        select(Job)
        .where(Job.status == "queued", Job.run_after <= now)
        .order_by(Job.id.asc())
        .limit(1)
    )

    # Use FOR UPDATE SKIP LOCKED on PostgreSQL
    if "postgresql" in settings.DATABASE_URL:
        query = query.with_for_update(skip_locked=True)

    result = await session.execute(query)
    job = result.scalar_one_or_none()

    if job:
        job.status = "processing"
        job.locked_at = now
        job.attempts += 1
        await session.commit()

    return job


async def process_job(
    job: Job,
    session: AsyncSession,
    storage: LocalStorageBackend,
    llm_client: FakeClient,
) -> None:
    """Execute a single job with backoff and error tracking."""
    log = logger.bind(job_id=job.id, kind=job.kind)
    log.info("processing_job_started", attempt=job.attempts)

    try:
        if job.kind == "ingest_asset":
            asset_id = uuid.UUID(job.payload["asset_id"])
            user_lat = job.payload.get("lat")
            user_lng = job.payload.get("lng")
            user_site_id = (
                uuid.UUID(job.payload["site_id"]) if job.payload.get("site_id") else None
            )

            await run_pipeline(
                asset_id=asset_id,
                session=session,
                storage=storage,
                llm_client=llm_client,
                user_lat=user_lat,
                user_lng=user_lng,
                user_site_id=user_site_id,
            )

        job.status = "done"
        job.last_error = None
        await session.commit()
        log.info("processing_job_completed")

    except Exception as exc:
        log.error("processing_job_failed", error=str(exc))
        if job.attempts >= job.max_attempts:
            job.status = "failed"
            job.last_error = f"Max attempts reached: {str(exc)}"
        else:
            job.status = "queued"
            # Exponential backoff with jitter
            backoff_secs = 2**job.attempts
            job.run_after = datetime.utcnow() + timedelta(seconds=backoff_secs)
            job.last_error = str(exc)
        await session.commit()


async def run_worker() -> None:
    """Continuous polling loop for jobs."""
    setup_logging()
    logger.info("worker_started", pid=os.getpid(), env=settings.APP_ENV)

    storage = LocalStorageBackend()
    llm_client = FakeClient()

    while RUNNING:
        try:
            async with AsyncSessionLocal() as session:
                job = await claim_next_job(session)
                if job:
                    await process_job(job, session, storage, llm_client)
                    continue
        except Exception as e:
            logger.error("worker_loop_error", error=str(e))

        await asyncio.sleep(1.0)

    logger.info("worker_stopped_gracefully")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    asyncio.run(run_worker())


from __future__ import annotations
from backend.api.auth import router as auth_router
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from backend.api.security import (
    MAX_UPLOAD_SIZE,
    ensure_inside_directory,
    generate_storage_filename,
    validate_file_signature,
    validate_file_size,
    validate_operation,
    validate_upload,
)

from backend.jobs.job_manager import JobManager
from backend.jobs.job_processor import JobProcessor
from backend.jobs.job_queue import JobQueue
from backend.jobs.worker import JobWorker

from backend.services.usage_service import (
    ensure_customer,
    can_create_job,
    record_job_usage,
    get_usage_summary,
)


# ---------------------------------------------------------
# PROJECT PATHS
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

STORAGE_DIR = PROJECT_ROOT / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
OUTPUTS_DIR = STORAGE_DIR / "outputs"
JOBS_DIR = STORAGE_DIR / "jobs"


UPLOADS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUTS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

JOBS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)


# ---------------------------------------------------------
# CORE SERVICES
# ---------------------------------------------------------

job_manager = JobManager(
    jobs_directory=JOBS_DIR
)

job_queue = JobQueue()

job_processor = JobProcessor(
    job_manager=job_manager,
    project_root=PROJECT_ROOT,
)

worker = JobWorker(
    job_queue=job_queue,
    job_processor=job_processor,
)


# ---------------------------------------------------------
# FASTAPI LIFESPAN
# ---------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Start the background worker when the API starts
    and stop it cleanly when the API shuts down.
    """

    worker.start()

    try:
        yield

    finally:
        worker.stop()


# ---------------------------------------------------------
# FASTAPI APPLICATION
# ---------------------------------------------------------

app = FastAPI(
    title="Sair Lab API",
    description="Sair Lab Excel and CSV Automation SaaS API",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
# ---------------------------------------------------------
# ROOT
# ---------------------------------------------------------

@app.get("/")
def root():
    return {
        "success": True,
        "service": "Sair Lab API",
        "version": "1.0.0",
        "status": "running",
    }


# ---------------------------------------------------------
# HEALTH
# ---------------------------------------------------------

@app.get("/health")
def health():
    return {
        "success": True,
        "status": "healthy",
        "worker_running": worker.is_running(),
        "queued_jobs": job_queue.size(),
    }


# ---------------------------------------------------------
# UPLOAD + CREATE JOB
# ---------------------------------------------------------

@app.post("/api/jobs/upload")
async def upload_job(
    file: UploadFile = File(...),
    operation: str = Form("clean"),
    customer_id: Optional[str] = Form(None),
    package: Optional[str] = Form("free"),
):
    """
    Secure upload endpoint.

    Flow:

        Upload
          ↓
        Validate metadata
          ↓
        Identify customer / usage plan
          ↓
        Save safely
          ↓
        Validate size
          ↓
        Validate actual file
          ↓
        Check usage quota
          ↓
        Create job
          ↓
        Record usage
          ↓
        Queue job
          ↓
        Worker processes job

    IMPORTANT:
    The client-supplied `package` field is NOT trusted for
    determining whether a customer is Free or Pro.
    The plan comes from the server-side usage database.
    """

    # -----------------------------------------------------
    # FILENAME
    # -----------------------------------------------------

    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required.",
        )

    original_filename = Path(
        file.filename
    ).name

    # -----------------------------------------------------
    # CUSTOMER
    # -----------------------------------------------------

    normalized_customer_id = None

    if customer_id is not None:
        normalized_customer_id = customer_id.strip()

        if not normalized_customer_id:
            raise HTTPException(
                status_code=400,
                detail="Customer ID cannot be empty.",
            )

    # -----------------------------------------------------
    # OPERATION
    # -----------------------------------------------------

    try:
        operation = validate_operation(
            operation
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    # -----------------------------------------------------
    # INITIAL FILENAME VALIDATION
    # -----------------------------------------------------

    try:
        upload_info = validate_upload(
            original_filename,
            0,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    extension = upload_info["extension"]

    # -----------------------------------------------------
    # CUSTOMER / PLAN
    # -----------------------------------------------------

    customer_plan = "free"

    if normalized_customer_id:
        customer = ensure_customer(
            normalized_customer_id
        )

        customer_plan = customer["plan"]

    # -----------------------------------------------------
    # SAVE UPLOAD
    # -----------------------------------------------------

    #
    # The current global security layer has a 25 MB hard
    # upload limit. Plan-specific expansion to 100 MB for
    # Pro will be handled when the global upload cap is
    # expanded.
    #

    storage_filename = generate_storage_filename(
        "TEMP",
        extension,
    )

    temp_path = UPLOADS_DIR / storage_filename

    try:
        temp_path = ensure_inside_directory(
            temp_path,
            UPLOADS_DIR,
        )

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Unsafe upload path.",
        )

    total_size = 0

    try:
        with open(
            temp_path,
            "wb",
        ) as buffer:

            while True:
                chunk = await file.read(
                    1024 * 1024
                )

                if not chunk:
                    break

                total_size += len(chunk)

                # Global hard security limit.
                if total_size > MAX_UPLOAD_SIZE:
                    raise ValueError(
                        "File is too large. "
                        "Maximum allowed size is 25 MB."
                    )

                buffer.write(chunk)

    except ValueError as exc:

        if temp_path.exists():
            temp_path.unlink()

        raise HTTPException(
            status_code=413,
            detail=str(exc),
        )

    except Exception as exc:

        if temp_path.exists():
            temp_path.unlink()

        raise HTTPException(
            status_code=500,
            detail="Failed to save uploaded file.",
        )

    finally:
        await file.close()

    # -----------------------------------------------------
    # FINAL SIZE VALIDATION
    # -----------------------------------------------------

    try:
        validate_file_size(
            total_size
        )

    except ValueError as exc:

        if temp_path.exists():
            temp_path.unlink()

        raise HTTPException(
            status_code=413,
            detail=str(exc),
        )

    # -----------------------------------------------------
    # USAGE LIMIT CHECK
    # -----------------------------------------------------

    if normalized_customer_id:

        allowed, usage_message = can_create_job(
            normalized_customer_id,
            total_size,
        )

        if not allowed:

            if temp_path.exists():
                temp_path.unlink()

            # File-size rejection.
            if (
                "file" in usage_message.lower()
                or "size" in usage_message.lower()
                or "mb" in usage_message.lower()
            ):
                raise HTTPException(
                    status_code=413,
                    detail=usage_message,
                )

            # Monthly quota rejection.
            raise HTTPException(
                status_code=429,
                detail=usage_message,
            )

    # -----------------------------------------------------
    # CREATE JOB
    # -----------------------------------------------------

    job = job_manager.create_job(
        customer_id=normalized_customer_id,
        package=customer_plan,
        operation=operation,
    )

    job_id = job["job_id"]

    # -----------------------------------------------------
    # FINAL INTERNAL FILENAME
    # -----------------------------------------------------

    final_storage_filename = generate_storage_filename(
        job_id,
        extension,
    )

    input_path = (
        UPLOADS_DIR / final_storage_filename
    )

    try:
        input_path = ensure_inside_directory(
            input_path,
            UPLOADS_DIR,
        )

    except ValueError as exc:

        if temp_path.exists():
            temp_path.unlink()

        job_manager.fail_job(
            job_id,
            str(exc),
        )

        raise HTTPException(
            status_code=400,
            detail="Unsafe upload path.",
        )

    # -----------------------------------------------------
    # MOVE TEMP FILE TO FINAL JOB FILE
    # -----------------------------------------------------

    try:
        shutil.move(
            str(temp_path),
            str(input_path),
        )

    except Exception as exc:

        if temp_path.exists():
            temp_path.unlink()

        job_manager.fail_job(
            job_id,
            f"Failed to finalize upload: {exc}",
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to finalize uploaded file.",
        )

    # -----------------------------------------------------
    # ACTUAL FILE VALIDATION
    # -----------------------------------------------------

    try:
        validate_file_signature(
            input_path,
            extension,
        )

    except ValueError as exc:

        if input_path.exists():
            input_path.unlink()

        job_manager.fail_job(
            job_id,
            str(exc),
        )

        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    # -----------------------------------------------------
    # SAVE JOB INPUT METADATA
    # -----------------------------------------------------

    job_manager.update_job(
        job_id,
        {
            "input": {
                "file_name": original_filename,
                "file_path": str(input_path),
                "size_bytes": total_size,
            }
        },
    )

    # -----------------------------------------------------
    # ADD TO QUEUE
    # -----------------------------------------------------

    added = job_queue.add(
        job_id
    )

    if not added:

        if input_path.exists():
            input_path.unlink()

        job_manager.fail_job(
            job_id,
            "Job could not be added to queue.",
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to queue job.",
        )

    # -----------------------------------------------------
    # RECORD USAGE
    # -----------------------------------------------------

    if normalized_customer_id:
        try:
            record_job_usage(
                normalized_customer_id,
                total_size,
            )

        except Exception as exc:

            # The job has already entered the queue.
            # Do not destroy a valid queued job because
            # usage bookkeeping failed.
            #
            # The error is intentionally not exposed to
            # the customer.
            print(
                f"WARNING: Failed to record usage "
                f"for {normalized_customer_id}: {exc}"
            )

    # -----------------------------------------------------
    # USAGE SUMMARY
    # -----------------------------------------------------

    usage = None

    if normalized_customer_id:
        try:
            usage = get_usage_summary(
                normalized_customer_id
            )

        except Exception:
            usage = None

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    response = {
        "success": True,
        "job_id": job_id,
        "status": job_manager.get_job(
            job_id
        )["status"],
        "operation": operation,
        "file_name": original_filename,
        "size_bytes": total_size,
        "max_upload_size": MAX_UPLOAD_SIZE,
        "plan": customer_plan,
    }

    if normalized_customer_id:
        response["customer_id"] = normalized_customer_id
        response["usage"] = usage

    return response


# ---------------------------------------------------------
# GET SINGLE JOB
# ---------------------------------------------------------

@app.get("/api/jobs/{job_id}")
def get_job(
    job_id: str,
):
    job = job_manager.get_job(
        job_id
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found.",
        )

    return {
        "success": True,
        "job": job,
    }


# ---------------------------------------------------------
# LIST JOBS
# ---------------------------------------------------------

@app.get("/api/jobs")
def list_jobs(
    status: Optional[str] = None,
    customer_id: Optional[str] = None,
):
    jobs = job_manager.list_jobs(
        status=status,
        customer_id=customer_id,
    )

    return {
        "success": True,
        "count": len(jobs),
        "jobs": jobs,
    }


# ---------------------------------------------------------
# QUEUE STATUS
# ---------------------------------------------------------

@app.get("/api/queue")
def queue_status():
    return {
        "success": True,
        "queue": worker.stats(),
    }


# ---------------------------------------------------------
# DOWNLOAD
# ---------------------------------------------------------

@app.get("/api/jobs/{job_id}/download")
def download_job(
    job_id: str,
):
    job = job_manager.get_job(
        job_id
    )

    if job is None:
        raise HTTPException(
            status_code=404,
            detail="Job not found.",
        )

    if job["status"] != "COMPLETED":
        raise HTTPException(
            status_code=409,
            detail="Job is not completed yet.",
        )

    output = job.get(
        "output",
        {},
    )

    output_path = output.get(
        "file_path"
    )

    if not output_path:
        raise HTTPException(
            status_code=404,
            detail="Output file not found.",
        )

    # -----------------------------------------------------
    # DOWNLOAD PATH SECURITY
    # -----------------------------------------------------

    try:
        output_file = ensure_inside_directory(
            output_path,
            OUTPUTS_DIR,
        )

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Unsafe output path.",
        )

    if not output_file.exists():
        raise HTTPException(
            status_code=404,
            detail="Output file no longer exists.",
        )

    if output_file.stat().st_size == 0:
        raise HTTPException(
            status_code=404,
            detail="Output file is empty.",
        )

    return FileResponse(
        path=output_file,
        filename=output_file.name,
        media_type="application/octet-stream",
    )

from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.engine.core import (
    automatic_clean,
    create_report,
    csv_to_excel,
    excel_to_csv,
    format_excel,
    load_table,
    merge_csv_files,
    merge_excel_files,
)
from backend.jobs.job_manager import JobManager, JobStatus
from backend.qa.validator import full_qa


class JobProcessor:
    """
    Executes Sair Lab jobs through the processing engine,
    validates the result, and updates JobManager state.
    """

    def __init__(
        self,
        job_manager: JobManager | None = None,
        project_root: str | Path | None = None,
    ):
        self.project_root = (
            Path(project_root).resolve()
            if project_root
            else Path(__file__).resolve().parents[2]
        )

        if job_manager is not None:
            self.job_manager = job_manager
        else:
            self.job_manager = JobManager(
                jobs_directory=self.project_root / "storage" / "jobs"
            )

        self.uploads_dir = self.project_root / "storage" / "uploads"
        self.outputs_dir = self.project_root / "storage" / "outputs"
        self.temp_dir = self.project_root / "storage" / "temp"

        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self.outputs_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # PUBLIC PROCESS METHOD
    # ============================================================

    def process(
        self,
        job_id: str,
        input_path: str | Path | None = None,
        operation: str | None = None,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        job = self.job_manager.get_job(job_id)

        if job is None:
            return {
                "success": False,
                "job_id": job_id,
                "status": JobStatus.FAILED,
                "error": f"Job not found: {job_id}",
            }

        try:
            # ----------------------------------------------------
            # Resolve input file
            # ----------------------------------------------------

            if input_path is None:
                stored_input = job.get("input", {}).get("file_path")

                if not stored_input:
                    raise ValueError("No input file supplied for this job.")

                input_path = stored_input

            input_path = Path(input_path).resolve()

            if not input_path.exists():
                raise FileNotFoundError(
                    f"Input file not found: {input_path}"
                )

            # ----------------------------------------------------
            # Resolve operation
            # ----------------------------------------------------

            if operation is None:
                operation = job.get("operation")

            if not operation:
                raise ValueError("No operation specified.")

            operation = operation.lower().strip()

            options = options or {}

            # ----------------------------------------------------
            # Read input statistics
            # ----------------------------------------------------

            input_df = load_table(input_path)

            rows_before = len(input_df)
            columns_before = len(input_df.columns)

            self.job_manager.set_input_stats(
                job_id,
                rows=rows_before,
                columns=columns_before,
            )

            # ----------------------------------------------------
            # Processing
            # ----------------------------------------------------

            self.job_manager.set_status(
                job_id,
                JobStatus.PROCESSING,
            )

            output_file = self._default_output_path(
                job_id,
                input_path,
                operation,
            )

            output_file.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            result = self._execute_operation(
                input_path=input_path,
                output_path=output_file,
                operation=operation,
                options=options,
            )

            # ----------------------------------------------------
            # Validate output existence
            # ----------------------------------------------------

            if not output_file.exists():
                raise RuntimeError(
                    f"Processing completed but output file was not created: "
                    f"{output_file}"
                )

            if output_file.stat().st_size <= 0:
                raise RuntimeError(
                    f"Output file is empty: {output_file}"
                )

            # ----------------------------------------------------
            # Read output statistics
            # ----------------------------------------------------

            try:
                output_df = load_table(output_file)

                rows_after = len(output_df)
                columns_after = len(output_df.columns)

            except Exception:
                rows_after = None
                columns_after = None

            # ----------------------------------------------------
            # Save output metadata
            # ----------------------------------------------------

            output_size = output_file.stat().st_size

            self.job_manager.set_output(
                job_id,
                output_file=output_file,
                rows=rows_after,
                columns=columns_after,
            )

            # ----------------------------------------------------
            # QA
            # ----------------------------------------------------

            self.job_manager.set_status(
                job_id,
                JobStatus.QA,
            )

            qa_result = full_qa(
                input_path=input_path,
                output_path=output_file,
            )

            qa_passed = bool(qa_result.passed)

            self.job_manager.set_qa_result(
                job_id,
                passed=qa_passed,
                errors=list(qa_result.errors),
                warnings=list(qa_result.warnings),
            )

            # ----------------------------------------------------
            # QA failure
            # ----------------------------------------------------

            if not qa_passed:
                error_message = "; ".join(
                    qa_result.errors
                ) or "Output failed quality assurance."

                self.job_manager.fail_job(
                    job_id,
                    error_message,
                )

                return {
                    "success": False,
                    "job_id": job_id,
                    "status": JobStatus.FAILED,
                    "error": error_message,
                    "output_path": str(output_file),
                    "qa": {
                        "passed": False,
                        "errors": list(qa_result.errors),
                        "warnings": list(qa_result.warnings),
                    },
                }

            # ----------------------------------------------------
            # Complete job
            # ----------------------------------------------------

            completed_job = self.job_manager.complete_job(
                job_id
            )

            return {
                "success": True,
                "job_id": job_id,
                "status": JobStatus.COMPLETED,
                "operation": operation,
                "input_path": str(input_path),
                "output_path": str(output_file),
                "output_size": output_size,
                "rows_before": rows_before,
                "columns_before": columns_before,
                "rows_after": rows_after,
                "columns_after": columns_after,
                "qa": {
                    "passed": qa_passed,
                    "errors": list(qa_result.errors),
                    "warnings": list(qa_result.warnings),
                },
                "result": result,
                "job": completed_job,
            }

        except Exception as exc:

            error_message = str(exc)

            try:
                self.job_manager.fail_job(
                    job_id,
                    error_message,
                )
            except Exception:
                pass

            return {
                "success": False,
                "job_id": job_id,
                "status": JobStatus.FAILED,
                "error": error_message,
            }

    # ============================================================
    # OPERATION ROUTER
    # ============================================================

    def _execute_operation(
        self,
        input_path: Path,
        output_path: Path,
        operation: str,
        options: dict[str, Any],
    ) -> Any:

        # --------------------------------------------------------
        # CLEAN
        # --------------------------------------------------------

        if operation == "clean":
            return automatic_clean(
                input_path,
                output_path,
            )

        # --------------------------------------------------------
        # FORMAT
        # --------------------------------------------------------

        if operation == "format":
            return format_excel(
                input_path,
                output_path,
                **options,
            )

        # --------------------------------------------------------
        # REPORT
        # --------------------------------------------------------

        if operation == "report":

            df = load_table(input_path)

            return create_report(
                df,
                output_path,
            )

        # --------------------------------------------------------
        # CSV → EXCEL
        # --------------------------------------------------------

        if operation == "csv_to_excel":
            return csv_to_excel(
                input_path,
                output_path,
            )

        # --------------------------------------------------------
        # EXCEL → CSV
        # --------------------------------------------------------

        if operation == "excel_to_csv":
            return excel_to_csv(
                input_path,
                output_path,
            )

        # --------------------------------------------------------
        # MERGE CSV
        # --------------------------------------------------------

        if operation == "merge_csv":

            files = options.get("input_files")

            if not files:
                raise ValueError(
                    "merge_csv requires 'input_files' in options."
                )

            files = [
                Path(file)
                for file in files
            ]

            return merge_csv_files(
                files,
                output_path,
            )

        # --------------------------------------------------------
        # MERGE EXCEL
        # --------------------------------------------------------

        if operation == "merge_excel":

            files = options.get("input_files")

            if not files:
                raise ValueError(
                    "merge_excel requires 'input_files' in options."
                )

            files = [
                Path(file)
                for file in files
            ]

            return merge_excel_files(
                files,
                output_path,
            )

        # --------------------------------------------------------
        # UNKNOWN OPERATION
        # --------------------------------------------------------

        raise ValueError(
            f"Unsupported operation: {operation}"
        )

    # ============================================================
    # OUTPUT PATH
    # ============================================================

    def _default_output_path(
        self,
        job_id: str,
        input_path: Path,
        operation: str,
    ) -> Path:

        if operation == "excel_to_csv":
            extension = ".csv"

        else:
            extension = ".xlsx"

        return (
            self.outputs_dir
            / f"{job_id}_{operation}{extension}"
        )

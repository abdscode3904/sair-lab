from pathlib import Path

import pandas as pd

from backend.engine.core import (
    SUPPORTED_INPUTS,
    validate_input_file,
    load_table,
)


class QAResult:
    """
    Standardized QA result object.

    Provides both:
        result.passed
        result.errors
        result.warnings

    and dictionary-style access:
        result["passed"]
        result["errors"]
        result["warnings"]
    """

    def __init__(
        self,
        passed: bool,
        errors=None,
        warnings=None,
        checks=None,
    ):
        self.passed = passed
        self.errors = errors or []
        self.warnings = warnings or []
        self.checks = checks or {}

    def to_dict(self):
        return {
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
            "checks": self.checks,
        }

    def __getitem__(self, key):
        return self.to_dict()[key]

    def __bool__(self):
        return self.passed

    def __repr__(self):
        return (
            f"QAResult("
            f"passed={self.passed}, "
            f"errors={len(self.errors)}, "
            f"warnings={len(self.warnings)}"
            f")"
        )


def validate_output_file(
    input_path,
    output_path,
):
    """
    Validate that an output file exists,
    is readable, contains data, and is
    structurally compatible with the input.
    """

    input_path = Path(input_path)
    output_path = Path(output_path)

    errors = []
    warnings = []
    checks = {}

    # -----------------------------------------------------
    # INPUT FILE
    # -----------------------------------------------------

    try:
        validate_input_file(input_path)
        checks["input_file_valid"] = True
    except Exception as exc:
        errors.append(f"Input file validation failed: {exc}")
        checks["input_file_valid"] = False

    # -----------------------------------------------------
    # OUTPUT FILE EXISTS
    # -----------------------------------------------------

    if not output_path.exists():
        errors.append("Output file does not exist.")
        checks["output_exists"] = False

        return QAResult(
            passed=False,
            errors=errors,
            warnings=warnings,
            checks=checks,
        )

    checks["output_exists"] = True

    # -----------------------------------------------------
    # OUTPUT FILE SIZE
    # -----------------------------------------------------

    try:
        file_size = output_path.stat().st_size

        if file_size == 0:
            errors.append("Output file is empty.")
            checks["output_nonempty"] = False
        else:
            checks["output_nonempty"] = True

    except Exception as exc:
        errors.append(f"Could not check output file size: {exc}")
        checks["output_nonempty"] = False

    # -----------------------------------------------------
    # READ INPUT
    # -----------------------------------------------------

    input_df = None

    try:
        input_df = load_table(input_path)
        checks["input_readable"] = True
    except Exception as exc:
        errors.append(f"Could not read input file: {exc}")
        checks["input_readable"] = False

    # -----------------------------------------------------
    # READ OUTPUT
    # -----------------------------------------------------

    output_df = None

    try:
        output_df = load_table(output_path)
        checks["output_readable"] = True
    except Exception as exc:
        errors.append(f"Could not read output file: {exc}")
        checks["output_readable"] = False

    # -----------------------------------------------------
    # OUTPUT DATA
    # -----------------------------------------------------

    if output_df is not None:

        if output_df.shape[1] == 0:
            errors.append("Output contains no columns.")
            checks["output_has_columns"] = False
        else:
            checks["output_has_columns"] = True

        if len(output_df) == 0:
            warnings.append("Output contains zero data rows.")
            checks["output_has_rows"] = False
        else:
            checks["output_has_rows"] = True

    # -----------------------------------------------------
    # COLUMN COMPATIBILITY
    # -----------------------------------------------------

    if input_df is not None and output_df is not None:

        input_columns = list(input_df.columns)
        output_columns = list(output_df.columns)

        missing_columns = [
            column
            for column in input_columns
            if column not in output_columns
        ]

        if missing_columns:
            warnings.append(
                "Output is missing input columns: "
                + ", ".join(map(str, missing_columns))
            )
            checks["columns_compatible"] = False
        else:
            checks["columns_compatible"] = True

    # -----------------------------------------------------
    # FINAL RESULT
    # -----------------------------------------------------

    passed = len(errors) == 0

    return QAResult(
        passed=passed,
        errors=errors,
        warnings=warnings,
        checks=checks,
    )


def validate_no_duplicates(file_path):
    """
    Check whether a file contains duplicate rows.
    """

    file_path = Path(file_path)

    try:
        df = load_table(file_path)

        duplicate_count = int(df.duplicated().sum())

        return {
            "passed": duplicate_count == 0,
            "duplicate_rows": duplicate_count,
        }

    except Exception as exc:
        return {
            "passed": False,
            "duplicate_rows": None,
            "error": str(exc),
        }


def full_qa(
    input_path,
    output_path,
    require_no_duplicates=False,
):
    """
    Run the complete QA pipeline.

    Returns:
        QAResult
    """

    result = validate_output_file(
        input_path=input_path,
        output_path=output_path,
    )

    errors = list(result.errors)
    warnings = list(result.warnings)
    checks = dict(result.checks)

    # -----------------------------------------------------
    # DUPLICATE CHECK
    # -----------------------------------------------------

    if require_no_duplicates:

        duplicate_result = validate_no_duplicates(output_path)

        duplicate_count = duplicate_result.get(
            "duplicate_rows"
        )

        checks["duplicate_check"] = duplicate_result

        if duplicate_count is not None:

            if duplicate_count > 0:
                errors.append(
                    f"Output contains {duplicate_count} duplicate rows."
                )
            else:
                checks["no_duplicates"] = True

        else:
            errors.append(
                "Could not complete duplicate-row validation."
            )

    # -----------------------------------------------------
    # FINAL RESULT
    # -----------------------------------------------------

    passed = len(errors) == 0

    return QAResult(
        passed=passed,
        errors=errors,
        warnings=warnings,
        checks=checks,
    )

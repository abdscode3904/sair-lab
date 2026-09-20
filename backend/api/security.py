from __future__ import annotations

import secrets
from pathlib import Path


# ---------------------------------------------------------
# UPLOAD SECURITY SETTINGS
# ---------------------------------------------------------

MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25 MB

ALLOWED_EXTENSIONS = {
    ".csv",
    ".xlsx",
}

ALLOWED_OPERATIONS = {
    "clean",
    "format",
    "report",
    "csv_to_excel",
    "excel_to_csv",
    "merge_csv",
    "merge_excel",
}


# ---------------------------------------------------------
# FILE EXTENSION
# ---------------------------------------------------------

def get_safe_extension(filename: str) -> str:
    """
    Return a normalized file extension.

    Example:
        report.XLSX -> .xlsx
    """

    if not filename:
        raise ValueError("Filename is required.")

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported file type. Use CSV or XLSX."
        )

    return extension


# ---------------------------------------------------------
# SAFE ORIGINAL FILENAME
# ---------------------------------------------------------

def sanitize_filename(filename: str) -> str:
    """
    Remove path information and dangerous filename characters.

    The customer's original filename is never used as the
    actual storage filename.
    """

    if not filename:
        raise ValueError("Filename is required.")

    name = Path(filename).name

    # Remove potentially dangerous characters.
    safe_chars = []

    for char in name:
        if (
            char.isalnum()
            or char in {
                ".",
                "-",
                "_",
                " ",
            }
        ):
            safe_chars.append(char)

    safe_name = "".join(safe_chars).strip()

    if not safe_name:
        raise ValueError("Invalid filename.")

    return safe_name


# ---------------------------------------------------------
# RANDOM STORAGE NAME
# ---------------------------------------------------------

def generate_storage_filename(
    job_id: str,
    extension: str,
) -> str:
    """
    Generate a unique internal filename.

    Customer filenames never control the storage path.
    """

    extension = extension.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError(
            "Unsupported file extension."
        )

    random_token = secrets.token_hex(8)

    return (
        f"{job_id}_"
        f"{random_token}_input"
        f"{extension}"
    )


# ---------------------------------------------------------
# FILE SIZE VALIDATION
# ---------------------------------------------------------

def validate_file_size(size_bytes: int) -> None:
    """
    Reject files larger than MAX_UPLOAD_SIZE.
    """

    if size_bytes < 0:
        raise ValueError(
            "Invalid file size."
        )

    if size_bytes > MAX_UPLOAD_SIZE:
        size_mb = MAX_UPLOAD_SIZE / (
            1024 * 1024
        )

        raise ValueError(
            f"File is too large. "
            f"Maximum allowed size is "
            f"{size_mb:.0f} MB."
        )


# ---------------------------------------------------------
# OPERATION VALIDATION
# ---------------------------------------------------------

def validate_operation(operation: str) -> str:
    """
    Validate and normalize an API operation.
    """

    if not operation:
        raise ValueError(
            "Operation is required."
        )

    normalized = operation.lower().strip()

    if normalized not in ALLOWED_OPERATIONS:
        raise ValueError(
            f"Unsupported operation: {normalized}"
        )

    return normalized


# ---------------------------------------------------------
# PATH SAFETY
# ---------------------------------------------------------

def ensure_inside_directory(
    file_path: str | Path,
    allowed_directory: str | Path,
) -> Path:
    """
    Make sure a path cannot escape the intended directory.

    Protects against path traversal such as:
        ../../something
    """

    target = Path(file_path).resolve()
    directory = Path(
        allowed_directory
    ).resolve()

    try:
        target.relative_to(directory)
    except ValueError:
        raise ValueError(
            "Unsafe file path."
        )

    return target


# ---------------------------------------------------------
# FILE SIGNATURE VALIDATION
# ---------------------------------------------------------

def validate_file_signature(
    file_path: str | Path,
    extension: str,
) -> None:
    """
    Perform basic file-signature validation.

    XLSX files are ZIP containers and normally begin
    with PK.

    CSV files are text-based and therefore do not have
    one universal binary signature.
    """

    path = Path(file_path)

    if not path.exists():
        raise ValueError(
            "File does not exist."
        )

    if path.stat().st_size == 0:
        raise ValueError(
            "Uploaded file is empty."
        )

    extension = extension.lower()

    if extension == ".xlsx":
        with open(path, "rb") as file:
            header = file.read(4)

        if header != b"PK\x03\x04":
            raise ValueError(
                "Invalid XLSX file."
            )

    elif extension == ".csv":
        # Read a small portion to make sure the file can
        # be decoded as UTF-8 or UTF-8 with BOM.
        try:
            with open(
                path,
                "r",
                encoding="utf-8-sig",
            ) as file:
                file.read(4096)
        except UnicodeDecodeError:
            raise ValueError(
                "CSV file must contain valid UTF-8 text."
            )


# ---------------------------------------------------------
# COMPLETE UPLOAD VALIDATION
# ---------------------------------------------------------

def validate_upload(
    filename: str,
    size_bytes: int,
) -> dict:
    """
    Validate upload metadata before processing.
    """

    safe_filename = sanitize_filename(
        filename
    )

    extension = get_safe_extension(
        safe_filename
    )

    validate_file_size(
        size_bytes
    )

    return {
        "original_filename": safe_filename,
        "extension": extension,
        "size_bytes": size_bytes,
    }
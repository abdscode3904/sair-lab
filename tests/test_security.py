from pathlib import Path

import pytest

from backend.api.security import (
    ALLOWED_EXTENSIONS,
    MAX_UPLOAD_SIZE,
    ensure_inside_directory,
    generate_storage_filename,
    get_safe_extension,
    sanitize_filename,
    validate_file_signature,
    validate_file_size,
    validate_operation,
    validate_upload,
)


# ---------------------------------------------------------
# EXTENSION TESTS
# ---------------------------------------------------------

def test_valid_csv_extension():
    assert get_safe_extension(
        "data.csv"
    ) == ".csv"


def test_valid_xlsx_extension():
    assert get_safe_extension(
        "DATA.XLSX"
    ) == ".xlsx"


def test_invalid_extension():
    with pytest.raises(ValueError):
        get_safe_extension(
            "virus.exe"
        )


# ---------------------------------------------------------
# FILENAME TESTS
# ---------------------------------------------------------

def test_filename_path_is_removed():
    result = sanitize_filename(
        r"C:\Users\abdul\secret.xlsx"
    )

    assert result == "secret.xlsx"


def test_filename_is_sanitized():
    result = sanitize_filename(
        "report<>:\"/\\|?*.xlsx"
    )

    assert "<" not in result
    assert ">" not in result
    assert ":" not in result
    assert '"' not in result
    assert "/" not in result
    assert "\\" not in result
    assert "|" not in result
    assert "?" not in result
    assert "*" not in result


# ---------------------------------------------------------
# STORAGE FILENAME TESTS
# ---------------------------------------------------------

def test_storage_filename():
    result = generate_storage_filename(
        "SL-123456789",
        ".xlsx",
    )

    assert result.startswith(
        "SL-123456789_"
    )

    assert result.endswith(
        "_input.xlsx"
    )


# ---------------------------------------------------------
# SIZE TESTS
# ---------------------------------------------------------

def test_valid_file_size():
    validate_file_size(
        1024
    )


def test_max_file_size():
    validate_file_size(
        MAX_UPLOAD_SIZE
    )


def test_oversized_file():
    with pytest.raises(ValueError):
        validate_file_size(
            MAX_UPLOAD_SIZE + 1
        )


# ---------------------------------------------------------
# OPERATION TESTS
# ---------------------------------------------------------

def test_valid_operation():
    assert validate_operation(
        " CLEAN "
    ) == "clean"


def test_invalid_operation():
    with pytest.raises(ValueError):
        validate_operation(
            "delete_everything"
        )


# ---------------------------------------------------------
# PATH TRAVERSAL TESTS
# ---------------------------------------------------------

def test_safe_path(tmp_path):
    target = tmp_path / "file.xlsx"

    result = ensure_inside_directory(
        target,
        tmp_path,
    )

    assert result == target.resolve()


def test_unsafe_path(tmp_path):
    target = tmp_path.parent / "outside.xlsx"

    with pytest.raises(ValueError):
        ensure_inside_directory(
            target,
            tmp_path,
        )


# ---------------------------------------------------------
# UPLOAD VALIDATION
# ---------------------------------------------------------

def test_validate_upload():
    result = validate_upload(
        "customer_data.xlsx",
        5000,
    )

    assert result["original_filename"] == (
        "customer_data.xlsx"
    )

    assert result["extension"] == ".xlsx"
    assert result["size_bytes"] == 5000


# ---------------------------------------------------------
# XLSX SIGNATURE
# ---------------------------------------------------------

def test_valid_xlsx_signature(tmp_path):
    file_path = tmp_path / "test.xlsx"

    # ZIP/XLSX signature
    file_path.write_bytes(
        b"PK\x03\x04test"
    )

    validate_file_signature(
        file_path,
        ".xlsx",
    )


def test_invalid_xlsx_signature(tmp_path):
    file_path = tmp_path / "fake.xlsx"

    file_path.write_bytes(
        b"NOT AN XLSX FILE"
    )

    with pytest.raises(ValueError):
        validate_file_signature(
            file_path,
            ".xlsx",
        )


# ---------------------------------------------------------
# CSV SIGNATURE
# ---------------------------------------------------------

def test_valid_csv_signature(tmp_path):
    file_path = tmp_path / "test.csv"

    file_path.write_text(
        "Name,Age\nAbdul,20\n",
        encoding="utf-8",
    )

    validate_file_signature(
        file_path,
        ".csv",
    )


def test_invalid_csv_encoding(tmp_path):
    file_path = tmp_path / "bad.csv"

    file_path.write_bytes(
        b"\xff\xfe\xfd\xfc"
    )

    with pytest.raises(ValueError):
        validate_file_signature(
            file_path,
            ".csv",
        )
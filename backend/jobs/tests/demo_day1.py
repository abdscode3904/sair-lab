from pathlib import Path
import sys

# =========================================================
# PROJECT PATH
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

from backend.engine.core import (
    dataset_info,
    automatic_clean,
    format_excel,
    create_report,
    load_table,
)

from backend.qa.validator import full_qa


# =========================================================
# DIRECTORIES
# =========================================================

BASE_DIR = PROJECT_ROOT

UPLOAD_DIR = BASE_DIR / "storage" / "uploads"
OUTPUT_DIR = BASE_DIR / "storage" / "outputs"

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# =========================================================
# HEADER
# =========================================================

print("=" * 70)
print("SAIR LAB - DAY 1 DEMO")
print("=" * 70)


# =========================================================
# 1. CREATE DEMO INPUT FILE
# =========================================================

input_file = UPLOAD_DIR / "customer_sales.xlsx"

print("\nCreating demo Excel file...")

demo_data = pd.DataFrame({
    "Name": [
        " Abdul ",
        "Rahul",
        "  Aisha",
        "Abdul",
        "Vikram",
        None,
    ],
    "Product": [
        "Laptop",
        "Mouse",
        "Keyboard ",
        "Laptop",
        "Monitor",
        None,
    ],
    "Quantity": [
        2,
        5,
        3,
        2,
        1,
        None,
    ],
    "Price": [
        55000,
        800,
        1500,
        55000,
        12000,
        None,
    ],
})

demo_data.to_excel(input_file, index=False)

print(f"Input created: {input_file}")


# =========================================================
# 2. DATASET INFORMATION
# =========================================================

print("\n" + "=" * 70)
print("1. DATASET INFORMATION")
print("=" * 70)

info = dataset_info(input_file)

for key, value in info.items():
    print(f"{key}: {value}")


# =========================================================
# 3. AUTOMATIC CLEANING
# =========================================================

print("\n" + "=" * 70)
print("2. AUTOMATIC CLEANING")
print("=" * 70)

cleaned_file = OUTPUT_DIR / "cleaned_sales.xlsx"

automatic_clean(
    input_path=input_file,
    output_path=cleaned_file,
)

print(f"Cleaned file: {cleaned_file}")


# =========================================================
# 4. EXCEL FORMATTING
# =========================================================

print("\n" + "=" * 70)
print("3. EXCEL FORMATTING")
print("=" * 70)

formatted_file = OUTPUT_DIR / "formatted_sales.xlsx"

format_excel(
    input_path=cleaned_file,
    output_path=formatted_file,
)

print(f"Formatted file: {formatted_file}")


# =========================================================
# 5. CREATE REPORT
# =========================================================

print("\n" + "=" * 70)
print("4. CREATE REPORT")
print("=" * 70)

report_file = OUTPUT_DIR / "sales_report.xlsx"

cleaned_df = load_table(cleaned_file)

create_report(
    cleaned_df,
    report_file,
)

print(f"Report created: {report_file}")


# =========================================================
# 6. QUALITY ASSURANCE
# =========================================================

print("\n" + "=" * 70)
print("5. QUALITY ASSURANCE")
print("=" * 70)

qa_result = full_qa(
    input_path=input_file,
    output_path=cleaned_file,
    require_no_duplicates=True,
)

print(f"\nPASSED: {qa_result.passed}")

if qa_result.errors:
    print("\nErrors:")

    for error in qa_result.errors:
        print(f" - {error}")

if qa_result.warnings:
    print("\nWarnings:")

    for warning in qa_result.warnings:
        print(f" - {warning}")

print("\nQA checks:")

for check_name, check_value in qa_result.checks.items():
    print(f" - {check_name}: {check_value}")


# =========================================================
# 7. FINAL OUTPUT
# =========================================================

print("\n" + "=" * 70)
print("DAY 1 DEMO COMPLETE")
print("=" * 70)

print("\nGenerated files:")

print(f"1. {cleaned_file}")
print(f"2. {formatted_file}")
print(f"3. {report_file}")

print("\n" + "=" * 70)

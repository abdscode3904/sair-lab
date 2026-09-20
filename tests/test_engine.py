import pandas as pd

from backend.engine.core import (
    remove_duplicates,
    trim_whitespace,
    merge_columns,
    clean_dataframe,
    create_summary,
)


def test_remove_duplicates():
    df = pd.DataFrame({
        "Name": ["A", "B", "A"],
        "Age": [20, 21, 20],
    })

    result = remove_duplicates(df)

    assert len(result) == 2


def test_trim_whitespace():
    df = pd.DataFrame({
        "Name": ["  Abdul  ", " Test"],
    })

    result = trim_whitespace(df)

    assert result["Name"].tolist() == ["Abdul", "Test"]


def test_merge_columns():
    df = pd.DataFrame({
        "First": ["Abdul", "Ali"],
        "Last": ["Bari", "Khan"],
    })

    result = merge_columns(
        df,
        ["First", "Last"],
        "Full Name",
        separator=" ",
    )

    assert result["Full Name"].tolist() == [
        "Abdul Bari",
        "Ali Khan",
    ]


def test_clean_dataframe():
    df = pd.DataFrame({
        "Name": [" Abdul ", "Ali", " Abdul "],
        "Age": [20, None, 20],
    })

    # clean_dataframe() in the current engine
    # uses its own cleaning configuration.
    result = clean_dataframe(df)

    # The duplicate row should be removed.
    assert len(result) == 2

    # Whitespace should be cleaned.
    assert result["Name"].tolist() == ["Abdul", "Ali"]


def test_summary():
    df = pd.DataFrame({
        "Name": ["A", "B", "C"],
        "Sales": [100, 200, 300],
    })

    result = create_summary(df)

    # create_summary() returns a summary DataFrame.
    assert isinstance(result, pd.DataFrame)

    # One summary row should exist for each original column.
    assert len(result) == 2

    assert "Column" in result.columns
    assert "Data Type" in result.columns
    assert "Non-Empty" in result.columns
    assert "Missing" in result.columns
    assert "Unique Values" in result.columns

    # Verify the expected columns are represented.
    assert "Name" in result["Column"].tolist()
    assert "Sales" in result["Column"].tolist()

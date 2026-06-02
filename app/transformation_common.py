import pandas as pd
from pathlib import Path


def read_input_file(file):
    file_name = file if isinstance(file, str) else getattr(file, "name", "")
    suffix = Path(file_name).suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(file)
    elif suffix in [".xlsx", ".xls"]:
        return pd.read_excel(file, header=2)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")


def clean_columns(df):
    df.columns = [str(col).strip() for col in df.columns]
    return df


def normalize_datetime_column(df, col_name):
    if col_name in df.columns:
        df[col_name] = pd.to_datetime(df[col_name], errors="coerce")
    return df


def require_columns(df, required_cols, df_name):
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"{df_name} is missing required columns: {missing}")


def read_demographics_file(file):
    demo = clean_columns(read_input_file(file))
    require_columns(demo, ["Patient ID"], "Demographics file")
    demo = demo.drop_duplicates(subset=["Patient ID"])

    # Find Age column (case-insensitive, including variations like "Patient Age")
    age_col = next(
        (col for col in demo.columns if "age" in col.lower()),
        None
    )
    
    # Find Sex/Gender column (case-insensitive, including variations like "Patient Gender")
    sex_col = next(
        (col for col in demo.columns if any(term in col.lower() for term in ["sex", "gender"])),
        None
    )

    result_dict = {"Patient ID": demo["Patient ID"]}
    if age_col:
        result_dict["Age"] = demo[age_col]
    if sex_col:
        result_dict["Sex"] = demo[sex_col]

    return pd.DataFrame(result_dict)


def merge_demographics(df, demographics_file):
    if demographics_file is None:
        return df
    demo = read_demographics_file(demographics_file)
    return df.merge(demo, on="Patient ID", how="left")


def build_merged_table(primary_file, secondary_file):
    """
    Reads, cleans, validates and merges the two input files.
    Returns a long-format DataFrame with columns:
        Patient ID, Pathway Name, Content Name,
        Scheduled date (optional), Entry Date,
        Question, Answer_Combined
    """
    left = clean_columns(read_input_file(primary_file))
    right = clean_columns(read_input_file(secondary_file))

    if "Input date" in left.columns:
        left = left.rename(columns={"Input date": "Entry Date"})

    normalize_datetime_column(left, "Entry Date")
    normalize_datetime_column(right, "Entry Date")

    required_left = ["Patient ID", "Pathway Name", "Content Name", "Entry Date"]
    required_right = ["Patient ID", "Pathway Name", "Content Name", "Entry Date", "Question"]

    require_columns(left, required_left, "Primary input file")
    require_columns(right, required_right, "Secondary input file")

    merge_keys = ["Patient ID", "Pathway Name", "Content Name", "Entry Date"]
    merged = pd.merge(left, right, on=merge_keys, how="left")

    keep_cols = [
        col for col in [
            "Patient ID", "Pathway Name", "Content Name",
            "Scheduled date", "Entry Date",
            "Question", "Answer Text", "Answer Value",
        ]
        if col in merged.columns
    ]

    df = merged[keep_cols].copy()

    # Combine Answer Value and Answer Text into a single column
    df["Answer_Combined"] = pd.NA
    if "Answer Value" in df.columns:
        df["Answer_Combined"] = df["Answer Value"]
    if "Answer Text" in df.columns:
        df["Answer_Combined"] = df["Answer_Combined"].fillna(df["Answer Text"])

    if "Patient ID" not in df.columns:
        raise ValueError(
            f"'Patient ID' not found after merge. Available columns: {list(df.columns)}"
        )
    if "Question" not in df.columns:
        raise ValueError(
            f"'Question' not found after merge. Available columns: {list(df.columns)}"
        )

    return df

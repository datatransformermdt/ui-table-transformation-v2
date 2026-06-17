import re
import unicodedata

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


def normalize_question_text(text):
    if pd.isna(text):
        return text

    text = str(text).strip()
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+([:;,.?!])", r"\1", text)
    text = re.sub(r"([:;,.?!])(?=\S)", r"\1 ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[?¿!。．\.]+$", "", text).strip()

    return text


def normalize_content_name(text):
    if pd.isna(text):
        return text
    return str(text).strip()


def require_columns(df, required_cols, df_name):
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"{df_name} is missing required columns: {missing}")


def prepare_endpoint_file(endpoint_file):
    endpoints = clean_columns(read_input_file(endpoint_file))
    require_columns(endpoints, ["Patient ID", "Pathway Name"], "endpoint file")

    if "Length of hospital stay" in endpoints.columns:
        endpoints = endpoints.rename(
            columns={"Length of hospital stay": "Endpoint_Length of hospital stay days"}
        )

    discharge_cols = [
        "Entlassung Exitus",
        "Entlassung Nachhause",
        "Entlassung Pflegeheim",
        "Entlassung AHB Reha",
    ]

    available_discharge_cols = [
        col for col in discharge_cols
        if col in endpoints.columns
    ]

    if available_discharge_cols:
        def derive_discharge_modality(row):
            active = [
                col.replace("Entlassung ", "")
                for col in available_discharge_cols
                if pd.notna(row[col]) and row[col] == 1
            ]

            if len(active) == 0:
                return pd.NA
            if len(active) == 1:
                return active[0]

            return "Multiple: " + ", ".join(active)

        endpoints["Endpoint_Discharge modality"] = endpoints.apply(
            derive_discharge_modality,
            axis=1,
        )

        endpoints["Endpoint_Discharge modality conflict"] = (
            endpoints[available_discharge_cols].fillna(0).sum(axis=1) > 1
        )

    key_cols = ["Patient ID", "Pathway Name"]
    rename_map = {}
    for col in endpoints.columns:
        if col not in key_cols and not col.startswith("Endpoint_"):
            rename_map[col] = f"Endpoint_{col}"

    endpoints = endpoints.rename(columns=rename_map)
    return endpoints


def read_demographics_file(file):
    demo = clean_columns(read_input_file(file))
    require_columns(demo, ["Patient ID"], "Patient metadata file")

    merge_keys = ["Patient ID"]
    if "Pathway Name" in demo.columns:
        merge_keys.append("Pathway Name")

    demo = demo.drop_duplicates(subset=merge_keys)
    return demo


def merge_demographics(df, demographics_file):
    if demographics_file is None:
        return df
    demo = read_demographics_file(demographics_file)

    merge_keys = ["Patient ID"]
    if "Pathway Name" in demo.columns and "Pathway Name" in df.columns:
        merge_keys.append("Pathway Name")

    return df.merge(demo, on=merge_keys, how="left")


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

    if "Question" in df.columns:
        df["Question_Normalized"] = df["Question"].apply(normalize_question_text)

    if "Content Name" in df.columns:
        df["Content_Name_Normalized"] = df["Content Name"].apply(normalize_content_name)

    return df

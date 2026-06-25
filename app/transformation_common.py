import io
import os
import re
import unicodedata

import pandas as pd
from pathlib import Path

DEBUG_ENDPOINT_MAPPING = os.getenv("DEBUG_ENDPOINT_MAPPING", "0").lower() not in {"0", "false", "off"}

def _debug_endpoint_series(stage, col, series):
    print(f"DEBUG: {stage} - {col}")
    print(" dtype:", series.dtype)
    print(series.astype("object").value_counts(dropna=False).head(20))
    print(" head:", series.head(10).tolist())


def _find_excel_header_row(df):
    possible_headers = {
        "Patient ID", "Pathway Name", "Content Name", "Entry Date",
        "Scheduled date", "Input date", "Question", "Answer Text",
        "Answer Value",
    }

    max_rows = min(len(df), 8)
    for row_idx in range(max_rows):
        row = df.iloc[row_idx].astype(str).fillna("").str.strip()
        valid_cells = row[row != ""]
        if len(valid_cells) < 2:
            continue

        if valid_cells.str.contains(r"^Unnamed", regex=True).any():
            continue

        header_matches = sum(1 for value in valid_cells if value in possible_headers)
        if header_matches >= 2 or len(valid_cells) >= max(2, len(row) * 0.5):
            return row_idx

    return 0


def read_input_file(file):
    file_name = file if isinstance(file, str) else getattr(file, "name", "")
    suffix = Path(file_name).suffix.lower()

    if suffix == ".csv":
        if not isinstance(file, str) and hasattr(file, "seek"):
            file.seek(0)
        return pd.read_csv(file)
    elif suffix in [".xlsx", ".xls"]:
        engine = "openpyxl" if suffix == ".xlsx" else "xlrd"
        if isinstance(file, str):
            preview_df = pd.read_excel(file, header=None, engine=engine)
            header_row = _find_excel_header_row(preview_df)
            return pd.read_excel(file, header=header_row, engine=engine)
        else:
            if hasattr(file, "seek"):
                file.seek(0)
            file_bytes = file.read()
            excel_source = io.BytesIO(file_bytes)
            preview_df = pd.read_excel(excel_source, header=None, engine=engine)
            header_row = _find_excel_header_row(preview_df)
            excel_source.seek(0)
            return pd.read_excel(excel_source, header=header_row, engine=engine)
    else:
        raise ValueError(f"Unsupported file format: {suffix}")


def clean_columns(df):
    df.columns = [str(col).strip() for col in df.columns]
    return df


def normalize_datetime_column(df, col_name):
    if col_name in df.columns:
        df[col_name] = pd.to_datetime(df[col_name], errors="coerce")
    return df


def _strip_accents(text):
    if pd.isna(text):
        return text
    normalized = unicodedata.normalize("NFKD", str(text))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))

# Invisible/formatting Unicode characters that appear in PDF/Excel text extraction
# and cause identical questions to look different (e.g. soft hyphen mid-word).
_INVISIBLE_CHARS = re.compile(
    "­​‌‍\u200E\u200F⁠﻿"  # soft-hyphen + zero-width chars
)

def normalize_question_text(text):
    if pd.isna(text):
        return text

    text = str(text).strip()
    text = unicodedata.normalize("NFKC", text)
    text = _INVISIBLE_CHARS.sub("", text)        # remove soft hyphen and zero-width chars
    text = re.sub(r"\s+([:;,.?!])", r"\1", text)
    text = re.sub(r"([:;,.?!])(?=\S)", r"\1 ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[?¿!。．\.]+$", "", text).strip()

    return text


def normalize_content_name(text):
    if pd.isna(text):
        return text
    return str(text).strip()


def _strip_accents(text):
    if pd.isna(text):
        return text
    normalized = unicodedata.normalize("NFKD", str(text))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _find_column(df, candidate_names):
    for name in candidate_names:
        if name in df.columns:
            return name
    return None


def _combine_answer_columns(df):
    df = df.copy()
    text_cols = [col for col in ["Answer Text", "Text Answer", "Answer"] if col in df.columns]
    value_cols = [col for col in ["Answer Value", "Value", "Numeric Answer"] if col in df.columns]

    if not text_cols and not value_cols:
        raise ValueError(
            "Answers file must contain at least one answer column: Answer Text, Text Answer, Answer, Answer Value, Value, or Numeric Answer"
        )

    if text_cols:
        df[text_cols] = df[text_cols].replace({"": pd.NA})
    if value_cols:
        df[value_cols] = df[value_cols].replace({"": pd.NA})

    df["Answer_Combined"] = pd.NA
    for col in text_cols:
        df["Answer_Combined"] = df["Answer_Combined"].fillna(df[col])

    for col in value_cols:
        df["Answer_Combined"] = df["Answer_Combined"].fillna(df[col])

    if "Answer" in df.columns and "Answer" not in text_cols:
        df["Answer_Combined"] = df["Answer_Combined"].fillna(df["Answer"])

    return df


def _is_iterative_content_name(content_name):
    if pd.isna(content_name):
        return False

    keyword_list = [
        "Allgemeine Gesundheit",
        "Schmerztagebuch",
        "Tagesbericht zuhause",
        "BMI",
        "Bewegungstagebuch",
        "Wöchentliches Bewegungstagebuch",
        "Woechentliches Bewegungstagebuch",
    ]
    content_normalized = _strip_accents(content_name).lower()
    return any(_strip_accents(keyword).lower() in content_normalized for keyword in keyword_list)


def build_content_base(content_file):
    content = clean_columns(read_input_file(content_file))
    require_columns(content, ["Patient ID", "Pathway Name"], "Content file")
    return content[["Patient ID", "Pathway Name"]].drop_duplicates()


def build_answer_table(content_file, answers_file):
    base = build_content_base(content_file)
    answers = clean_columns(read_input_file(answers_file))

    if "Input date" in answers.columns:
        answers = answers.rename(columns={"Input date": "Entry Date"})

    normalize_datetime_column(answers, "Entry Date")

    require_columns(answers, ["Patient ID", "Pathway Name", "Content Name", "Question"], "Answers file")

    answers = answers.merge(
        base,
        on=["Patient ID", "Pathway Name"],
        how="inner"
    )

    answers = _combine_answer_columns(answers)
    answers["Question_Normalized"] = answers["Question"].apply(normalize_question_text)
    answers["Content_Name_Normalized"] = answers["Content Name"].apply(normalize_content_name)

    return answers


def require_columns(df, required_cols, df_name):
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"{df_name} is missing required columns: {missing}")


def prepare_endpoint_file(endpoint_file):
    if isinstance(endpoint_file, pd.DataFrame):
        endpoints = clean_columns(endpoint_file.copy())
    else:
        endpoints = clean_columns(read_input_file(endpoint_file))
    require_columns(endpoints, ["Patient ID", "Pathway Name"], "endpoint file")

    duplicate_count = endpoints.duplicated(subset=["Patient ID", "Pathway Name"]).sum()
    if duplicate_count > 0:
        raise ValueError(
            f"Endpoint file contains {duplicate_count} duplicate Patient ID + Pathway Name rows"
        )

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
        if DEBUG_ENDPOINT_MAPPING:
            print('DEBUG: prepare_endpoint_file - after read_input_file')
            for col in available_discharge_cols:
                _debug_endpoint_series('before mapping', col, endpoints[col])

        def _map_entlassung_value(value):
            if pd.isna(value):
                return pd.NA

            if isinstance(value, str):
                normalized = value.replace("\xa0", " ").strip()
                if normalized in {"", "0", "0.0"}:
                    return pd.NA
                if normalized in {"1", "1.0"}:
                    return "Ja"

            if isinstance(value, bool):
                return "Ja" if value else pd.NA

            try:
                numeric_value = float(value)
                if numeric_value == 1:
                    return "Ja"
                if numeric_value == 0:
                    return pd.NA
            except (TypeError, ValueError):
                pass

            return value

        for col in available_discharge_cols:
            endpoints[col] = endpoints[col].map(_map_entlassung_value)

        if DEBUG_ENDPOINT_MAPPING:
            print('DEBUG: prepare_endpoint_file - after mapping')
            for col in available_discharge_cols:
                _debug_endpoint_series('after mapping', col, endpoints[col])

    key_cols = ["Patient ID", "Pathway Name"]
    rename_map = {}
    for col in endpoints.columns:
        if col not in key_cols and not col.startswith("Endpoint_"):
            rename_map[col] = f"Endpoint_{col}"

    endpoints = endpoints.rename(columns=rename_map)
    if DEBUG_ENDPOINT_MAPPING and available_discharge_cols:
        print('DEBUG: prepare_endpoint_file - after rename')
        for col in available_discharge_cols:
            new_col = f'Endpoint_{col}'
            if new_col in endpoints.columns:
                _debug_endpoint_series('after rename', new_col, endpoints[new_col])
    return endpoints


def read_demographics_file(file):
    demo = clean_columns(read_input_file(file))
    require_columns(demo, ["Patient ID"], "Enrichment file")

    merge_keys = ["Patient ID"]
    if "Pathway Name" in demo.columns:
        merge_keys.append("Pathway Name")

    duplicate_count = demo.duplicated(subset=merge_keys).sum()
    if duplicate_count > 0:
        raise ValueError(
            f"Enrichment file contains {duplicate_count} duplicate rows for keys {merge_keys}"
        )

    return demo


def _sort_question_column(col_with_index):
    """Sort key for ContentName_Iteration_Question (or ContentName_Question) format."""
    col, index = col_with_index
    if not isinstance(col, str):
        return ("", 0, "", index)

    # ContentName_N_Question  (iterative)
    m = re.match(r"^(.+?)_(\d+)_(.+)$", col)
    if m:
        return (m.group(1).strip().lower(), int(m.group(2)), m.group(3).strip().lower(), index)

    # ContentName_Question  (non-iterative with content prefix)
    parts = col.split("_", 1)
    if len(parts) == 2:
        return (parts[0].strip().lower(), 0, parts[1].strip().lower(), index)

    return ("", 0, col.strip().lower(), index)


def _sort_question_columns(cols):
    return [col for col, _ in sorted(
        ((col, idx) for idx, col in enumerate(cols)),
        key=_sort_question_column,
    )]


def reorder_transformed_columns(final, demographics_file=None):
    primary_id_cols = [col for col in ["Patient ID"] if col in final.columns]
    path_cols       = [col for col in ["Pathway Name"] if col in final.columns]

    demo_cols = []
    if demographics_file is not None:
        if isinstance(demographics_file, pd.DataFrame):
            demo = clean_columns(demographics_file.copy())
        else:
            demo = read_demographics_file(demographics_file)
        demo_cols = [col for col in demo.columns if col not in primary_id_cols + ["Pathway Name"]]
        demo_cols = [col for col in demo_cols if col in final.columns]

    endpoint_cols = sorted(
        [col for col in final.columns if isinstance(col, str) and col.startswith("Endpoint_")]
    )
    # Structural columns present only in the normal (non-iterative) workflow
    content_cols  = [col for col in ["Content Name"] if col in final.columns]
    date_cols     = [col for col in ["Scheduled date", "Entry Date"] if col in final.columns]

    fixed = set(primary_id_cols + path_cols + demo_cols + endpoint_cols + content_cols + date_cols)
    question_cols = [col for col in final.columns if col not in fixed]

    ordered_cols = (
        primary_id_cols       # Patient ID
        + path_cols           # Pathway Name
        + demo_cols           # enrichment / demographics
        + endpoint_cols       # Endpoint_* columns
        + content_cols        # Content Name  (normal workflow only)
        + date_cols           # Scheduled date, Entry Date  (normal workflow only)
        + _sort_question_columns(question_cols)  # ContentName_[N_]Question, grouped by questionnaire
    )
    return final[ordered_cols]


def _first_non_null(series):
    for value in series:
        if pd.notna(value):
            return value
    return pd.NA


def _collapse_duplicate_rows(df, merge_keys, df_name):
    if not df.duplicated(subset=merge_keys).any():
        return df

    duplicates = df[df.duplicated(subset=merge_keys, keep=False)]
    conflicts = []
    non_key_cols = [col for col in df.columns if col not in merge_keys]
    grouped = duplicates.groupby(merge_keys, dropna=False)

    for key_values, group in grouped:
        for col in non_key_cols:
            non_null_values = group[col].dropna().astype(str).unique()
            if len(non_null_values) > 1:
                conflicts.append((key_values, col, non_null_values.tolist()))

    if conflicts:
        raise ValueError(
            f"{df_name} contains conflicting duplicate rows for keys {merge_keys}: "
            f"{len(conflicts)} conflict(s) found."
        )

    return df.groupby(merge_keys, as_index=False).agg(_first_non_null)


def merge_demographics(df, demographics_file):
    """Merge demographics/enrichment information into the main dataframe.

    Accepts either a path/file-like object or a pre-loaded pandas DataFrame.
    Merges on Patient ID and Pathway Name when both are available.
    """
    if demographics_file is None:
        return df

    if isinstance(demographics_file, pd.DataFrame):
        demo = clean_columns(demographics_file.copy())
    else:
        demo = read_demographics_file(demographics_file)

    require_columns(df, ["Patient ID"], "Final output")
    require_columns(demo, ["Patient ID"], "Enrichment file")

    merge_keys = ["Patient ID"]
    if "Pathway Name" in demo.columns and "Pathway Name" in df.columns:
        merge_keys.append("Pathway Name")

    demo = _collapse_duplicate_rows(demo, merge_keys, "Enrichment data")

    overlap = set(demo.columns).intersection(set(df.columns)) - set(merge_keys)
    if overlap:
        raise ValueError(
            f"Enrichment file contains column(s) already present in output: {sorted(overlap)}"
        )

    return df.merge(demo, on=merge_keys, how="left")


def _assign_answer_entry_dates_by_tolerance(left, right, tolerance=pd.Timedelta(seconds=2)):
    """Assign each answer row the nearest scheduled Entry Date within tolerance."""
    core_keys = ["Patient ID", "Pathway Name", "Content Name"]
    required_cols = core_keys + ["Entry Date"]

    if any(col not in left.columns for col in required_cols):
        raise ValueError(f"Left file is missing required columns for tolerance matching: {required_cols}")
    if any(col not in right.columns for col in required_cols):
        raise ValueError(f"Right file is missing required columns for tolerance matching: {required_cols}")

    left_events = (
        left[required_cols]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    right = right.reset_index().rename(columns={"index": "_right_idx"})
    candidates = right.merge(
        left_events.rename(columns={"Entry Date": "Entry Date_Scheduled"}),
        on=core_keys,
        how="left",
    )

    candidates["Distance"] = (candidates["Entry Date"] - candidates["Entry Date_Scheduled"]).abs()
    candidates = candidates[candidates["Distance"] <= tolerance].copy()

    if not candidates.empty:
        candidates = (
            candidates.sort_values(["_right_idx", "Distance"])
            .groupby("_right_idx", as_index=False)
            .first()
        )
        right = right.merge(
            candidates[["_right_idx", "Entry Date_Scheduled"]],
            on="_right_idx",
            how="left",
        )
        right["Entry Date"] = right["Entry Date_Scheduled"].fillna(right["Entry Date"])
        right = right.drop(columns=["Entry Date_Scheduled", "_right_idx"])
    else:
        right = right.drop(columns=["_right_idx"])

    return right


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
    if "Input date" in right.columns:
        right = right.rename(columns={"Input date": "Entry Date"})

    normalize_datetime_column(left, "Entry Date")
    normalize_datetime_column(right, "Entry Date")

    required_left = ["Patient ID", "Pathway Name", "Content Name", "Entry Date"]
    required_right = ["Patient ID", "Pathway Name", "Content Name", "Entry Date", "Question"]

    require_columns(left, required_left, "Primary input file")
    require_columns(right, required_right, "Secondary input file")

    right = _combine_answer_columns(right)
    right["Question_Normalized"] = right["Question"].apply(normalize_question_text)
    right["Content_Name_Normalized"] = right["Content Name"].apply(normalize_content_name)

    if "Entry Date" in right.columns:
        right = _assign_answer_entry_dates_by_tolerance(left, right)

    merge_keys = ["Patient ID", "Pathway Name", "Content Name", "Entry Date"]
    merged = pd.merge(left, right, on=merge_keys, how="left", suffixes=("", "_answer"))

    keep_cols = [
        col for col in [
            "Patient ID", "Pathway Name", "Content Name",
            "Scheduled date", "Entry Date",
            "Question", "Answer_Combined",
            "Question_Normalized", "Content_Name_Normalized",
        ]
        if col in merged.columns
    ]

    df = merged[keep_cols].copy()

    if "Patient ID" not in df.columns:
        raise ValueError(
            f"'Patient ID' not found after merge. Available columns: {list(df.columns)}"
        )
    if "Question" not in df.columns:
        raise ValueError(
            f"'Question' not found after merge. Available columns: {list(df.columns)}"
        )

    return df

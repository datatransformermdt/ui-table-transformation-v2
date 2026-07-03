import os
import pandas as pd
from transformation_common import (
    apply_question_canonical_map,
    build_merged_table,
    build_patient_base,
    _compute_source_stats,
    build_transformation_report,
    merge_demographics,
    prepare_endpoint_file,
    reorder_transformed_columns,
)


def process_normal_files(primary_file, secondary_file, demographics_file=None, endpoint_file=None, output_file=None):
    """
    Normal (non-iterative) questionnaire workflow.

    Output: one row per questionnaire event (Patient ID + Pathway Name +
    Content Name + Entry Date), with one column per question.

    The answers file is the primary source for questionnaire variables.
    Patients with answer records but no content file entry still receive
    questionnaire columns (Scheduled date will be NaT for those rows).
    """
    # build_merged_table uses an outer join so answer-only rows are preserved.
    df = build_merged_table(primary_file, secondary_file)

    id_cols   = [col for col in ["Patient ID", "Pathway Name", "Content Name"] if col in df.columns]
    date_cols = [col for col in ["Scheduled date", "Entry Date"] if col in df.columns]

    # pivot_table silently drops rows where any index value is NaN/NaT.
    # Replace them with sentinels so those rows are kept, then restore afterwards.
    SENTINEL_DATE = pd.Timestamp("1900-01-01")
    SENTINEL_STR  = "___MISSING___"

    df_pivot = df.copy()
    for col in date_cols:
        if pd.api.types.is_datetime64_any_dtype(df_pivot[col]):
            df_pivot[col] = df_pivot[col].fillna(SENTINEL_DATE)
        else:
            df_pivot[col] = df_pivot[col].fillna(SENTINEL_STR)

    if "Content_Name_Normalized" in df_pivot.columns:
        _q = "Question_Normalized" if "Question_Normalized" in df_pivot.columns else "Question"
        df_pivot["_col_label"] = df_pivot["Content_Name_Normalized"] + "_" + df_pivot[_q]
        df_pivot["_col_label"] = apply_question_canonical_map(df_pivot["_col_label"])
        pivot_question_col = "_col_label"
    else:
        pivot_question_col = "Question_Normalized" if "Question_Normalized" in df_pivot.columns else "Question"

    # Drop rows where the question label is null (can't become a column name)
    df_pivot = df_pivot[df_pivot[pivot_question_col].notna()].copy()

    final = df_pivot.pivot_table(
        index=id_cols + date_cols,
        columns=pivot_question_col,
        values="Answer_Combined",
        aggfunc="first",
    ).reset_index()

    event_base = df_pivot[id_cols + date_cols].drop_duplicates()
    final = event_base.merge(final, on=id_cols + date_cols, how="left")
    final.columns.name = None

    # Restore sentinels
    for col in date_cols:
        if pd.api.types.is_datetime64_any_dtype(final[col]):
            final[col] = final[col].replace(SENTINEL_DATE, pd.NaT)
        else:
            final[col] = final[col].replace(SENTINEL_STR, pd.NA)

    # Build the full patient-pathway universe from content + answers + demographics.
    # Any patient-pathway in demographics or answers but absent from the pivot
    # (e.g. truly data-sparse patients) gets one blank row added below.
    full_base, content_base = build_patient_base(
        primary_file, demographics_file, answers_file=secondary_file
    )

    # Patients already in the pivot (from content or answers records)
    pivot_pairs = final[["Patient ID", "Pathway Name"]].drop_duplicates()
    missing_pairs = full_base.merge(
        pivot_pairs, on=["Patient ID", "Pathway Name"], how="left", indicator=True
    )
    missing_pairs = (
        missing_pairs[missing_pairs["_merge"] == "left_only"]
        [["Patient ID", "Pathway Name"]]
        .reset_index(drop=True)
    )

    if not missing_pairs.empty:
        blank_rows = missing_pairs.copy()
        for col in final.columns:
            if col not in blank_rows.columns:
                blank_rows[col] = pd.NA
        final = pd.concat([final, blank_rows[final.columns]], ignore_index=True)

    # Collect source stats before demographics/endpoints are merged in.
    source_stats = _compute_source_stats(final, content_base)
    _ans_pairs = df[["Patient ID", "Pathway Name"]].drop_duplicates()

    final = merge_demographics(final, demographics_file)

    if endpoint_file is not None:
        if os.getenv("DEBUG_ENDPOINT_MAPPING", "0").lower() not in {"0", "false", "off"}:
            print('DEBUG: process_normal_files - final before endpoint merge columns:', list(final.columns))
        endpoints = prepare_endpoint_file(endpoint_file)
        final = final.merge(
            endpoints,
            on=["Patient ID", "Pathway Name"],
            how="left",
            suffixes=("", "_endpoint"),
        )

    final = reorder_transformed_columns(final, demographics_file)

    # Attach metadata last so merges above cannot clear attrs.
    final.attrs["transformation_report"] = build_transformation_report(
        final, content_base,
        source_stats=source_stats,
        answers_pairs=_ans_pairs,
    )

    if output_file:
        final.to_csv(output_file, index=False, encoding='utf-8-sig')

    return final

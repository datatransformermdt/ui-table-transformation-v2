import os
import pandas as pd
from transformation_common import (
    build_merged_table,
    build_patient_base,
    _compute_analog_answer_stats,
    build_transformation_report,
    merge_demographics,
    prepare_endpoint_file,
    reorder_transformed_columns,
)


def process_normal_files(primary_file, secondary_file, demographics_file=None, endpoint_file=None, output_file=None):
    """
    Normal (non-iterative) questionnaire workflow.

    Each patient/pathway/content appears only ONCE in the input data.
    Output: one row per questionnaire event, with Scheduled date and
    Entry Date included, and one column per question.

    Rows where Scheduled date is missing are preserved — NaT/NaN is a
    valid state (patient answered but was not formally scheduled).
    """
    df = build_merged_table(primary_file, secondary_file)

    id_cols  = [col for col in ["Patient ID", "Pathway Name", "Content Name"] if col in df.columns]
    date_cols = [col for col in ["Scheduled date", "Entry Date"] if col in df.columns]

    # pivot_table silently drops rows where any index value is NaN/NaT.
    # Replace NaT/NaN in date columns with a sentinel so those rows are kept,
    # then restore the original missing values after the pivot.
    SENTINEL_DATE = pd.Timestamp("1900-01-01")
    SENTINEL_STR  = "___MISSING___"

    df_pivot = df.copy()
    for col in date_cols:
        if pd.api.types.is_datetime64_any_dtype(df_pivot[col]):
            df_pivot[col] = df_pivot[col].fillna(SENTINEL_DATE)
        else:
            df_pivot[col] = df_pivot[col].fillna(SENTINEL_STR)

    # Build ContentName_Question label for pivot column headers
    if "Content_Name_Normalized" in df_pivot.columns:
        _q = "Question_Normalized" if "Question_Normalized" in df_pivot.columns else "Question"
        df_pivot["_col_label"] = df_pivot["Content_Name_Normalized"] + "_" + df_pivot[_q]
        pivot_question_col = "_col_label"
    else:
        pivot_question_col = "Question_Normalized" if "Question_Normalized" in df_pivot.columns else "Question"

    final = df_pivot.pivot_table(
        index=id_cols + date_cols,
        columns=pivot_question_col,
        values="Answer_Combined",
        aggfunc="first",
    ).reset_index()

    base = df_pivot[id_cols + date_cols].drop_duplicates()
    final = base.merge(final, on=id_cols + date_cols, how="left")
    final.columns.name = None

    # Restore sentinels back to NaN/NaT
    for col in date_cols:
        if pd.api.types.is_datetime64_any_dtype(final[col]):
            final[col] = final[col].replace(SENTINEL_DATE, pd.NaT)
        else:
            final[col] = final[col].replace(SENTINEL_STR, pd.NA)

    # Capture the digital patient-pathways before adding any analog rows.
    # This is used for the transformation report and the analog answer check.
    digital_base = final[["Patient ID", "Pathway Name"]].drop_duplicates().reset_index(drop=True)

    # Include analog patients: those in demographics but absent from the
    # questionnaire file. They get one blank row per (Patient ID, Pathway Name).
    # Questionnaire answers are always merged by [Patient ID, Pathway Name] only.
    if demographics_file is not None:
        full_base, _ = build_patient_base(primary_file, demographics_file)
        merged_check = full_base.merge(
            digital_base,
            on=["Patient ID", "Pathway Name"],
            how="left",
            indicator=True,
        )
        analog_pairs = (
            merged_check[merged_check["_merge"] == "left_only"]
            [["Patient ID", "Pathway Name"]]
            .reset_index(drop=True)
        )
        if not analog_pairs.empty:
            analog_rows = analog_pairs.copy()
            for col in final.columns:
                if col not in analog_rows.columns:
                    analog_rows[col] = pd.NA
            final = pd.concat([final, analog_rows[final.columns]], ignore_index=True)

    # Verify analog patients have no questionnaire answers (must run before
    # demographics/endpoints are merged in so non-null values = answers only).
    analog_answer_stats = _compute_analog_answer_stats(final, digital_base)

    final = merge_demographics(final, demographics_file)
    if endpoint_file is not None:
        if os.getenv("DEBUG_ENDPOINT_MAPPING", "0").lower() not in {"0", "false", "off"}:
            print('DEBUG: process_normal_files - final before endpoint merge columns:', list(final.columns))
            print(final.filter(regex='Entlassung|Endpoint_Entlassung').head(5).to_dict('records'))
        endpoints = prepare_endpoint_file(endpoint_file)
        if os.getenv("DEBUG_ENDPOINT_MAPPING", "0").lower() not in {"0", "false", "off"}:
            print('DEBUG: process_normal_files - endpoint file columns:', list(endpoints.columns))
        final = final.merge(
            endpoints,
            on=["Patient ID", "Pathway Name"],
            how="left",
            suffixes=("", "_endpoint"),
        )
        if os.getenv("DEBUG_ENDPOINT_MAPPING", "0").lower() not in {"0", "false", "off"}:
            print('DEBUG: process_normal_files - final after endpoint merge columns:', list(final.columns))
            print(final.filter(regex='Entlassung|Endpoint_Entlassung').head(5).to_dict('records'))

    final = reorder_transformed_columns(final, demographics_file)

    # Attach all attrs last so downstream merges cannot clear them.
    final.attrs["transformation_report"] = build_transformation_report(
        final, digital_base, analog_answer_stats
    )

    if output_file:
        final.to_csv(output_file, index=False, encoding='utf-8-sig')

    return final

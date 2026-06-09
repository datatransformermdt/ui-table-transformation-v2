import pandas as pd
from transformation_common import build_merged_table, merge_demographics


def process_normal_files(primary_file, secondary_file, demographics_file=None, output_file=None):
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

    final = merge_demographics(final, demographics_file)
    if any(col in final.columns for col in ["Age", "Sex", "Gender"]):
        demo_cols = [col for col in ["Age", "Sex", "Gender"] if col in final.columns]
        base_cols = [col for col in ["Patient ID"] if col in final.columns]
        remaining_id_cols = [col for col in ["Pathway Name", "Content Name"] if col in final.columns]
        other_cols = [col for col in final.columns if col not in base_cols + demo_cols + remaining_id_cols]
        final = final[base_cols + demo_cols + remaining_id_cols + other_cols]

    if output_file:
        final.to_csv(output_file, index=False, encoding="utf-8-sig")

    return final

import re
import pandas as pd
from transformation_common import build_merged_table, merge_demographics

ITERATIVE_CONTENT_NAME_KEYWORDS = [
    "Allgemeine Gesundheit",  # Globale Gesundheitsumfrage / PROMIS-10
    "Schmerztagebuch",         # Schmerztagebuch variants
    "Tagesbericht zuhause",   # Tagesbericht zuhause
    "BMI",                    # BMI-Daten
]


def _is_iterative_content_name(content_name):
    content_name = str(content_name or "").strip().lower()
    return any(keyword.lower() in content_name for keyword in ITERATIVE_CONTENT_NAME_KEYWORDS)


def normalize_question_text(question):
    """
    Normalize question text to handle minor variations:
    - Remove trailing punctuation (?, !, .)
    - Strip whitespace
    - Handle NaN/None values
    
    This ensures questions like:
      'Wurde das Prä-operative Blutbild erhoben (inkl. Bluttyp & Ferritin/Transferrin)'
      'Wurde das Prä-operative Blutbild erhoben (inkl. Bluttyp & Ferritin/Transferrin)?'
    are recognized as the same question.
    """
    if pd.isna(question):
        return pd.NA
    question = str(question).strip()
    # Remove trailing punctuation (?, !, .)
    question = re.sub(r'[?!.]+$', '', question).strip()
    return question


def sort_question_columns(cols):
    """Sort columns by questionnaire name first, then question text, then iteration."""
    def parse_column(col):
        parts = col.rsplit("_", maxsplit=1)
        if len(parts) == 2 and parts[1].isdigit():
            question_part, iteration = parts[0], int(parts[1])
            question_parts = question_part.rsplit("_", maxsplit=1)
            if len(question_parts) == 2:
                question_text, content_name = question_parts
                return (content_name.strip(), question_text.strip(), iteration)
            return ("", question_part.strip(), iteration)

        if len(parts) == 2:
            question_text, content_name = parts
            return (content_name.strip(), question_text.strip(), 0)

        return ("", col.strip(), 0)

    return sorted(cols, key=parse_column)


def _fill_sentinel(series, sentinel_ts, sentinel_str):
    """Fill NaN/NaT regardless of whether the column is datetime or object/str."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return series.fillna(sentinel_ts)
    else:
        return series.fillna(sentinel_str)


def _restore_sentinel(series, sentinel_ts, sentinel_str):
    """Put NaN/NaT back after pivot."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return series.replace(sentinel_ts, pd.NaT)
    else:
        return series.replace(sentinel_str, pd.NA)


def process_iterative_files(primary_file, secondary_file, demographics_file=None, output_file=None):
    """
    Iterative questionnaire workflow.

    Output: one row per patient, with repeated question answers suffixed
    _1, _2, _3 … in chronological order by Entry Date.

    When there are multiple questionnaires (Content Name varies):
    - Column names include the questionnaire name: Question_QuestionnaireName_1
    When there is only one questionnaire:
    - Column names use simple iteration: Question_1, Question_2

    Rows where Scheduled date (or any other date) is missing are fully
    preserved — NaT/NaN is replaced with a sentinel before pivoting so
    pandas does not silently discard those rows.
    """
    df = build_merged_table(primary_file, secondary_file)
    
    # Normalize question text to handle minor variations (e.g., missing ?)
    if "Question" in df.columns:
        df["Question"] = df["Question"].apply(normalize_question_text)

    id_cols   = [col for col in ["Patient ID", "Pathway Name"] if col in df.columns]
    date_cols = [col for col in ["Scheduled date", "Entry Date"] if col in df.columns]
    
    # Detect if there are multiple questionnaires
    has_content_name = "Content Name" in df.columns
    multiple_questionnaires = has_content_name and (df.groupby(id_cols)["Content Name"].nunique() > 1).any()

    SENTINEL_TS  = pd.Timestamp("1900-01-01")
    SENTINEL_STR = "___MISSING___"

    # ── Step 1: pivot to one row per event, keeping NaN rows via sentinel ──
    df_pivot = df.copy()
    for col in date_cols:
        df_pivot[col] = _fill_sentinel(df_pivot[col], SENTINEL_TS, SENTINEL_STR)

    pivot_idx = id_cols + date_cols
    if multiple_questionnaires:
        pivot_idx = pivot_idx + ["Content Name"]

    event_rows = df_pivot[pivot_idx].drop_duplicates()
    question_wide = (
        df_pivot.dropna(subset=["Question"])
        .pivot_table(
            index=pivot_idx,
            columns="Question",
            values="Answer_Combined",
            aggfunc="first",
        )
        .reset_index()
    )

    wide_per_event = event_rows.merge(question_wide, on=pivot_idx, how="left")
    wide_per_event.columns.name = None

    # Restore sentinels to NaN/NaT
    for col in date_cols:
        wide_per_event[col] = _restore_sentinel(wide_per_event[col], SENTINEL_TS, SENTINEL_STR)

    # ── Step 2: sort by Entry Date (NaT last) so iteration order follows time ──
    sort_key_col = "Entry Date" if "Entry Date" in wide_per_event.columns else (date_cols[0] if date_cols else None)
    if sort_key_col:
        sort_cols = id_cols + ([sort_key_col] if sort_key_col else [])
        wide_per_event = (
            wide_per_event
            .sort_values(sort_cols, na_position="last")
            .reset_index(drop=True)
        )

    # ── Step 3: assign iteration number per questionnaire event ──
    # Use Content Name grouping so repeated entries within the same questionnaire
    # type get their own ordinal number, while non-iterative questionnaires
    # can still collapse into a single column later.
    iteration_group = id_cols + (["Content Name"] if multiple_questionnaires else [])
    wide_per_event["Iteration"] = (
        wide_per_event.groupby(iteration_group).cumcount() + 1
    )

    # ── Step 4: melt back to long format ──
    melt_id_vars = id_cols + ["Iteration"]
    if multiple_questionnaires:
        melt_id_vars = melt_id_vars + ["Content Name"]
    
    non_value_cols = set(melt_id_vars + date_cols)
    value_cols = [col for col in wide_per_event.columns if col not in non_value_cols]

    melted = wide_per_event.melt(
        id_vars=melt_id_vars,
        value_vars=value_cols,
        var_name="Question",
        value_name="Value",
    )

    # Preserve rows with empty values here so unanswered questions still
    # become columns in the final iterative output.

    # ── Step 5: build Question column names ──
    # Use iteration suffix only for known iterative questionnaires.
    print(f"[DEBUG] Step 5: multiple_questionnaires={multiple_questionnaires}")
    question = melted["Question"].astype(str).str.strip()
    if has_content_name and multiple_questionnaires:
        print(f"[DEBUG] Building Question_Iteration using Content Name, iterative content names will keep iteration")
        content_name = melted["Content Name"].astype(str).str.strip()
        melted["Question_Iteration"] = question + "_" + content_name

        iterative_mask = melted["Content Name"].apply(_is_iterative_content_name)
        if iterative_mask.any():
            melted.loc[iterative_mask, "Question_Iteration"] = (
                melted.loc[iterative_mask, "Question_Iteration"]
                + "_"
                + melted.loc[iterative_mask, "Iteration"].astype(str)
            )
        print(f"[DEBUG] Iterative rows: {iterative_mask.sum()}, non-iterative rows: {(~iterative_mask).sum()}")
    elif has_content_name:
        print(f"[DEBUG] Building Question_Iteration WITHOUT Content Name for single questionnaire")
        melted["Question_Iteration"] = (
            question + "_" + melted["Iteration"].astype(str)
        )
    else:
        print(f"[DEBUG] Building Question_Iteration WITHOUT Content Name")
        melted["Question_Iteration"] = (
            question + "_" + melted["Iteration"].astype(str)
        )

    final = melted.pivot_table(
        index=id_cols,
        columns="Question_Iteration",
        values="Value",
        aggfunc="first",
    ).reset_index()
    final.columns.name = None

    print(f"[DEBUG] After pivot: shape={final.shape}, 'Content Name' in columns={'Content Name' in final.columns}")
    if 'Content Name' in final.columns:
        print(f"[DEBUG] WARNING: Content Name should not be in final columns!")
    print(f"[DEBUG] First 5 columns: {list(final.columns[:5])}")

    # ── Step 6: order columns ──
    base_cols    = [col for col in id_cols if col in final.columns]
    dynamic_cols = [col for col in final.columns if col not in base_cols]
    final = final[base_cols + sort_question_columns(dynamic_cols)]

    # ── Step 7: preserve all question columns ──
    # Keep blank columns for rare or unanswered questionnaires so the
    # output schema remains stable and empty questionnaire columns still appear.
    #
    # Note: columns are already ordered above; do not drop sparse iteration columns.

    final = merge_demographics(final, demographics_file)
    if any(col in final.columns for col in ["Age", "Sex", "Gender"]):
        demo_cols = [col for col in ["Age", "Sex", "Gender"] if col in final.columns]
        base_cols = [col for col in ["Patient ID"] if col in final.columns]
        remaining_id_cols = [col for col in ["Pathway Name"] if col in final.columns]
        other_cols = [col for col in final.columns if col not in base_cols + demo_cols + remaining_id_cols]
        final = final[base_cols + demo_cols + remaining_id_cols + other_cols]

    if output_file:
        final.to_csv(output_file, index=False, encoding="utf-8-sig")

    return final

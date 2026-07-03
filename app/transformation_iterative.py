import os
import pandas as pd
from transformation_common import (
    build_answer_table,
    build_patient_base,
    _compute_analog_answer_stats,
    build_transformation_report,
    merge_demographics,
    prepare_endpoint_file,
    reorder_transformed_columns,
    read_input_file,
    clean_columns,
)

_DEBUG_ANALOG = os.getenv("DEBUG_ANALOG_PIPELINE", "0").lower() not in {"0", "false", "off"}

_DIAG_SEP = "-" * 72


def _diag_rows(stage, df, analog_pairs):
    """Print row counts and analog-pair survival for a patient-level DataFrame."""
    if not _DEBUG_ANALOG:
        return
    keys = ["Patient ID", "Pathway Name"]
    pairs = df[keys].drop_duplicates() if all(c in df.columns for c in keys) else pd.DataFrame(columns=keys)
    print(f"\n{_DIAG_SEP}")
    print(f"[DIAG] {stage}")
    print(f"  total rows      : {len(df)}")
    print(f"  unique pairs    : {len(pairs)}")
    if analog_pairs is not None and not analog_pairs.empty and all(c in df.columns for c in keys):
        rem = pairs.merge(analog_pairs, on=keys, how="inner")
        print(f"  analog pairs    : {len(rem)} / {len(analog_pairs)}")
        for pw in sorted(rem["Pathway Name"].dropna().astype(str).unique()):
            print(f"    pathway '{pw}'")
    elif analog_pairs is not None and analog_pairs.empty:
        print(f"  analog pairs    : 0 (no analog pairs identified)")
    print(_DIAG_SEP)


def _diag_answers(stage, answers, analog_pairs):
    """Print row counts and analog-pair survival for an answer-row-level DataFrame."""
    if not _DEBUG_ANALOG:
        return
    keys = ["Patient ID", "Pathway Name"]
    print(f"\n{_DIAG_SEP}")
    print(f"[DIAG] {stage}")
    print(f"  total rows      : {len(answers)}")
    if all(c in answers.columns for c in keys):
        pairs = answers[keys].drop_duplicates()
        print(f"  unique pairs    : {len(pairs)}")
        if analog_pairs is not None and not analog_pairs.empty:
            analog_rows = answers.merge(analog_pairs, on=keys, how="inner")
            print(f"  analog rows     : {len(analog_rows)} / {len(answers)}")
            print(f"  analog pairs w/ rows: {len(analog_rows[keys].drop_duplicates())} / {len(analog_pairs)}")
            if "Answer_Combined" in analog_rows.columns:
                has_val = analog_rows["Answer_Combined"].notna().sum()
                print(f"  analog rows w/ answer value: {has_val}")
            for pw in sorted(analog_rows["Pathway Name"].dropna().astype(str).unique()):
                sub = analog_rows[analog_rows["Pathway Name"] == pw]
                has_v = sub["Answer_Combined"].notna().sum() if "Answer_Combined" in sub.columns else "n/a"
                print(f"    pathway '{pw}': {len(sub)} rows, {has_v} with answer")
        elif analog_pairs is not None and analog_pairs.empty:
            print(f"  analog rows     : 0 (no analog pairs identified)")
    print(_DIAG_SEP)

ITERATIVE_CONTENT_NAME_KEYWORDS = [
    "Allgemeine Gesundheit",  # Globale Gesundheitsumfrage / PROMIS-10
    "Schmerztagebuch",         # Schmerztagebuch variants
    "Tagesbericht zuhause",   # Tagesbericht zuhause
    "Wöchentliches Bewegungstagebuch",  # Weekly movement diary
    "BMI",                    # BMI-Daten
]


def _is_iterative_content_name(content_name):
    content_name = str(content_name or "").strip().lower()
    return any(keyword.lower() in content_name for keyword in ITERATIVE_CONTENT_NAME_KEYWORDS)


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


def _build_question_iteration_column(row, has_content_name):
    question = str(row["Question_Normalized"]).strip()
    content_name = str(row["Content_Name_Normalized"]).strip() if has_content_name else ""
    iteration = str(int(row["Iteration"]))

    if row["Is_Iterative_Content"]:
        if has_content_name:
            return f"{content_name}_{iteration}_{question}"
        return f"{iteration}_{question}"

    if has_content_name:
        return f"{content_name}_{question}"

    return question


def _collapse_answer_groups(answers):
    answers = answers.copy()
    answers = answers.sort_values([
        "Patient ID",
        "Pathway Name",
        "Content Name",
        "Question_Normalized",
        "Entry Date",
    ], na_position="last")

    collapsed_rows = []
    conflicts = []
    group_cols = ["Patient ID", "Pathway Name", "Question_Iteration"]

    for _, group in answers.groupby(group_cols, sort=False):
        last_row = group.iloc[-1].copy()
        non_null_answers = group["Answer_Combined"].dropna().astype(str)

        if not non_null_answers.empty:
            if (
                len(non_null_answers.unique()) > 1
                and not group["Is_Iterative_Content"].iloc[0]
            ):
                conflicts.append({
                    "Patient ID": last_row["Patient ID"],
                    "Pathway Name": last_row["Pathway Name"],
                    "Question_Iteration": last_row["Question_Iteration"],
                    "values": non_null_answers.unique().tolist(),
                })
            last_row["Answer_Combined"] = non_null_answers.iloc[-1]
        else:
            last_row["Answer_Combined"] = pd.NA

        collapsed_rows.append(last_row)

    collapsed = pd.DataFrame(collapsed_rows)
    if not collapsed.empty:
        collapsed = collapsed.reset_index(drop=True)
    collapsed.attrs = {"conflicts": conflicts}
    return collapsed


def _validate_final_output(final, base):
    expected_rows = len(base.drop_duplicates(subset=["Patient ID", "Pathway Name"]))
    if final.shape[0] != expected_rows:
        raise ValueError(
            f"Final output row count {final.shape[0]} does not match expected base row count {expected_rows}."
        )

    if final.duplicated(subset=["Patient ID", "Pathway Name"]).any():
        raise ValueError("Final output contains duplicate Patient ID + Pathway Name rows.")

    if final.columns.duplicated().any():
        raise ValueError("Final output contains duplicate column names.")

    dot_zero_columns = [col for col in final.columns if isinstance(col, str) and col.endswith(".0")]
    if dot_zero_columns:
        raise ValueError(
            f"Final output contains invalid .0 suffixes: {dot_zero_columns}"
        )


def process_iterative_files(primary_file, secondary_file, demographics_file=None, endpoint_file=None, output_file=None):
    """
    Iterative questionnaire workflow.

    Output: one row per patient/pathway, with repeated question answers suffixed
    _1, _2, _3 … for true iterative content.

    Non-iterative repeated answers are collapsed to the latest non-empty value.
    """
    # ── Diagnostic setup ────────────────────────────────────────────────────────
    # Set DEBUG_ANALOG_PIPELINE=1 in the environment to enable step-by-step output.
    analog_pairs = None  # populated below when debug is active
    if _DEBUG_ANALOG:
        _raw_content = clean_columns(read_input_file(primary_file))
        _raw_answers = clean_columns(read_input_file(secondary_file))
        _content_pairs = _raw_content[["Patient ID", "Pathway Name"]].drop_duplicates()

        if isinstance(demographics_file, pd.DataFrame):
            _demo_raw = clean_columns(demographics_file.copy())
        elif demographics_file is not None:
            _demo_raw = clean_columns(read_input_file(demographics_file))
        else:
            _demo_raw = pd.DataFrame(columns=["Patient ID", "Pathway Name"])

        if "Pathway Name" in _demo_raw.columns:
            _demo_pairs = _demo_raw[["Patient ID", "Pathway Name"]].drop_duplicates()
            _chk = _demo_pairs.merge(_content_pairs, on=["Patient ID", "Pathway Name"],
                                     how="left", indicator=True)
            analog_pairs = _chk[_chk["_merge"] == "left_only"][["Patient ID", "Pathway Name"]].reset_index(drop=True)
        else:
            _demo_pairs = pd.DataFrame(columns=["Patient ID", "Pathway Name"])
            analog_pairs = pd.DataFrame(columns=["Patient ID", "Pathway Name"])

        print(f"\n{'='*72}")
        print("[DIAG] ANALOG PIPELINE DIAGNOSTIC - iterative workflow")
        print(f"{'='*72}")
        print(f"  content unique pairs   : {len(_content_pairs)}")
        print(f"  demographics pairs     : {len(_demo_pairs)}")
        print(f"  analog pairs (demo only, not in content): {len(analog_pairs)}")
        for _pw in sorted(analog_pairs["Pathway Name"].dropna().astype(str).unique()):
            _n = (analog_pairs["Pathway Name"] == _pw).sum()
            print(f"    '{_pw}'  ({_n} patients)")

        # Stage 1: raw content
        _diag_rows("1. Raw content file", _raw_content, analog_pairs)

        # Stage 2: raw answers (before any filtering)
        _diag_answers("2. Raw answers file (before any join/filter)", _raw_answers, analog_pairs)

    base, digital_base = build_patient_base(primary_file, demographics_file)
    answers = build_answer_table(primary_file, secondary_file)

    if _DEBUG_ANALOG:
        # Stage 3: after build_content_base (captured inside build_patient_base → digital_base)
        _diag_rows("3. After build_content_base (digital_base)", digital_base, analog_pairs)
        # Stage 4: after build_answer_table (inner-joined with content pairs)
        _diag_answers("4. After build_answer_table (inner-joined with content)", answers, analog_pairs)

    # Remove rows with blank/missing questions so we don't generate "nan_" columns.
    # Keep a report of rows where Question is blank but an answer exists.
    try:
        import pandas as _pd
    except Exception:
        _pd = pd

    # Normalize obvious string representations of missing values on the raw Question column
    answers["Question"] = answers["Question"].replace(["nan", "NaN", ""], pd.NA)

    # Report rows where Question is blank/missing but there is an answer present
    blank_q_mask = (
        answers["Question"].isna()
        | answers["Question"].astype(str).str.strip().eq("")
        | answers["Question"].astype(str).str.lower().eq("nan")
    )

    report_mask = blank_q_mask & answers["Answer_Combined"].notna()
    blank_question_report = answers.loc[report_mask, [
        "Patient ID", "Pathway Name", "Content Name", "Entry Date", "Answer Text", "Answer Value"
    ]].copy()

    # Now drop any rows where Question is blank or normalizes to 'nan'
    answers = answers[~blank_q_mask].copy()

    if _DEBUG_ANALOG:
        _diag_answers("5. After blank-question filter", answers, analog_pairs)

    if answers.empty:
        final = base.copy()
        final = merge_demographics(final, demographics_file)
        if endpoint_file is not None:
            endpoints = prepare_endpoint_file(endpoint_file)
            final = final.merge(
                endpoints,
                on=["Patient ID", "Pathway Name"],
                how="left",
                suffixes=("", "_endpoint"),
            )
        _validate_final_output(final, base)
        final.attrs["transformation_report"] = build_transformation_report(final, digital_base)
        if output_file:
            final.to_csv(output_file, index=False, encoding="utf-8-sig")
        return final

    answers = answers.merge(
        base[["Patient ID", "Pathway Name"]],
        on=["Patient ID", "Pathway Name"],
        how="inner",
    )

    if _DEBUG_ANALOG:
        _diag_answers("6. After inner merge with base (full_base incl. analog)", answers, analog_pairs)

    answers["Is_Iterative_Content"] = answers["Content Name"].apply(_is_iterative_content_name)
    answers = answers.sort_values([
        "Patient ID",
        "Pathway Name",
        "Content Name",
        "Question_Normalized",
        "Entry Date",
    ], na_position="last")

    answers["Iteration"] = (
        answers
        .groupby([
            "Patient ID",
            "Pathway Name",
            "Content Name",
            "Question_Normalized",
        ], dropna=False)
        .cumcount()
        + 1
    )

    has_content_name = "Content Name" in answers.columns

    answers["Question_Iteration"] = answers.apply(
        lambda row: _build_question_iteration_column(row, has_content_name),
        axis=1,
    )

    if _DEBUG_ANALOG:
        _diag_answers("7. After Question_Iteration assignment (before collapse)", answers, analog_pairs)

    collapsed = _collapse_answer_groups(answers)
    conflicts = collapsed.attrs.get("conflicts", [])

    if _DEBUG_ANALOG:
        _diag_answers("8. After _collapse_answer_groups", collapsed, analog_pairs)

    final = collapsed.pivot_table(
        index=["Patient ID", "Pathway Name"],
        columns="Question_Iteration",
        values="Answer_Combined",
        aggfunc="first",
    ).reset_index()
    final.columns.name = None

    if _DEBUG_ANALOG:
        _diag_rows("9. After pivot (before merge with base)", final, analog_pairs)

    final = base.merge(final, on=["Patient ID", "Pathway Name"], how="left")

    if _DEBUG_ANALOG:
        _diag_rows("10. After base.merge(pivot, how='left') - final patient-level output", final, analog_pairs)
        q_cols = [c for c in final.columns if c not in ["Patient ID", "Pathway Name"]]
        if analog_pairs is not None and not analog_pairs.empty and q_cols:
            _ap_in_final = final.merge(analog_pairs, on=["Patient ID", "Pathway Name"], how="inner")
            _has_data = _ap_in_final[q_cols].notna().any(axis=1).sum()
            print(f"  analog patients with >=1 questionnaire value: {_has_data} / {len(_ap_in_final)}")

    # Check for unexpected questionnaire answers on analog patients.
    # Must run here, before demographics/endpoints are merged in, so that
    # the only non-null columns can be questionnaire answers.
    analog_answer_stats = _compute_analog_answer_stats(final, digital_base)

    final = merge_demographics(final, demographics_file)
    if endpoint_file is not None:
        endpoints = prepare_endpoint_file(endpoint_file)
        final = final.merge(
            endpoints,
            on=["Patient ID", "Pathway Name"],
            how="left",
            suffixes=("", "_endpoint"),
        )

    final = reorder_transformed_columns(final, demographics_file)

    # Ensure we did not accidentally create any columns beginning with 'nan_'
    nan_cols = [col for col in final.columns if isinstance(col, str) and col.lower().startswith("nan_")]
    if nan_cols:
        raise ValueError(f"Final output contains invalid columns starting with 'nan_': {nan_cols}")

    _validate_final_output(final, base)

    # Attach all attrs last so downstream merges cannot clear them.
    # Never store DataFrames in attrs — only plain Python types (str/int/list/dict).
    if conflicts:
        final.attrs["conflicts"] = [
            f"{conflict['Patient ID']}/{conflict['Pathway Name']}/{conflict['Question_Iteration']}: {conflict['values']}"
            for conflict in conflicts
        ]
    final.attrs["transformation_report"] = build_transformation_report(
        final, digital_base, analog_answer_stats
    )

    if output_file:
        final.to_csv(output_file, index=False, encoding="utf-8-sig")

    return final

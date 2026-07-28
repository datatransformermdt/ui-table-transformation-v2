import os
import pandas as pd
from transformation_common import (
    apply_question_canonical_map,
    build_answer_table,
    build_patient_base,
    _compute_source_stats,
    build_transformation_report,
    merge_demographics,
    prepare_endpoint_file,
    reorder_transformed_columns,
    read_input_file,
    clean_columns,
    _strip_accents,
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


def _normalize_iterative_name(text):
    if pd.isna(text):
        return ""
    return _strip_accents(str(text).strip().lower())


def _is_iterative_content_name(content_name, iterative_content_names=None):
    content_name = _normalize_iterative_name(content_name)
    if not content_name:
        return False

    if iterative_content_names:
        for candidate in iterative_content_names:
            if pd.isna(candidate):
                continue
            normalized_candidate = _normalize_iterative_name(candidate)
            if normalized_candidate and normalized_candidate in content_name:
                return True

    return any(
        _normalize_iterative_name(keyword) in content_name
        for keyword in ITERATIVE_CONTENT_NAME_KEYWORDS
    )


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
    iteration = str(int(row["Occurrence"]))

    if int(row["Occurrence"]) > 0:
        if has_content_name:
            return f"{content_name}_{iteration}_{question}"
        return f"{iteration}_{question}"

    if has_content_name:
        return f"{content_name}_{question}"

    return question


def _build_questionnaire_occurrence_validation(answers, final):
    source_pairs = answers[["Patient ID", "Pathway Name", "Content_Name_Normalized"]].copy()
    source_pairs = source_pairs.drop_duplicates()

    # A "submission" is one distinct questionnaire fill-in event — i.e. one
    # (Patient ID, Pathway Name, Content Name, Entry Date) — not one answer row.
    # A 5-question questionnaire filled in 3 times produces 15 answer rows but
    # only 3 submissions; counting rows here would flag every multi-question
    # questionnaire as a false mismatch even though no data was lost. `answers`
    # already carries one "Occurrence" number per submission event (shared
    # across all of that event's questions), so counting distinct Occurrence
    # values per questionnaire gives the true submission count.
    source_counts = (
        answers.groupby(["Patient ID", "Pathway Name", "Content_Name_Normalized"], dropna=False)["Occurrence"]
        .nunique()
        .reset_index(name="source_submissions")
    )

    output_pairs = final[["Patient ID", "Pathway Name"]].drop_duplicates()

    # Determine which (Patient, Pathway, Question_Iteration) answers actually
    # survived into a non-null cell of the pivoted output. This works directly
    # off the Question_Iteration labels already assigned before the pivot,
    # instead of re-parsing "Content_N_Question" column-name strings — that
    # regex approach breaks silently whenever Content Name or Question text
    # itself contains a "_<digits>_"-shaped substring (not unusual in real
    # questionnaire text), which would misattribute or drop occurrences with
    # no error. This version also catches genuine pivot collisions, where two
    # different submissions were assigned the same Question_Iteration label
    # and pivot_table's aggfunc="first" silently kept only one of them.
    id_cols = ["Patient ID", "Pathway Name"]
    q_iteration_cols = [
        c for c in answers["Question_Iteration"].dropna().unique() if c in final.columns
    ]
    if q_iteration_cols:
        melted = final[id_cols + q_iteration_cols].melt(
            id_vars=id_cols, var_name="Question_Iteration", value_name="_output_value"
        )
        survived_cells = melted.loc[
            melted["_output_value"].notna(), id_cols + ["Question_Iteration"]
        ].drop_duplicates()
        survived = answers.merge(survived_cells, on=id_cols + ["Question_Iteration"], how="inner")
    else:
        survived = answers.iloc[0:0]

    occurrence_output_counts = (
        survived.groupby(["Patient ID", "Pathway Name", "Content_Name_Normalized"], dropna=False)["Occurrence"]
        .max()
        .reset_index(name="output_occurrences")
    )

    comparison = source_counts.merge(
        occurrence_output_counts,
        on=["Patient ID", "Pathway Name", "Content_Name_Normalized"],
        how="left",
    )
    comparison["output_occurrences"] = comparison["output_occurrences"].fillna(0).astype(int)

    mismatch_mask = comparison["output_occurrences"] != comparison["source_submissions"]
    mismatch_rows = [
        {
            "Patient ID": row["Patient ID"],
            "Pathway Name": row["Pathway Name"],
            "Questionnaire": row["Content_Name_Normalized"],
            "source_submissions": int(row["source_submissions"]),
            "output_occurrences": int(row["output_occurrences"]),
        }
        for _, row in comparison.loc[mismatch_mask].iterrows()
    ]

    return {
        "source_total_patients": int(source_pairs[["Patient ID", "Pathway Name"]].drop_duplicates().shape[0]),
        "output_total_patients": int(output_pairs.shape[0]),
        "total_questionnaire_submissions_source": int(source_counts["source_submissions"].sum()),
        "total_questionnaire_occurrences_output": int(comparison["output_occurrences"].sum()),
        "mismatches": mismatch_rows,
    }


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


def process_iterative_files(primary_file, secondary_file, demographics_file=None, endpoint_file=None, output_file=None, iterative_content_names=None):
    """
    Iterative questionnaire workflow.

    Output: one row per patient/pathway, with repeated question answers suffixed
    _1, _2, _3 … for true iterative content.

    Non-iterative repeated answers are collapsed to the latest non-empty value.
    """
    # base = union(content pairs, answers pairs, demographics pairs)
    # content_base = pairs from the content/schedule file only
    base, content_base = build_patient_base(
        primary_file, demographics_file, answers_file=secondary_file
    )

    # answers is now built directly from the answers file — no content filter.
    answers = build_answer_table(secondary_file)

    if _DEBUG_ANALOG:
        _raw_answers = clean_columns(read_input_file(secondary_file))
        _answers_pairs = _raw_answers[["Patient ID", "Pathway Name"]].drop_duplicates()
        _not_in_content = _answers_pairs.merge(
            content_base[["Patient ID", "Pathway Name"]],
            on=["Patient ID", "Pathway Name"], how="left", indicator=True,
        )
        _answers_only = _not_in_content[_not_in_content["_merge"] == "left_only"][
            ["Patient ID", "Pathway Name"]
        ]
        print(f"\n{'='*72}")
        print("[DIAG] ITERATIVE PIPELINE - source summary")
        print(f"{'='*72}")
        print(f"  content pairs      : {len(content_base)}")
        print(f"  answer pairs       : {len(_answers_pairs)}")
        print(f"  answer-only pairs  : {len(_answers_only)} (no content record)")
        print(f"  full base          : {len(base)}")
        for _pw in sorted(_answers_only["Pathway Name"].dropna().astype(str).unique()):
            _n = (_answers_only["Pathway Name"] == _pw).sum()
            print(f"    answers-only pathway '{_pw}' ({_n} patients)")
        _diag_answers("2. Answers file (no content filter)", answers, _answers_only)

    # Normalize blank/missing question values
    answers["Question"] = answers["Question"].replace(["nan", "NaN", ""], pd.NA)

    blank_q_mask = (
        answers["Question"].isna()
        | answers["Question"].astype(str).str.strip().eq("")
        | answers["Question"].astype(str).str.lower().eq("nan")
    )

    # Track rows where Question is blank but an answer value exists
    report_mask = blank_q_mask & answers["Answer_Combined"].notna()
    blank_question_report = answers.loc[report_mask, [
        "Patient ID", "Pathway Name", "Content Name", "Entry Date", "Answer Text", "Answer Value"
    ]].copy()

    answers = answers[~blank_q_mask].copy()

    if _DEBUG_ANALOG:
        _diag_answers("3. After blank-question filter", answers,
                      _answers_only if _DEBUG_ANALOG else None)

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
        final.attrs["transformation_report"] = build_transformation_report(
            final, content_base
        )
        if output_file:
            final.to_csv(output_file, index=False, encoding="utf-8-sig")
        return final

    answers["Is_Iterative_Content"] = answers["Content Name"].apply(
        lambda value: _is_iterative_content_name(value, iterative_content_names)
    )

    has_content_name = "Content Name" in answers.columns

    # Occurrence numbers are assigned per *submission event* — i.e. per distinct
    # (Patient ID, Pathway Name, Content_Name_Normalized, Entry Date) — and then
    # shared across every question that belongs to that event. This keeps all
    # questions from the same questionnaire fill-in labeled with the same
    # occurrence number even when a particular question was skipped on some
    # occasions (assigning occurrence per-question independently would let
    # "Occurrence 2" mean a different physical submission for different
    # questions of the same questionnaire).
    events = (
        answers[["Patient ID", "Pathway Name", "Content_Name_Normalized", "Entry Date"]]
        .drop_duplicates()
        .sort_values(
            ["Patient ID", "Pathway Name", "Content_Name_Normalized", "Entry Date"],
            na_position="last",
        )
    )
    events["Occurrence"] = (
        events.groupby(
            ["Patient ID", "Pathway Name", "Content_Name_Normalized"],
            dropna=False, sort=False,
        )
        .cumcount()
        + 1
    )
    answers = answers.merge(
        events,
        on=["Patient ID", "Pathway Name", "Content_Name_Normalized", "Entry Date"],
        how="left",
    )
    answers["Occurrence"] = answers["Occurrence"].astype(int)

    answers["Question_Iteration"] = answers.apply(
        lambda row: _build_question_iteration_column(row, has_content_name),
        axis=1,
    )
    answers["Question_Iteration"] = apply_question_canonical_map(answers["Question_Iteration"])

    if _DEBUG_ANALOG:
        _diag_answers("4. After Question_Iteration assignment (before pivot)", answers,
                      _answers_only if _DEBUG_ANALOG else None)

    final = answers.pivot_table(
        index=["Patient ID", "Pathway Name"],
        columns="Question_Iteration",
        values="Answer_Combined",
        aggfunc="first",
    ).reset_index()
    final.columns.name = None

    if _DEBUG_ANALOG:
        _diag_rows("6. After pivot (before merge with base)", final,
                   _answers_only if _DEBUG_ANALOG else None)

    # Left merge: base provides one row per patient/pathway;
    # pivot fills in questionnaire columns where answers exist.
    final = base.merge(final, on=["Patient ID", "Pathway Name"], how="left")

    if _DEBUG_ANALOG:
        _diag_rows("7. After base.merge(pivot) - final output before demo/endpoints", final,
                   _answers_only if _DEBUG_ANALOG else None)
        _q_cols = [c for c in final.columns if c not in ["Patient ID", "Pathway Name"]]
        if _q_cols and not _answers_only.empty:
            _in_final = final.merge(_answers_only, on=["Patient ID", "Pathway Name"], how="inner")
            _has_data = _in_final[_q_cols].notna().any(axis=1).sum()
            print(f"  answers-only patients with >=1 questionnaire value: {_has_data} / {len(_in_final)}")

    # Compute per-source stats before demographics/endpoints are merged in.
    # At this point any non-null value in a non-key column is a questionnaire answer.
    source_stats = _compute_source_stats(final, content_base)

    # Collect pairs for the report
    _ans_pairs = answers[["Patient ID", "Pathway Name"]].drop_duplicates()

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

    nan_cols = [c for c in final.columns if isinstance(c, str) and c.lower().startswith("nan_")]
    if nan_cols:
        raise ValueError(f"Final output contains invalid columns starting with 'nan_': {nan_cols}")

    _validate_final_output(final, base)

    # Attach metadata last so merges above cannot clear attrs.
    # Never store DataFrames in attrs — only plain Python types.
    validation_report = _build_questionnaire_occurrence_validation(answers, final)
    final.attrs["questionnaire_occurrence_validation"] = validation_report
    final.attrs["transformation_report"] = build_transformation_report(
        final, content_base,
        source_stats=source_stats,
        answers_pairs=_ans_pairs,
    )
    final.attrs["transformation_report"]["questionnaire_occurrence_validation"] = validation_report

    if output_file:
        final.to_csv(output_file, index=False, encoding="utf-8-sig")

    return final

import pandas as pd
from transformation_common import (
    build_answer_table,
    build_content_base,
    merge_demographics,
    prepare_endpoint_file,
    reorder_transformed_columns,
)

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
            return f"{question}_{content_name}_{iteration}"
        return f"{question}_{iteration}"

    if has_content_name:
        return f"{question}_{content_name}"

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
    base = build_content_base(primary_file)
    answers = build_answer_table(primary_file, secondary_file)

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
        if output_file:
            final.to_csv(output_file, index=False, encoding="utf-8-sig")
        return final

    answers = answers.merge(
        base[["Patient ID", "Pathway Name"]],
        on=["Patient ID", "Pathway Name"],
        how="inner",
    )

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

    collapsed = _collapse_answer_groups(answers)
    conflicts = collapsed.attrs.get("conflicts", [])

    final = collapsed.pivot_table(
        index=["Patient ID", "Pathway Name"],
        columns="Question_Iteration",
        values="Answer_Combined",
        aggfunc="first",
    ).reset_index()
    final.columns.name = None

    final = base.merge(final, on=["Patient ID", "Pathway Name"], how="left")

    # Attach the blank-question report (may be empty) so callers can offer it for download
    final.attrs["blank_question_answers_report"] = blank_question_report

    if conflicts:
        final.attrs["conflicts"] = [
            f"{conflict['Patient ID']}/{conflict['Pathway Name']}/{conflict['Question_Iteration']}: {conflict['values']}"
            for conflict in conflicts
        ]

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

    if output_file:
        final.to_csv(output_file, index=False, encoding="utf-8-sig")

    return final

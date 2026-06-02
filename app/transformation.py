"""
transformation.py – router

Delegates to the correct workflow module based on the `workflow` parameter.
Keeping this file preserves backwards compatibility with any existing callers
(e.g. run_transformation.py, tests) that import `process_files` from here.
"""

from transformation_normal import process_normal_files
from transformation_iterative import process_iterative_files

WORKFLOWS = ("normal", "iterative")


def process_files(primary_file, secondary_file, workflow="normal",
                  demographics_file=None, output_file=None):
    """
    Run the requested transformation workflow.

    Parameters
    ----------
    primary_file : str or file-like
        Questions / content file (CSV or XLSX).
    secondary_file : str or file-like
        Answers file (CSV or XLSX).
    workflow : {"normal", "iterative"}
        "normal"     – one row per questionnaire event, dates included.
        "iterative"  – one row per patient, repeated answers suffixed _1, _2 ...
    demographics_file : str or file-like or None
        Optional demographics file containing Patient ID, Age, Sex.
    output_file : str or None
        If provided, the result is also written to this CSV path.

    Returns
    -------
    pandas.DataFrame
    """
    if workflow == "normal":
        return process_normal_files(
            primary_file,
            secondary_file,
            demographics_file=demographics_file,
            output_file=output_file,
        )

    if workflow == "iterative":
        return process_iterative_files(
            primary_file,
            secondary_file,
            demographics_file=demographics_file,
            output_file=output_file,
        )

    raise ValueError(
        f"Unknown workflow '{workflow}'. Valid options are: {WORKFLOWS}"
    )

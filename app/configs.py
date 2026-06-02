MEDTRONIC_CONFIG = {
    "rename_left": {
        "Input date": "Entry Date"
    },
    "rename_right": {},
    "merge_on": ["Entry Date"],
    "selected_columns_after_merge": [
        "Patient ID_x",
        "Pathway Name_x",
        "Content Name_x",
        "Scheduled date",
        "Entry Date",
        "Question",
        "Answer Text",
        "Answer Value",
    ],
    "rename_after_merge": {
        "Patient ID_x": "Patient ID",
        "Pathway Name_x": "Pathway Name",
        "Content Name_x": "Content Name",
    },
    "id_columns": [
        "Patient ID",
        "Entry Date",
        "Pathway Name",
        "Content Name",
        "Scheduled date",
    ],
    "field_column": "Question",
    "value_priority": ["Answer Value", "Answer Text"],
    "sort_columns": ["Patient ID", "Scheduled date", "Entry Date"],
}
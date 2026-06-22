# UI Table Transformation - Generalization Refactoring Guide

## Overview

The UI Table Transformation app has been refactored to support **generalized, config-driven workflows** that work with different hospitals, pathways, and data structures—instead of being hardcoded around the Ulm use case.

## What Changed

### New Architecture

The refactored app is built on a **schema mapping** architecture that separates data structure from business logic:

1. **Raw input columns** → **Standardized internal schema** → **Output dataset**
   
Instead of hardcoding column names like `"Patient ID"`, `"Question"`, `"Answer Text"`, the system now:
- Accepts flexible column names via configuration
- Auto-detects likely mappings from column names
- Allows manual mapping if auto-detection fails
- Uses standardized internal names for all processing

### New Modules

| Module | Purpose |
|--------|---------|
| `schema_mapping.py` | Column mapping and file role management |
| `validation.py` | Comprehensive input validation with clear error messages |
| `normalization.py` | Question text and content name normalization |
| `endpoints.py` | Clinical endpoint detection and derivation |
| `data_dictionary.py` | Generates comprehensive data dictionaries |
| `quality_reports.py` | Multi-tab quality and validation reports |
| `config_loader.py` | Loads transformation configs from YAML/CSV |

### Configuration Files

Located in `configs/` directory:

- **`ulm_erp.yaml`** - Medtronic Ulm Hospital ERP configuration
- **`generic_template.yaml`** - Template for new hospitals/projects

Located in `mappings/` directory:

- **`ulm_variable_mapping.csv`** - Example variable mapping for Ulm ERP

## How to Use

### For Ulm ERP (Current Use Case)

The existing workflow still works. The refactoring is backward-compatible:

```bash
python run_transformation.py
```

The `transformation.py` router delegates to `transformation_normal.py` or `transformation_iterative.py` as before.

### For New Hospitals/Datasets

#### Option 1: Use the Generalized Streamlit App

```bash
streamlit run app/streamlit_app_generalized.py
```

This provides a step-by-step workflow:

1. **Upload Files** - Load your data files. The generalized app now accepts multiple enrichment/demographics files: assign each uploaded demographics/enrichment file the `Demographics` role and the app will concatenate them before merging.
2. **Assign Roles** - Specify which file is Answers, Scheduled Content, Demographics, etc.
3. **Map Columns** - Auto-detect or manually map your column names to standard internal names
4. **Configure** - Select iterative content, set non-iterative repeat policy
5. **Validate** - Check for data quality issues
6. **Transform** - Run the transformation
7. **Download** - Get outputs (wide dataset, data dictionary, quality report)

#### Option 2: Create a YAML Configuration File

Create a new config in `configs/`:

```yaml
name: "Your Hospital Name"
description: "Your hospital's data transformation config"

column_mappings:
  demographics:
    patient_id: "Your Patient ID Column"
    age: "Your Age Column"
    sex: "Your Sex Column"
  
  scheduled_content:
    patient_id: "Patient ID"
    pathway_name: "Program Name"
    content_name: "Form Name"
    scheduled_date: "Scheduled Date"
    entry_date: "Completion Date"
  
  answers:
    patient_id: "Patient ID"
    pathway_name: "Program Name"
    content_name: "Form Name"
    question: "Item"
    answer: "Response"
    entry_date: "Response Date"

iterative_contents:
  - "Form 1"
  - "Form 2"

non_iterative_policy:
  policy: "latest_non_blank"
  flag_if_different: true

enabled_endpoints:
  - "length_of_stay_days"
  - "discharge_destination"
```

Then use it programmatically:

```python
from config_loader import ConfigLibrary, TransformationConfig
from schema_mapping import ColumnMapping

# Load your config
config = TransformationConfig.from_yaml("configs/your_hospital.yaml")

# Or create from dict
config = TransformationConfig.from_dict("name", config_dict)
```

#### Option 3: Use the Generic Template

```python
from config_loader import ConfigLibrary

config = ConfigLibrary.get_config("generic")
```

Then programmatically configure it for your needs.

## Key Features

### Column Mapping

Auto-detects standard column names:

```python
from schema_mapping import MappingBuilder

auto_mapping = MappingBuilder.auto_detect_mapping(df)
# Returns dict like: {"patient_id": "Patient ID", "question": "Item Text", ...}
```

Override with manual mapping:

```python
from schema_mapping import ColumnMapping

mapping = ColumnMapping({
    "patient_id": "Your Patient Column",
    "question": "Your Question Column",
    ...
})

df_standardized = mapping.apply_to_dataframe(df)
```

### File Role Classification

Specify what each uploaded file contains:

```python
from schema_mapping import FileRole

roles = [
    FileRole.DEMOGRAPHICS,
    FileRole.SCHEDULED_CONTENT,
    FileRole.ANSWERS,
    FileRole.ENDPOINTS,
    FileRole.ADHERENCE,
]
```

### Comprehensive Validation

Get detailed, actionable validation reports:

```python
from validation import SchemaValidator, ValidationLevel

report = SchemaValidator.validate_file_for_role(df, FileRole.ANSWERS, mapping, "answers.csv")

if report.has_errors():
    for error in report.get_errors():
        print(f"ERROR: {error.message}")

if report.get_warnings():
    for warning in report.get_warnings():
        print(f"WARNING: {warning.message}")
```

### Question Text Normalization

Automatically finds duplicate questions hidden by punctuation/spacing:

```python
from normalization import normalize_question_text, find_duplicate_questions

# Normalize a question
clean = normalize_question_text("BMI?? (Body Mass Index)")
# Returns: "BMI Body Mass Index"

# Find duplicates in dataframe
duplicates = find_duplicate_questions(df, question_col="Question")
# Returns: {"Gewicht": [("Gewicht", 15), ("Gewicht??", 2)], ...}
```

### Clinical Endpoints

Detect, derive, and report on clinical endpoints:

```python
from endpoints import EndpointRegistry, EndpointDeriver

registry = EndpointRegistry()

# Search for endpoints in dataframe
endpoints = registry.get_all_endpoint_statuses(df, question_col="question")

# Derive endpoints
df["length_of_stay_days"] = EndpointDeriver.derive_length_of_stay(df)
df["pathway_adherence_pct"] = EndpointDeriver.derive_pathway_adherence(df)

# Get availability report
report_df = registry.get_endpoint_availability_report(df)
```

### Data Dictionary Generation

Automatically generate comprehensive data dictionaries:

```python
from data_dictionary import DataDictionaryGenerator

generator = DataDictionaryGenerator()
generator.add_from_dataframe(output_df, source_file="output")
generator.assign_clinical_phase()

dictionary = generator.to_dataframe()
dictionary.to_csv("data_dictionary.csv", index=False)
```

### Quality Reports

Generate multi-tab Excel quality reports:

```python
from quality_reports import QualityReportGenerator

report_tabs = QualityReportGenerator.generate_complete_report(
    raw_df=raw_data,
    final_df=output_data,
    id_cols=["patient_id", "pathway_name"],
    question_col="question",
    iterative_contents=["BMI"]
)

# Write to Excel
with pd.ExcelWriter("quality_report.xlsx") as writer:
    for tab_name, df in report_tabs.items():
        df.to_excel(writer, sheet_name=tab_name, index=False)
```

## Standard Internal Schema

The system uses these standardized column names internally:

### Required Fields
- `patient_id` - Patient identifier
- `pathway_name` - Pathway/program name
- `content_name` - Questionnaire/content name
- `question` - Question text
- `answer` - Answer value (combines text and numeric)

### Temporal Fields
- `entry_date` - When response was recorded
- `scheduled_date` - When the content was scheduled
- `admission_date` - Hospital admission date
- `discharge_date` - Hospital discharge date

### Metadata Fields
- `source_file` - Which file this data came from
- `source_row_id` - Row ID in source file
- `content_status` - Status (completed, pending, etc.)

### Endpoint Fields
- `discharge_destination` - Where patient was discharged
- `mortality_status` - Did patient die?
- `pathway_adherence_pct` - Percentage of pathway completed

## Backward Compatibility

The refactoring **maintains full backward compatibility**:

- Existing `process_files()` calls work as before
- Hardcoded column names for Ulm ERP are preserved
- Legacy `transformation_normal.py` and `transformation_iterative.py` unchanged
- Original Streamlit app (`streamlit_app.py`) still works

## Migration Path

For hospitals currently using the Ulm-specific workflow:

1. **Phase 1** (Stabilize): Add new output files using new modules
   - Data dictionary
   - Long audit trail
   - Quality report
   - Endpoint availability report

2. **Phase 2** (Generalize): Create a YAML config for your hospital
   - Document your column names
   - Specify iterative content
   - Define endpoint mappings

3. **Phase 3** (Extend): Use generalized app for other projects
   - Reuse infrastructure for similar hospitals
   - Build custom endpoints and derivations

## Example: Adding Support for a New Hospital

### Step 1: Create Configuration

`configs/new_hospital.yaml`:
```yaml
name: "New Hospital Name"
description: "Hospital XYZ data transformation"

column_mappings:
  answers:
    patient_id: "PatientCode"
    pathway_name: "ClinicalPath"
    content_name: "FormCode"
    question: "ItemLabel"
    answer: "PatientResponse"
    entry_date: "ResponseTimestamp"

iterative_contents:
  - "Daily Vitals"
  - "Symptom Tracker"

enabled_endpoints:
  - "length_of_stay_days"
  - "pathway_adherence_pct"
```

### Step 2: Use in Code

```python
from config_loader import TransformationConfig

config = TransformationConfig.from_yaml("configs/new_hospital.yaml")
mapping = config.get_mapping_for_role("answers")

df = read_input_file_with_mapping("answers.csv", mapping)
# Now has standardized columns: patient_id, pathway_name, etc.
```

### Step 3: Run Transformation

```python
result = process_files(
    primary_file="answers.csv",
    secondary_file="scheduled_content.csv",
    demographics_file="demographics.csv",
    workflow="normal"
)
```

## Testing

New tests should be added to `tests/`:

- `test_schema_mapping.py` - Column mapping logic
- `test_validation.py` - Input validation
- `test_endpoints.py` - Endpoint detection/derivation
- `test_data_dictionary.py` - Data dictionary generation
- `test_quality_reports.py` - Report generation

Example:

```python
from schema_mapping import MappingBuilder

def test_auto_detect_mapping():
    df = pd.DataFrame({
        "Patient ID": [1, 2],
        "Question": ["Q1", "Q2"],
        "Answer": ["A", "B"]
    })
    
    mapping_dict = MappingBuilder.auto_detect_mapping(df)
    assert mapping_dict["patient_id"] == "Patient ID"
    assert mapping_dict["question"] == "Question"
    assert mapping_dict["answer"] == "Answer"
```

## FAQ

**Q: Does this break existing Ulm workflows?**
A: No. The refactoring is backward compatible. Existing code and configs continue to work unchanged.

**Q: How do I add support for my hospital?**
A: Create a YAML config in `configs/` describing your column names and iterative content. See `configs/generic_template.yaml`.

**Q: Can I use the old hardcoded app?**
A: Yes! The original `streamlit_app.py` and hardcoded workflow still work. The new `streamlit_app_generalized.py` is the flexible version.

**Q: How do I handle custom variables that don't fit the standard schema?**
A: Use the `variable_mapping.csv` file to define custom mappings and variable names.

**Q: What if my data structure is completely different?**
A: The schema is flexible. You can:
1. Create custom file roles in `schema_mapping.py`
2. Extend the transformation logic
3. Override normalization/validation rules

## Next Steps

1. **Test** with your hospital data
2. **Create** configs for other projects
3. **Extend** with custom endpoints and derivations
4. **Integrate** with Cortex (planned future phase)

## Support

For questions or issues:
- Review the docstrings in each module
- Check `configs/generic_template.yaml` for examples
- Look at `tests/` for usage examples

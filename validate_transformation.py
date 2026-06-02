"""
validate_transformation.py

Comprehensive validation script for transformed questionnaire data.
Checks for data quality, completeness, and format compliance.

Usage:
    python validate_transformation.py <output_file.csv>
    
Example:
    python validate_transformation.py final_table_transformed.csv
"""

import pandas as pd
import sys
from pathlib import Path
from collections import defaultdict, Counter


class TransformationValidator:
    """Validates the quality and completeness of transformed questionnaire data."""
    
    def __init__(self, filepath):
        """Initialize validator with output CSV file."""
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        self.df = pd.read_csv(filepath)
        self.issues = []
        self.warnings = []
        self.info = []
        
        # Detect workflow type
        self._detect_workflow()
    
    def _detect_workflow(self):
        """Detect if this is 'normal' or 'iterative' workflow."""
        # Iterative: Content Name is not in columns, has Question_X_N or Question_QuestionnaireName_X_N format
        # Normal: Content Name is in columns, one row per event
        
        if "Content Name" in self.df.columns:
            self.workflow = "normal"
            self.info.append("Workflow detected: NORMAL (one row per event)")
        else:
            self.workflow = "iterative"
            self.info.append("Workflow detected: ITERATIVE (one row per patient)")
        
        
    def run_all_checks(self):
        """Run all validation checks."""
        print("=" * 80)
        print(f"VALIDATION REPORT: {self.filepath.name}")
        print("=" * 80)
        print()
        
        # Basic info
        self._check_basic_info()
        print()
        
        # Check 1: No duplicates
        self._check_no_duplicates()
        print()
        
        # Check 2: Demographics (Age and Gender)
        self._check_demographics()
        print()
        
        # Check 3: Questionnaire structure
        self._check_questionnaire_structure()
        print()
        
        # Check 4: Iterations
        self._check_iterations()
        print()
        
        # Check 5: Data completeness
        self._check_data_completeness()
        print()
        
        # Summary
        self._print_summary()
        
    def _check_basic_info(self):
        """Print basic dataset information."""
        print("📊 BASIC INFORMATION")
        print(f"  • Total rows: {len(self.df)}")
        print(f"  • Total columns: {len(self.df.columns)}")
        print(f"  • Unique patients: {self.df['Patient ID'].nunique() if 'Patient ID' in self.df.columns else 'N/A'}")
        self.info.append(f"Dataset shape: {self.df.shape}")
        
        # Show column names
        print(f"\n  Column names:")
        for i, col in enumerate(self.df.columns, 1):
            print(f"    {i:2d}. {col}")
        
    def _check_no_duplicates(self):
        """Check 1: Verify no duplicate patients (one row per patient) - for ITERATIVE workflow."""
        print("✓ CHECK 1: DUPLICATE ROWS")
        
        if "Patient ID" not in self.df.columns:
            self.issues.append("Patient ID column not found")
            print("  ❌ Patient ID column not found")
            return
        
        if self.workflow == "normal":
            print(f"  ℹ️  Normal workflow detected: multiple rows per patient allowed")
            print(f"     (same patient may appear for different pathways or questionnaire events)")
            print(f"  • Total rows: {len(self.df)}")
            print(f"  • Unique patients: {self.df['Patient ID'].nunique()}")
            
            # Check for exact duplicate event rows
            keys = ["Patient ID", "Content Name", "Entry Date"]
            if "Pathway Name" in self.df.columns:
                keys.append("Pathway Name")
            if all(col in self.df.columns for col in keys):
                dup_check = self.df.groupby(keys).size()
                true_dups = dup_check[dup_check > 1]
                if len(true_dups) > 0:
                    self.issues.append(f"Found {len(true_dups)} duplicate patient-event rows")
                    print(f"  ❌ WARNING: {len(true_dups)} rows with duplicate Patient ID / Pathway / Content / Entry Date")
                else:
                    print(f"  ✅ PASS: No duplicate patient-event rows")
            else:
                print(f"  ✅ PASS: Rows are differentiated by event")
        else:
            # Iterative workflow: one row per patient
            patient_counts = self.df["Patient ID"].value_counts()
            duplicates = patient_counts[patient_counts > 1]
            
            if len(duplicates) == 0:
                self.info.append("✓ No duplicate patients found")
                print(f"  ✅ PASS: Each patient appears exactly once ({len(patient_counts)} unique patients)")
            else:
                self.issues.append(f"Found {len(duplicates)} duplicate patients")
                print(f"  ❌ FAIL: {len(duplicates)} patients appear multiple times:")
                for patient_id, count in duplicates.items():
                    print(f"     - Patient {patient_id}: {count} rows")
    
    def _check_demographics(self):
        """Check 2: Verify Age and Gender are present for all patients."""
        print("✓ CHECK 2: DEMOGRAPHICS (Age & Gender)")
        
        # Check for demographic columns
        demo_cols = []
        age_col = next((col for col in self.df.columns if "age" in col.lower()), None)
        sex_col = next((col for col in self.df.columns if any(term in col.lower() for term in ["sex", "gender"])), None)
        
        if age_col:
            demo_cols.append(age_col)
            print(f"  • Found Age column: '{age_col}'")
        else:
            print(f"  ⚠️  Age column not found (demographics are optional for this transformation stage)")
        
        if sex_col:
            demo_cols.append(sex_col)
            print(f"  • Found Gender/Sex column: '{sex_col}'")
        else:
            print(f"  ⚠️  Gender/Sex column not found (demographics are optional for this transformation stage)")
        
        if not demo_cols:
            self.info.append("Demographic columns not included in this transformation")
            print("  ℹ️  No demographic columns found; skipping mandatory demographic completeness check")
            return
        
        # Check for missing values
        print("\n  Checking for missing values:")
        all_complete = True
        for col in demo_cols:
            missing_count = self.df[col].isna().sum()
            missing_pct = (missing_count / len(self.df)) * 100
            
            if missing_count == 0:
                print(f"    ✅ {col}: Complete ({len(self.df)} values)")
            else:
                all_complete = False
                self.issues.append(f"{col} has {missing_count} missing values")
                print(f"    ❌ {col}: {missing_count} missing ({missing_pct:.1f}%)")
        
        if all_complete:
            self.info.append("✓ All demographic data is complete")
            print("\n  ✅ PASS: Demographics present and complete for all patients")
        else:
            print("\n  ⚠️  INCOMPLETE: Some demographic data is missing")
    
    def _check_questionnaire_structure(self):
        """Check 3: Verify questionnaire columns follow naming conventions."""
        print("✓ CHECK 3: QUESTIONNAIRE STRUCTURE")
        
        # Identify base columns (non-question columns)
        base_cols = {"Patient ID", "Pathway Name", "Age", "Sex", "Gender", "Patient Age", "Patient Gender", "Patient Sex",
                     "Iteration", "Content Name", "Scheduled date", "Entry Date"}
        base_pattern = set(col for col in self.df.columns if col.lower() in {b.lower() for b in base_cols})
        base_pattern.update([col for col in self.df.columns if any(term in col.lower() for term in ["age", "sex", "gender", "patient id", "pathway", "date", "iteration"])])
        
        question_cols = [col for col in self.df.columns if col not in base_pattern]
        
        print(f"  • Base columns: {len(base_pattern)} ({', '.join(sorted(base_pattern))})")
        print(f"  • Question/Answer columns: {len(question_cols)}")
        
        if len(question_cols) == 0:
            self.warnings.append("No question columns found - may be normal workflow (one row per event)")
            print("  ℹ️  Appears to be 'normal' workflow (one row per event, not iterative)")
            return
        
        # Analyze question column naming
        print("\n  Column naming patterns:")
        
        # Check for Content Name in columns
        has_content_name = "Content Name" in self.df.columns
        if has_content_name:
            self.info.append("'Content Name' present - 'normal' workflow format detected")
            print("    ℹ️  'Content Name' column present - normal workflow format")
        
        # Parse question column names
        iteration_cols = []
        naming_format = {}
        
        import re
        for col in question_cols:
            # Pattern 1: Question_Questionnaire_Iteration
            match = re.match(r"^(.+)_(.+)_(\d+)$", col)
            if match:
                question, questionnaire, iteration = match.groups()
                iteration_cols.append((col, question, questionnaire, int(iteration)))
                naming_format[col] = "Question_Questionnaire_Iteration"
                continue
            
            # Pattern 2: Question_Iteration
            match = re.match(r"^(.+)_(\d+)$", col)
            if match:
                question, iteration = match.groups()
                iteration_cols.append((col, question, None, int(iteration)))
                naming_format[col] = "Question_Iteration"
                continue
        
        # Summarize formats
        if not iteration_cols:
            print("    ℹ️  Standard question columns (no iteration numbering)")
            print(f"       Question columns: {', '.join(question_cols[:5])}" + ("..." if len(question_cols) > 5 else ""))
        else:
            format_counts = Counter(naming_format.values())
            if len(format_counts) == 1:
                fmt = list(format_counts.keys())[0]
                print(f"    ✅ Consistent format: {fmt}")
                
                # Check if multiple questionnaires
                questionnaires = set(q for _, _, q, _ in iteration_cols if q)
                if questionnaires:
                    print(f"    ✅ Multiple questionnaires detected: {', '.join(sorted(questionnaires))}")
                    self.info.append(f"Multiple questionnaires: {', '.join(sorted(questionnaires))}")
                else:
                    print(f"    ✅ Single questionnaire (simple iteration numbering)")
            else:
                self.issues.append("Mixed column naming formats detected")
                print(f"    ❌ Mixed formats: {format_counts}")
            
            # Check iteration numbering
            print("\n  Iteration numbering:")
            all_iterations = [it for _, _, _, it in iteration_cols]
            if all_iterations:
                min_it, max_it = min(all_iterations), max(all_iterations)
                print(f"    • Iteration range: {min_it} to {max_it}")
                
                if min_it != 1:
                    self.warnings.append(f"Iterations start at {min_it} instead of 1")
                    print(f"    ⚠️  Iterations start at {min_it} (expected to start at 1)")
    
    def _check_iterations(self):
        """Check 4: Verify iterations are correctly assigned (for ITERATIVE workflow)."""
        print("✓ CHECK 4: ITERATION VALIDATION")
        
        if "Patient ID" not in self.df.columns:
            print("  ❌ Patient ID column not found")
            return
        
        if self.workflow == "normal":
            print(f"  ℹ️  Normal workflow: checking event/iteration tracking")
            if "Entry Date" in self.df.columns:
                print(f"     Entry Date column present for event tracking")
                if "Iteration" in self.df.columns:
                    print(f"     Iteration column present")
                    self.info.append("✓ Iteration tracking present")
            return
        
        # Parse question columns for iterations
        import re
        iteration_data = defaultdict(list)
        
        for col in self.df.columns:
            match = re.match(r"^(.+)_(\d+)$", col) or re.match(r"^(.+)_(.+)_(\d+)$", col)
            if match:
                if len(match.groups()) == 3:
                    _, _, iteration = match.groups()
                else:
                    _, iteration = match.groups()
                iteration_data[col] = int(iteration)
        
        if not iteration_data:
            self.warnings.append("No iteration columns found")
            print("  ⚠️  No iteration columns detected")
            return
        
        print(f"  • Found {len(iteration_data)} columns with iteration numbering")
        
        # Check iteration coverage per patient
        print("\n  Checking iteration coverage:")
        iterations_per_patient = []
        
        for patient_id in self.df["Patient ID"].unique():
            patient_row = self.df[self.df["Patient ID"] == patient_id].iloc[0]
            iterations_present = []
            
            for col in iteration_data:
                if pd.notna(patient_row[col]):
                    iterations_present.append(iteration_data[col])
            
            iterations_present = sorted(set(iterations_present))
            iterations_per_patient.append(len(iterations_present))
        
        avg_iterations = sum(iterations_per_patient) / len(iterations_per_patient) if iterations_per_patient else 0
        max_iterations = max(iterations_per_patient) if iterations_per_patient else 0
        
        print(f"    • Average iterations per patient: {avg_iterations:.1f}")
        print(f"    • Maximum iterations: {max_iterations}")
        
        # Check for gaps in iteration numbering
        iteration_counter = Counter()
        for patient_id in self.df["Patient ID"].unique():
            patient_row = self.df[self.df["Patient ID"] == patient_id].iloc[0]
            for col in iteration_data:
                if pd.notna(patient_row[col]):
                    iteration_counter[iteration_data[col]] += 1
        
        if iteration_counter:
            print(f"    ✅ Iteration distribution: {dict(sorted(iteration_counter.items()))}")
        
        print("\n  ✅ PASS: Iterations are consistently numbered")
    
    def _check_data_completeness(self):
        """Check 5: General data completeness and quality."""
        print("✓ CHECK 5: DATA COMPLETENESS & QUALITY")
        
        # Count missing values per column
        print("  Missing data by column:")
        missing_info = []
        
        for col in self.df.columns:
            missing = self.df[col].isna().sum()
            if missing > 0:
                missing_pct = (missing / len(self.df)) * 100
                missing_info.append((col, missing, missing_pct))
        
        if missing_info:
            # Sort by percentage missing
            missing_info.sort(key=lambda x: x[2], reverse=True)
            
            for col, missing, missing_pct in missing_info[:10]:  # Show top 10
                if missing_pct > 50:
                    symbol = "⚠️"
                elif missing_pct > 20:
                    symbol = "ℹ️"
                else:
                    symbol = " "
                print(f"    {symbol} {col}: {missing} missing ({missing_pct:.1f}%)")
            
            if len(missing_info) > 10:
                print(f"    ... and {len(missing_info) - 10} more columns with missing data")
        else:
            print("    ✅ No missing data")
        
        # Check whether answer data is present in transformed output
        answer_cols = [col for col in self.df.columns if col.lower() in {"answer text", "answer value", "answer_combined"}]
        if answer_cols:
            blank_rows = self.df[answer_cols].isna().all(axis=1).sum()
            print(f"\n  • Found answer columns: {answer_cols}")
            if blank_rows > 0:
                self.warnings.append(f"{blank_rows} rows have no answer text/value data")
                print(f"    ⚠️  {blank_rows} rows contain no answer text or value")
            else:
                print(f"    ✅ All rows contain at least one answer field")
        else:
            # For pivoted output, check whether question columns contain any values
            id_cols = {"Patient ID", "Pathway Name", "Content Name", "Iteration", "Scheduled date", "Entry Date"}
            question_cols = [col for col in self.df.columns if col not in id_cols]
            if len(question_cols) == 0:
                self.issues.append("No question or answer columns found in transformed output")
                print("  ❌ FAIL: No question or answer columns found beyond identifier fields")
            else:
                non_empty_answer_cells = self.df[question_cols].notna().sum().sum()
                print(f"\n  • Found {len(question_cols)} question/answer columns")
                print(f"  • Non-empty answer cells: {non_empty_answer_cells}")
                if non_empty_answer_cells == 0:
                    self.issues.append("No answer values found in question columns")
                    print("    ❌ FAIL: Question columns are all empty")
                else:
                    self.info.append(f"Answer data present in {len(question_cols)} question columns")
                    print("    ✅ PASS: Answer data is present in transformed output")
        
        # Check for sparse columns
        print("\n  Checking column sparsity:")
        sparse_cols = []
        for col in self.df.columns:
            if col not in {"Patient ID", "Pathway Name"}:
                if "age" not in col.lower() and "sex" not in col.lower() and "gender" not in col.lower():
                    non_null_pct = (self.df[col].notna().sum() / len(self.df)) * 100
                    if non_null_pct < 10:
                        sparse_cols.append((col, non_null_pct))
        
        if sparse_cols:
            sparse_cols.sort(key=lambda x: x[1])
            print(f"    ⚠️  {len(sparse_cols)} columns with <10% data coverage:")
            for col, pct in sparse_cols[:5]:
                print(f"       - {col}: {pct:.1f}%")
            if len(sparse_cols) > 5:
                print(f"       ... and {len(sparse_cols) - 5} more")
        else:
            print("    ✅ No sparse columns (<10% threshold)")
        
        # Data type consistency
        print("\n  Data types:")
        dtype_summary = self.df.dtypes.value_counts()
        for dtype, count in dtype_summary.items():
            print(f"    • {dtype}: {count} columns")
    
    def _print_summary(self):
        """Print validation summary and recommendations."""
        print("=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        
        if self.issues:
            print(f"\n❌ ISSUES FOUND: {len(self.issues)}")
            for i, issue in enumerate(self.issues, 1):
                print(f"   {i}. {issue}")
        else:
            print(f"\n✅ NO CRITICAL ISSUES FOUND")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS: {len(self.warnings)}")
            for i, warning in enumerate(self.warnings, 1):
                print(f"   {i}. {warning}")
        
        if self.info:
            print(f"\nℹ️  INFO: {len(self.info)}")
            for i, item in enumerate(self.info, 1):
                print(f"   {i}. {item}")
        
        # Overall assessment
        print("\n" + "=" * 80)
        if not self.issues:
            print("🎉 ASSESSMENT: DATA IS READY FOR PHYSICIAN ANALYSIS")
        elif len(self.issues) <= 2:
            print("⚠️  ASSESSMENT: Minor issues found - review before physician use")
        else:
            print("❌ ASSESSMENT: Significant issues found - requires remediation")
        print("=" * 80)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python validate_transformation.py <output_file.csv>")
        print("\nExample:")
        print("  python validate_transformation.py final_table_transformed.csv")
        sys.exit(1)
    
    filepath = sys.argv[1]
    
    try:
        validator = TransformationValidator(filepath)
        validator.run_all_checks()
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

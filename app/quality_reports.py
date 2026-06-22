"""
quality_reports.py

Generates comprehensive data quality reports including:
- Missing required columns
- Row coverage and non-responders
- Duplicate and normalized duplicate questions
- Non-iterative repeated answer conflicts
- Endpoint availability
- General warnings and data quality metrics
"""

import pandas as pd
from typing import Dict, List, Optional, Set, Tuple
from datetime import datetime
import io


class QualityReportGenerator:
    """Generates comprehensive data quality reports."""
    
    def __init__(self):
        self.report_data: Dict[str, pd.DataFrame] = {}
        self.summary_stats: Dict[str, any] = {}
    
    def add_summary_stats(self, stats: Dict[str, any]):
        """Add summary statistics."""
        self.summary_stats.update(stats)
    
    def generate_summary_tab(self) -> pd.DataFrame:
        """
        Generate summary statistics tab.
        
        Returns
        -------
        pd.DataFrame
            Summary statistics
        """
        rows = []
        
        for metric, value in self.summary_stats.items():
            rows.append({
                "Metric": metric,
                "Value": value,
            })
        
        return pd.DataFrame(rows)
    
    def generate_missing_columns_tab(self, df: pd.DataFrame, 
                                    expected_columns: List[str]) -> pd.DataFrame:
        """
        Generate tab for missing required columns.
        
        Parameters
        ----------
        df : pd.DataFrame
            Input dataframe
        expected_columns : list of str
            Expected column names
        
        Returns
        -------
        pd.DataFrame
            Report of missing columns
        """
        present = set(df.columns)
        expected = set(expected_columns)
        missing = expected - present
        
        if not missing:
            return pd.DataFrame({
                "Status": ["✓ All expected columns present"]
            })
        
        rows = []
        for col in sorted(missing):
            rows.append({
                "Missing Column": col,
                "Status": "NOT FOUND",
            })
        
        return pd.DataFrame(rows) if rows else pd.DataFrame({
            "Status": ["✓ All expected columns present"]
        })
    
    def generate_row_coverage_tab(self, expected_population_df: pd.DataFrame,
                                 final_df: pd.DataFrame,
                                 id_cols: List[str]) -> pd.DataFrame:
        """
        Generate row coverage report.
        
        Parameters
        ----------
        expected_population_df : pd.DataFrame
            Expected patient-pathway population
        final_df : pd.DataFrame
            Final output dataset
        id_cols : list of str
            ID column names
        
        Returns
        -------
        pd.DataFrame
            Row coverage report
        """
        # Create composite keys
        if not id_cols or not all(col in expected_population_df.columns for col in id_cols):
            return pd.DataFrame({
                "Status": ["Cannot determine coverage without ID columns"]
            })
        
        expected_keys = set(expected_population_df[id_cols].drop_duplicates().apply(
            lambda row: tuple(row), axis=1
        ))
        
        if id_cols[0] in final_df.columns:
            final_keys = set(final_df[id_cols].drop_duplicates().apply(
                lambda row: tuple(row), axis=1
            )) if all(col in final_df.columns for col in id_cols) else set()
        else:
            final_keys = set()
        
        missing_keys = expected_keys - final_keys
        
        rows = [
            {"Metric": "Total Expected Rows", "Count": len(expected_keys)},
            {"Metric": "Rows in Final Output", "Count": len(final_keys)},
            {"Metric": "Missing Rows", "Count": len(missing_keys)},
            {"Metric": "Coverage %", "Count": f"{100 * len(final_keys) / len(expected_keys):.1f}%" if expected_keys else "N/A"},
        ]
        
        return pd.DataFrame(rows)
    
    @staticmethod
    def generate_non_responder_rows_tab(base_df: pd.DataFrame, 
                                       answers_df: pd.DataFrame,
                                       id_cols: List[str]) -> pd.DataFrame:
        """
        Identify rows with no questionnaire responses.
        
        Parameters
        ----------
        base_df : pd.DataFrame
            Expected base population
        answers_df : pd.DataFrame
            Rows with questionnaire answers
        id_cols : list of str
            ID column names
        
        Returns
        -------
        pd.DataFrame
            Non-responder report
        """
        if not id_cols or not all(col in base_df.columns for col in id_cols):
            return pd.DataFrame()
        
        base_keys = set(base_df[id_cols].drop_duplicates().apply(
            lambda row: tuple(row), axis=1
        ))
        
        if all(col in answers_df.columns for col in id_cols):
            answer_keys = set(answers_df[id_cols].drop_duplicates().apply(
                lambda row: tuple(row), axis=1
            ))
        else:
            answer_keys = set()
        
        non_responder_keys = base_keys - answer_keys
        
        rows = []
        for key in sorted(non_responder_keys):
            row_dict = {id_cols[i]: key[i] for i in range(len(id_cols))}
            row_dict["Status"] = "Non-responder"
            rows.append(row_dict)
        
        if not rows:
            return pd.DataFrame({
                "Status": ["✓ No non-responders (all expected rows have responses)"]
            })
        
        return pd.DataFrame(rows)
    
    @staticmethod
    def generate_duplicate_columns_tab(df: pd.DataFrame) -> pd.DataFrame:
        """
        Find exact duplicate columns (same name appearing multiple times).
        
        Parameters
        ----------
        df : pd.DataFrame
            Input dataframe
        
        Returns
        -------
        pd.DataFrame
            Report of duplicate columns
        """
        column_counts = df.columns.value_counts()
        duplicates = column_counts[column_counts > 1]
        
        if duplicates.empty:
            return pd.DataFrame({
                "Status": ["✓ No duplicate column names found"]
            })
        
        rows = []
        for col, count in duplicates.items():
            rows.append({
                "Column Name": col,
                "Count": count,
                "Status": f"DUPLICATE ({count} occurrences)"
            })
        
        return pd.DataFrame(rows)
    
    @staticmethod
    def generate_normalized_duplicates_tab(df: pd.DataFrame, 
                                          question_col: str = "question") -> pd.DataFrame:
        """
        Find questions that normalize to the same text.
        
        Parameters
        ----------
        df : pd.DataFrame
            Input dataframe with questions
        question_col : str
            Column name containing questions
        
        Returns
        -------
        pd.DataFrame
            Report of normalized duplicate questions
        """
        if question_col not in df.columns:
            return pd.DataFrame({
                "Status": [f"Question column '{question_col}' not found"]
            })
        
        from normalization import normalize_question_text
        
        df_copy = df[[question_col]].drop_duplicates()
        df_copy["normalized"] = df_copy[question_col].apply(normalize_question_text)
        
        # Find groups with multiple raw questions
        duplicates = df_copy.groupby("normalized")[question_col].apply(list)
        duplicates = duplicates[duplicates.apply(len) > 1]
        
        if duplicates.empty:
            return pd.DataFrame({
                "Status": ["✓ No normalized duplicate questions found"]
            })
        
        rows = []
        for normalized, originals in duplicates.items():
            rows.append({
                "Normalized Form": normalized,
                "Raw Variations": "; ".join(originals),
                "Count": len(originals),
                "Status": "DUPLICATE"
            })
        
        return pd.DataFrame(rows)
    
    @staticmethod
    def generate_non_iterative_conflicts_tab(df: pd.DataFrame,
                                            id_cols: List[str],
                                            question_col: str,
                                            answer_col: str,
                                            iterative_contents: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Find repeated different answers in non-iterative questionnaires.
        
        Parameters
        ----------
        df : pd.DataFrame
            Input dataframe in long format
        id_cols : list of str
            Patient/pathway ID columns
        question_col : str
            Column name for questions
        answer_col : str
            Column name for answers
        iterative_contents : list of str, optional
            Content names that are iterative (excluded from conflict check)
        
        Returns
        -------
        pd.DataFrame
            Report of conflicts
        """
        if iterative_contents is None:
            iterative_contents = []
        
        # Filter to non-iterative content
        if "content_name" in df.columns:
            df_filtered = df[~df["content_name"].isin(iterative_contents)].copy()
        else:
            df_filtered = df.copy()
        
        # Find rows with repeated different answers
        conflicts = []
        
        for group_cols in [id_cols + [question_col]]:
            if all(col in df_filtered.columns for col in group_cols):
                grouped = df_filtered.groupby(group_cols)[answer_col].nunique()
                conflict_rows = grouped[grouped > 1]
                
                for group_key, num_answers in conflict_rows.items():
                    row_dict = {group_cols[i]: group_key[i] for i in range(len(group_cols))}
                    row_dict["Number of Different Answers"] = int(num_answers)
                    row_dict["Status"] = "CONFLICT"
                    conflicts.append(row_dict)
        
        if not conflicts:
            return pd.DataFrame({
                "Status": ["✓ No conflicting repeated answers found in non-iterative content"]
            })
        
        return pd.DataFrame(conflicts)
    
    def write_to_excel(self, output_path: str):
        """
        Write all report tabs to an Excel workbook.
        
        Parameters
        ----------
        output_path : str
            Path to write Excel file
        """
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for tab_name, df in self.report_data.items():
                df.to_excel(writer, sheet_name=tab_name, index=False)
    
    @staticmethod
    def generate_complete_report(raw_df: pd.DataFrame,
                                final_df: pd.DataFrame,
                                id_cols: List[str] = None,
                                question_col: str = "question",
                                answer_col: str = "answer",
                                iterative_contents: List[str] = None) -> Dict[str, pd.DataFrame]:
        """
        Generate a complete quality report with all tabs.
        
        Parameters
        ----------
        raw_df : pd.DataFrame
            Raw input dataframe
        final_df : pd.DataFrame
            Final output dataframe
        id_cols : list of str, optional
            ID column names
        question_col : str
            Column name for questions
        answer_col : str
            Column name for answers
        iterative_contents : list of str, optional
            Iterative content names
        
        Returns
        -------
        dict
            Maps tab name -> dataframe
        """
        if id_cols is None:
            id_cols = ["patient_id", "pathway_id"]
        
        if iterative_contents is None:
            iterative_contents = []
        
        report_tabs = {}
        
        # Summary
        stats = {
            "Generation Date": str(datetime.now().isoformat()),
            "Raw Data Rows": len(raw_df),
            "Output Rows": len(final_df),
            "Output Columns": len(final_df.columns),
        }
        
        generator = QualityReportGenerator()
        generator.add_summary_stats(stats)
        report_tabs["summary"] = generator.generate_summary_tab()
        
        # Missing columns
        report_tabs["missing_required_columns"] = generator.generate_missing_columns_tab(
            raw_df,
            [col for col in final_df.columns if col not in raw_df.columns]
        )
        
        # Row coverage
        if all(col in raw_df.columns for col in id_cols):
            report_tabs["row_coverage"] = generator.generate_row_coverage_tab(
                raw_df, final_df, id_cols
            )
        
        # Non-responders
        if all(col in raw_df.columns for col in id_cols):
            report_tabs["non_responder_rows"] = generator.generate_non_responder_rows_tab(
                raw_df, final_df, id_cols
            )
        
        # Duplicate columns
        report_tabs["duplicate_columns"] = generator.generate_duplicate_columns_tab(final_df)
        
        # Normalized duplicates
        if question_col in raw_df.columns:
            report_tabs["normalized_duplicate_questions"] = generator.generate_normalized_duplicates_tab(
                raw_df, question_col
            )
        
        # Non-iterative conflicts
        if all(col in raw_df.columns for col in [question_col, answer_col]) and id_cols:
            report_tabs["non_iterative_repeated_conflicts"] = generator.generate_non_iterative_conflicts_tab(
                raw_df, id_cols, question_col, answer_col, iterative_contents
            )
        
        return report_tabs

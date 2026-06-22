"""
data_dictionary.py

Generates comprehensive data dictionaries that document all variables in the output.
Includes source information, descriptions, and metadata for every column.
"""

import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime


class DataDictionaryEntry:
    """Represents a single variable in the data dictionary."""
    
    def __init__(self, variable_name: str):
        self.variable_name = variable_name
        self.source_file: Optional[str] = None
        self.source_column: Optional[str] = None
        self.content_name: Optional[str] = None
        self.original_question_text: Optional[str] = None
        self.standard_question_text: Optional[str] = None
        self.standard_variable_name: Optional[str] = None
        self.iteration: Optional[int] = None
        self.value_type: str = "text"
        self.description: str = ""
        self.endpoint_group: Optional[str] = None
        self.clinical_phase: Optional[str] = None
        self.is_derived: bool = False
        self.derivation_logic: Optional[str] = None
        self.notes: str = ""
        self.possible_values: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for DataFrame creation."""
        return {
            "variable_name": self.variable_name,
            "source_file": self.source_file or "",
            "source_column": self.source_column or "",
            "content_name": self.content_name or "",
            "original_question_text": self.original_question_text or "",
            "standard_question_text": self.standard_question_text or "",
            "standard_variable_name": self.standard_variable_name or "",
            "iteration": self.iteration or "",
            "value_type": self.value_type,
            "description": self.description,
            "endpoint_group": self.endpoint_group or "",
            "clinical_phase": self.clinical_phase or "",
            "is_derived": self.is_derived,
            "derivation_logic": self.derivation_logic or "",
            "possible_values": self.possible_values or "",
            "notes": self.notes,
        }


class DataDictionaryGenerator:
    """Generates comprehensive data dictionaries."""
    
    # Group columns by clinical phase
    PHASE_KEYWORDS = {
        "Identifier": ["patient_id", "pathway_id", "pathway_name"],
        "Demographics": ["age", "sex", "gender", "birthdate", "height", "weight", "bmi"],
        "Pre-operative": ["admission", "pre_op", "preop", "baseline", "initial"],
        "Intra-operative": ["surgery", "procedure", "operative", "intra_op", "intraop"],
        "Post-operative": ["post_op", "postop", "pod", "postoperative", "discharge"],
        "Follow-up": ["follow_up", "followup", "3month", "6month", "12month"],
        "Clinical Endpoints": ["endpoint", "outcome", "mortality", "los", "length_of_stay"],
        "Adherence": ["adherence", "compliance", "completed", "scheduled"],
        "Quality": ["quality", "satisfaction", "prom"],
    }
    
    def __init__(self):
        self.entries: Dict[str, DataDictionaryEntry] = {}
    
    def add_entry(self, variable_name: str) -> DataDictionaryEntry:
        """Add or get an entry."""
        if variable_name not in self.entries:
            self.entries[variable_name] = DataDictionaryEntry(variable_name)
        return self.entries[variable_name]
    
    def add_from_dataframe(self, df: pd.DataFrame, source_file: str = "input"):
        """
        Automatically add entries for all columns in a dataframe.
        
        Parameters
        ----------
        df : pd.DataFrame
            Dataframe to document
        source_file : str
            Name/role of source file
        """
        for col in df.columns:
            entry = self.add_entry(col)
            entry.source_file = source_file
            entry.source_column = col
            
            # Infer value type from data
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                entry.value_type = "datetime"
            elif pd.api.types.is_numeric_dtype(df[col]):
                entry.value_type = "numeric"
            elif pd.api.types.is_bool_dtype(df[col]):
                entry.value_type = "boolean"
            else:
                entry.value_type = "text"
            
            # Get possible values for categorical columns
            if entry.value_type in ["text", "categorical"]:
                unique_vals = df[col].dropna().unique()
                if len(unique_vals) <= 20:  # Only show if reasonable number
                    entry.possible_values = sorted([str(v) for v in unique_vals])
    
    def assign_clinical_phase(self):
        """
        Automatically assign clinical phases based on column names.
        """
        for var_name, entry in self.entries.items():
            var_lower = var_name.lower()
            
            for phase, keywords in self.PHASE_KEYWORDS.items():
                if any(kw in var_lower for kw in keywords):
                    entry.clinical_phase = phase
                    break
    
    def merge_manual_mappings(self, mapping_df: pd.DataFrame):
        """
        Merge in manual variable mappings.
        
        Parameters
        ----------
        mapping_df : pd.DataFrame
            Should have columns like: source_column, standard_question_text, 
            standard_variable_name, description, endpoint_group, is_iterative, etc.
        """
        for _, row in mapping_df.iterrows():
            source_col = row.get("source_column")
            if source_col and source_col in self.entries:
                entry = self.entries[source_col]
                
                if "standard_question_text" in row and pd.notna(row["standard_question_text"]):
                    entry.standard_question_text = row["standard_question_text"]
                
                if "standard_variable_name" in row and pd.notna(row["standard_variable_name"]):
                    entry.standard_variable_name = row["standard_variable_name"]
                
                if "description" in row and pd.notna(row["description"]):
                    entry.description = row["description"]
                
                if "endpoint_group" in row and pd.notna(row["endpoint_group"]):
                    entry.endpoint_group = row["endpoint_group"]
    
    def to_dataframe(self) -> pd.DataFrame:
        """
        Convert to dataframe for export.
        
        Returns
        -------
        pd.DataFrame
            Data dictionary
        """
        rows = [entry.to_dict() for entry in self.entries.values()]
        df = pd.DataFrame(rows)
        
        # Sort by clinical phase, then by variable name
        phase_order = {phase: i for i, phase in enumerate(self.PHASE_KEYWORDS.keys())}
        df["phase_sort"] = df["clinical_phase"].map(phase_order).fillna(999)
        df = df.sort_values(["phase_sort", "variable_name"]).drop("phase_sort", axis=1)
        
        return df
    
    @staticmethod
    def generate_for_output(output_df: pd.DataFrame, 
                           source_mappings: Optional[Dict[str, str]] = None,
                           manual_mapping_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        Generate a complete data dictionary for an output dataset.
        
        Parameters
        ----------
        output_df : pd.DataFrame
            The final output dataset
        source_mappings : dict, optional
            Maps output column -> source file
        manual_mapping_df : pd.DataFrame, optional
            Manual mappings to merge in
        
        Returns
        -------
        pd.DataFrame
            Complete data dictionary
        """
        generator = DataDictionaryGenerator()
        
        # Add all columns
        generator.add_from_dataframe(output_df, source_file="output")
        
        # Apply source mappings if provided
        if source_mappings:
            for col, source in source_mappings.items():
                if col in generator.entries:
                    generator.entries[col].source_file = source
        
        # Merge manual mappings if provided
        if manual_mapping_df is not None:
            generator.merge_manual_mappings(manual_mapping_df)
        
        # Assign clinical phases
        generator.assign_clinical_phase()
        
        return generator.to_dataframe()


class DataDictionaryAuditor:
    """Audits the data dictionary for completeness."""
    
    @staticmethod
    def audit_entries(dictionary_df: pd.DataFrame) -> List[Dict[str, str]]:
        """
        Audit data dictionary entries for missing documentation.
        
        Parameters
        ----------
        dictionary_df : pd.DataFrame
            Data dictionary
        
        Returns
        -------
        list of dict
            Issues found (variable, issue_type, message)
        """
        issues = []
        
        for _, row in dictionary_df.iterrows():
            var_name = row.get("variable_name", "")
            description = row.get("description", "")
            value_type = row.get("value_type", "")
            
            # Check for missing descriptions (exclude certain internal variables)
            if pd.isna(description) or description == "":
                if not any(prefix in var_name.lower() for prefix in ["id", "date", "count"]):
                    issues.append({
                        "variable": var_name,
                        "issue_type": "missing_description",
                        "message": f"Variable '{var_name}' has no description"
                    })
            
            # Check for unknown value types
            if value_type not in ["text", "numeric", "datetime", "boolean", "categorical", ""]:
                issues.append({
                    "variable": var_name,
                    "issue_type": "unknown_value_type",
                    "message": f"Unknown value_type: {value_type}"
                })
        
        return issues
    
    @staticmethod
    def check_coverage(output_df: pd.DataFrame, dictionary_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Check if all output columns are documented.
        
        Parameters
        ----------
        output_df : pd.DataFrame
            Output dataset
        dictionary_df : pd.DataFrame
            Data dictionary
        
        Returns
        -------
        dict
            Coverage report with statistics
        """
        output_cols = set(output_df.columns)
        documented_cols = set(dictionary_df.get("variable_name", []))
        
        missing = output_cols - documented_cols
        extra = documented_cols - output_cols
        
        return {
            "total_output_columns": len(output_cols),
            "total_documented_columns": len(documented_cols),
            "missing_from_dictionary": sorted(list(missing)),
            "extra_in_dictionary": sorted(list(extra)),
            "coverage_percent": 100 * len(output_cols & documented_cols) / len(output_cols) if output_cols else 0,
        }

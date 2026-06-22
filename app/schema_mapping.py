"""
schema_mapping.py

Provides flexible column mapping from raw input to standardized internal schema.
Allows different hospitals/datasets to use different column names while maintaining
a consistent internal processing pipeline.
"""

import pandas as pd
from typing import Dict, List, Optional, Any


STANDARD_INTERNAL_SCHEMA = {
    # Keys/identifiers
    "patient_id": str,
    "pathway_id": Optional[str],
    "pathway_name": str,
    
    # Content/question/answer
    "content_name": str,
    "question": str,
    "answer": str,
    "text_answer": Optional[str],
    "numeric_answer": Optional[float],
    
    # Dates
    "entry_date": Optional[pd.Timestamp],
    "scheduled_date": Optional[pd.Timestamp],
    
    # Metadata
    "content_status": Optional[str],
    "source_file": str,
    "source_row_id": Optional[int],
    
    # Optional endpoint fields
    "admission_date": Optional[pd.Timestamp],
    "discharge_date": Optional[pd.Timestamp],
    "discharge_destination": Optional[str],
    "mortality_status": Optional[str],
    "mortality_date": Optional[pd.Timestamp],
    "pathway_adherence_pct": Optional[float],
    "scheduled_count": Optional[int],
    "completed_count": Optional[int],
}


class ColumnMapping:
    """Maps raw column names to standard internal names."""
    
    def __init__(self, mapping: Dict[str, str]):
        """
        Initialize with a mapping dictionary.
        
        Parameters
        ----------
        mapping : dict
            Maps standard internal names to raw column names.
            Example: {"patient_id": "Patient ID", "question": "Question"}
        """
        self.mapping = mapping
        self.reverse_mapping = {v: k for k, v in mapping.items() if v is not None}
    
    def get_raw_column(self, standard_name: str) -> Optional[str]:
        """Get the raw column name for a standard internal name."""
        return self.mapping.get(standard_name)
    
    def get_standard_name(self, raw_column: str) -> Optional[str]:
        """Get the standard internal name for a raw column."""
        return self.reverse_mapping.get(raw_column)
    
    def apply_to_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply the mapping to a dataframe, renaming columns to standard names.
        
        Parameters
        ----------
        df : pd.DataFrame
            Input dataframe with raw column names
        
        Returns
        -------
        pd.DataFrame
            Dataframe with standard internal column names
        """
        rename_dict = {}
        for standard_name, raw_name in self.mapping.items():
            if raw_name is not None and raw_name in df.columns:
                rename_dict[raw_name] = standard_name
        
        df = df.rename(columns=rename_dict)
        return df
    
    def validate_required_columns(self, df: pd.DataFrame, required: List[str]) -> List[str]:
        """
        Check if required columns are available in dataframe.
        
        Parameters
        ----------
        df : pd.DataFrame
            Input dataframe
        required : list of str
            Required standard internal column names
        
        Returns
        -------
        list of str
            List of missing standard column names
        """
        available_standard = set()
        for col in df.columns:
            standard_name = self.get_standard_name(col)
            if standard_name:
                available_standard.add(standard_name)
        
        return [r for r in required if r not in available_standard]


class MappingBuilder:
    """Helper to build mappings with defaults and suggestions."""
    
    @staticmethod
    def auto_detect_mapping(df: pd.DataFrame) -> Dict[str, str]:
        """
        Auto-detect likely mappings based on column name patterns.
        
        Parameters
        ----------
        df : pd.DataFrame
            Input dataframe
        
        Returns
        -------
        dict
            Auto-detected mapping (standard -> raw column names)
        """
        mapping = {}
        columns_lower = {col.lower(): col for col in df.columns}
        
        # Try to match common patterns
        patterns = {
            "patient_id": ["patient id", "patientid", "patient_id", "pid", "patienten-id"],
            "pathway_name": ["pathway name", "pathway", "pathway_name", "care program", "care_program"],
            "pathway_id": ["pathway id", "pathwayid", "pathway_id"],
            "content_name": ["content name", "content_name", "module name", "module_name", "form name"],
            "question": ["question", "item", "item_text", "item name", "variable"],
            "answer": ["answer", "response", "response_value", "value", "result"],
            "text_answer": ["text answer", "text_answer", "answer_text"],
            "numeric_answer": ["numeric answer", "numeric_answer", "answer_value", "value"],
            "entry_date": ["entry date", "entry_date", "response_date", "completion_date", "timestamp"],
            "scheduled_date": ["scheduled date", "scheduled_date", "appointment_date"],
            "content_status": ["content status", "content_status", "status", "completion_status"],
        }
        
        for standard_name, patterns_list in patterns.items():
            for pattern in patterns_list:
                if pattern in columns_lower:
                    mapping[standard_name] = columns_lower[pattern]
                    break
        
        return mapping
    
    @staticmethod
    def from_yaml_dict(config: Dict[str, Any]) -> Dict[str, ColumnMapping]:
        """
        Build mappings from a YAML-style configuration.
        
        Parameters
        ----------
        config : dict
            Configuration with file roles as keys, each containing a mapping dict
            Example:
            {
                "answers": {
                    "patient_id": "Patient ID",
                    "question": "Question",
                    "answer": "Answer"
                }
            }
        
        Returns
        -------
        dict
            Maps file role to ColumnMapping object
        """
        result = {}
        for role, mapping_dict in config.items():
            result[role] = ColumnMapping(mapping_dict)
        return result


class FileRole:
    """Enumeration of file roles in the transformation pipeline."""
    
    DEMOGRAPHICS = "demographics"
    SCHEDULED_CONTENT = "scheduled_content"
    ANSWERS = "answers"
    ENDPOINTS = "endpoints"
    ADHERENCE = "adherence"
    VARIABLE_MAPPING = "variable_mapping"
    
    ALL = [DEMOGRAPHICS, SCHEDULED_CONTENT, ANSWERS, ENDPOINTS, ADHERENCE, VARIABLE_MAPPING]
    
    DESCRIPTIONS = {
        DEMOGRAPHICS: "Patient demographics (age, sex, etc.)",
        SCHEDULED_CONTENT: "Scheduled pathway content/questionnaires",
        ANSWERS: "Patient responses to questionnaires",
        ENDPOINTS: "Clinical endpoints (admission, discharge, mortality, etc.)",
        ADHERENCE: "Pathway adherence information",
        VARIABLE_MAPPING: "Manual mapping of questions to standard variables",
    }


class FileRoleMapping:
    """Maps uploaded files to their roles and stores their column mappings."""
    
    def __init__(self):
        self.files: Dict[str, Dict[str, Any]] = {}
    
    def add_file(self, file_name: str, role: str, df: pd.DataFrame, 
                 column_mapping: Optional[ColumnMapping] = None):
        """
        Add a file with its role and detected/specified column mapping.
        
        Parameters
        ----------
        file_name : str
            Name of the file
        role : str
            Role from FileRole class
        df : pd.DataFrame
            The dataframe
        column_mapping : ColumnMapping, optional
            The column mapping; if None, will auto-detect
        """
        if column_mapping is None:
            auto_mapping = MappingBuilder.auto_detect_mapping(df)
            column_mapping = ColumnMapping(auto_mapping)
        
        self.files[file_name] = {
            "role": role,
            "dataframe": df,
            "mapping": column_mapping,
        }
    
    def get_files_by_role(self, role: str) -> Dict[str, Dict[str, Any]]:
        """Get all files with a specific role."""
        return {name: info for name, info in self.files.items() if info["role"] == role}
    
    def get_mapping_for_role(self, role: str) -> Optional[ColumnMapping]:
        """Get column mapping for a specific role (returns first if multiple)."""
        files_with_role = self.get_files_by_role(role)
        if files_with_role:
            first_file = next(iter(files_with_role.values()))
            return first_file["mapping"]
        return None

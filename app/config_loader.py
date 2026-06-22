"""
config_loader.py

Loads transformation configuration from YAML/CSV files.
Supports different hospital/project configurations.
"""

import yaml
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional
from schema_mapping import ColumnMapping, FileRole, MappingBuilder


class TransformationConfig:
    """Represents a transformation configuration."""
    
    def __init__(self, name: str):
        self.name = name
        self.description: str = ""
        
        # Column mappings by file role
        self.column_mappings: Dict[str, ColumnMapping] = {}
        
        # Iterative content names
        self.iterative_contents: list = []
        
        # Non-iterative repeat policy
        self.non_iterative_policy: str = "latest_non_blank"  # or "first_non_blank", "preserve_all"
        self.flag_non_iterative_conflicts: bool = True
        
        # Endpoint configuration
        self.enabled_endpoints: list = []
        self.custom_endpoint_aliases: Dict[str, list] = {}
        
        # Output sorting
        self.column_groups_order: list = []
    
    @staticmethod
    def from_yaml(yaml_path: str) -> "TransformationConfig":
        """
        Load configuration from a YAML file.
        
        Parameters
        ----------
        yaml_path : str
            Path to YAML configuration file
        
        Returns
        -------
        TransformationConfig
        """
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        
        config = TransformationConfig(data.get("name", "unnamed"))
        config.description = data.get("description", "")
        
        # Load column mappings
        if "column_mappings" in data:
            for role, mappings in data["column_mappings"].items():
                if isinstance(mappings, dict):
                    config.column_mappings[role] = ColumnMapping(mappings)
        
        # Load iterative contents
        config.iterative_contents = data.get("iterative_contents", [])
        
        # Load non-iterative policy
        if "non_iterative_policy" in data:
            config.non_iterative_policy = data["non_iterative_policy"]["policy"]
            config.flag_non_iterative_conflicts = data["non_iterative_policy"].get(
                "flag_if_different", True
            )
        
        # Load endpoint config
        config.enabled_endpoints = data.get("enabled_endpoints", [])
        config.custom_endpoint_aliases = data.get("custom_endpoint_aliases", {})
        
        # Load output sorting
        config.column_groups_order = data.get("column_groups_order", [])
        
        return config
    
    @staticmethod
    def from_dict(name: str, config_dict: Dict[str, Any]) -> "TransformationConfig":
        """
        Load configuration from a dictionary.
        
        Parameters
        ----------
        name : str
            Name for the configuration
        config_dict : dict
            Configuration dictionary
        
        Returns
        -------
        TransformationConfig
        """
        config = TransformationConfig(name)
        
        if "description" in config_dict:
            config.description = config_dict["description"]
        
        if "column_mappings" in config_dict:
            for role, mappings in config_dict["column_mappings"].items():
                if isinstance(mappings, dict):
                    config.column_mappings[role] = ColumnMapping(mappings)
        
        config.iterative_contents = config_dict.get("iterative_contents", [])
        
        if "non_iterative_policy" in config_dict:
            policy_config = config_dict["non_iterative_policy"]
            if isinstance(policy_config, dict):
                config.non_iterative_policy = policy_config.get("policy", "latest_non_blank")
                config.flag_non_iterative_conflicts = policy_config.get("flag_if_different", True)
            else:
                config.non_iterative_policy = policy_config
        
        config.enabled_endpoints = config_dict.get("enabled_endpoints", [])
        config.custom_endpoint_aliases = config_dict.get("custom_endpoint_aliases", {})
        config.column_groups_order = config_dict.get("column_groups_order", [])
        
        return config
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "column_mappings": {
                role: mapping.mapping for role, mapping in self.column_mappings.items()
            },
            "iterative_contents": self.iterative_contents,
            "non_iterative_policy": {
                "policy": self.non_iterative_policy,
                "flag_if_different": self.flag_non_iterative_conflicts,
            },
            "enabled_endpoints": self.enabled_endpoints,
            "custom_endpoint_aliases": self.custom_endpoint_aliases,
            "column_groups_order": self.column_groups_order,
        }
    
    def get_mapping_for_role(self, role: str) -> Optional[ColumnMapping]:
        """Get column mapping for a file role."""
        return self.column_mappings.get(role)


class ConfigLibrary:
    """Library of pre-built configurations."""
    
    # Ulm ERP configuration (Medtronic Ulm Hospital)
    ULM_ERP_CONFIG = {
        "name": "Ulm ERP",
        "description": "Medtronic Ulm Hospital Enhanced Recovery Program",
        "column_mappings": {
            FileRole.DEMOGRAPHICS: {
                "patient_id": "Patient ID",
                "age": "Patient Age",
                "sex": "Patient Gender",
            },
            FileRole.SCHEDULED_CONTENT: {
                "patient_id": "Patient ID",
                "pathway_name": "Pathway Name",
                "content_name": "Content Name",
                "scheduled_date": "Scheduled date",
                "entry_date": "Entry Date",
                "content_status": "Content Status",
            },
            FileRole.ANSWERS: {
                "patient_id": "Patient ID",
                "pathway_name": "Pathway Name",
                "content_name": "Content Name",
                "question": "Question",
                "answer": "Answer Text",
                "numeric_answer": "Answer Value",
                "entry_date": "Entry Date",
                "scheduled_date": "Scheduled date",
            },
        },
        "iterative_contents": [
            "BMI",
            "Allgemeine Gesundheit",
            "Schmerztagebuch",
            "Tagesbericht zuhause",
        ],
        "non_iterative_policy": {
            "policy": "latest_non_blank",
            "flag_if_different": True,
        },
        "enabled_endpoints": [
            "length_of_stay_days",
            "discharge_destination",
            "postoperative_mortality",
            "pathway_adherence_pct",
            "urinary_catheter_removed_by_pod1",
            "mobility_minutes_out_of_bed_pod1",
        ],
    }
    
    # Generic template
    GENERIC_CONFIG = {
        "name": "Generic Template",
        "description": "Generic configuration for new hospitals/datasets",
        "column_mappings": {
            FileRole.DEMOGRAPHICS: {
                "patient_id": "patient_id",
            },
            FileRole.SCHEDULED_CONTENT: {
                "patient_id": "patient_id",
                "pathway_name": "pathway_name",
                "content_name": "content_name",
            },
            FileRole.ANSWERS: {
                "patient_id": "patient_id",
                "pathway_name": "pathway_name",
                "content_name": "content_name",
                "question": "question",
                "answer": "answer",
            },
        },
        "iterative_contents": [],
        "non_iterative_policy": {
            "policy": "latest_non_blank",
            "flag_if_different": True,
        },
        "enabled_endpoints": [],
    }
    
    @classmethod
    def get_config(cls, name: str) -> Optional[TransformationConfig]:
        """
        Get a built-in configuration by name.
        
        Parameters
        ----------
        name : str
            Configuration name ("ulm_erp", "generic", etc.)
        
        Returns
        -------
        TransformationConfig or None
        """
        configs = {
            "ulm_erp": cls.ULM_ERP_CONFIG,
            "generic": cls.GENERIC_CONFIG,
        }
        
        if name not in configs:
            return None
        
        return TransformationConfig.from_dict(name, configs[name])
    
    @classmethod
    def list_available(cls) -> list:
        """List available built-in configurations."""
        return ["ulm_erp", "generic"]


def load_variable_mapping_file(file_path: str) -> pd.DataFrame:
    """
    Load a variable mapping CSV file.
    
    Expected columns:
    - source_table (e.g., "answers")
    - content_name (e.g., "BMI")
    - raw_question_contains (substring to match)
    - standard_question_text (the normalized question)
    - standard_variable_name (output column name)
    - description (what this variable represents)
    - endpoint_group (e.g., "BMI", "Endpoints", "Mobility")
    - is_iterative (true/false)
    
    Parameters
    ----------
    file_path : str
        Path to CSV file
    
    Returns
    -------
    pd.DataFrame
        Variable mapping dataframe
    """
    df = pd.read_csv(file_path, dtype=str)
    
    # Normalize column names
    df.columns = [col.lower().replace(" ", "_") for col in df.columns]
    
    return df


def apply_variable_mapping(answers_df: pd.DataFrame,
                          mapping_df: pd.DataFrame,
                          question_col: str = "question") -> pd.DataFrame:
    """
    Apply variable mapping to standardize question/variable names.
    
    Parameters
    ----------
    answers_df : pd.DataFrame
        Answers dataframe
    mapping_df : pd.DataFrame
        Variable mapping dataframe (from load_variable_mapping_file)
    question_col : str
        Column name for questions in answers_df
    
    Returns
    -------
    pd.DataFrame
        Dataframe with additional mapping columns
    """
    answers_df = answers_df.copy()
    
    # Add standard variable name column
    if "standard_variable_name" not in answers_df.columns:
        answers_df["standard_variable_name"] = None
        answers_df["standard_question_text"] = answers_df.get(question_col, None)
    
    # Apply mappings
    for _, mapping_row in mapping_df.iterrows():
        raw_question_contains = mapping_row.get("raw_question_contains", "")
        standard_var = mapping_row.get("standard_variable_name", "")
        standard_question = mapping_row.get("standard_question_text", "")
        
        if not raw_question_contains or not standard_var:
            continue
        
        # Find matching questions
        if question_col in answers_df.columns:
            mask = answers_df[question_col].str.contains(
                raw_question_contains, case=False, na=False
            )
            
            answers_df.loc[mask, "standard_variable_name"] = standard_var
            if standard_question:
                answers_df.loc[mask, "standard_question_text"] = standard_question
    
    return answers_df

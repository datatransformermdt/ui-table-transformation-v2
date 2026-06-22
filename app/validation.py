"""
validation.py

Validates input files and configurations before transformation.
Produces clear validation reports with errors, warnings, and info messages.
"""

import pandas as pd
from typing import Dict, List, Tuple, Optional
from enum import Enum
from schema_mapping import ColumnMapping, FileRole


class ValidationLevel(Enum):
    """Severity levels for validation messages."""
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ValidationMessage:
    """A single validation message."""
    
    def __init__(self, level: ValidationLevel, message: str, field: Optional[str] = None):
        self.level = level
        self.message = message
        self.field = field
    
    def __repr__(self):
        field_str = f" [{self.field}]" if self.field else ""
        return f"{self.level.value}{field_str}: {self.message}"
    
    def to_dict(self):
        return {
            "level": self.level.value,
            "message": self.message,
            "field": self.field,
        }


class ValidationReport:
    """Aggregates validation messages."""
    
    def __init__(self):
        self.messages: List[ValidationMessage] = []
    
    def add(self, level: ValidationLevel, message: str, field: Optional[str] = None):
        """Add a message to the report."""
        self.messages.append(ValidationMessage(level, message, field))
    
    def error(self, message: str, field: Optional[str] = None):
        """Add an error message."""
        self.add(ValidationLevel.ERROR, message, field)
    
    def warning(self, message: str, field: Optional[str] = None):
        """Add a warning message."""
        self.add(ValidationLevel.WARNING, message, field)
    
    def info(self, message: str, field: Optional[str] = None):
        """Add an info message."""
        self.add(ValidationLevel.INFO, message, field)
    
    def has_errors(self) -> bool:
        """Check if report contains any errors."""
        return any(m.level == ValidationLevel.ERROR for m in self.messages)
    
    def get_messages_by_level(self, level: ValidationLevel) -> List[ValidationMessage]:
        """Get all messages at a specific level."""
        return [m for m in self.messages if m.level == level]
    
    def get_errors(self) -> List[ValidationMessage]:
        return self.get_messages_by_level(ValidationLevel.ERROR)
    
    def get_warnings(self) -> List[ValidationMessage]:
        return self.get_messages_by_level(ValidationLevel.WARNING)
    
    def get_infos(self) -> List[ValidationMessage]:
        return self.get_messages_by_level(ValidationLevel.INFO)
    
    def to_dataframe(self) -> pd.DataFrame:
        """Convert report to a dataframe."""
        data = [m.to_dict() for m in self.messages]
        if not data:
            return pd.DataFrame(columns=["level", "message", "field"])
        return pd.DataFrame(data)
    
    def __repr__(self):
        if not self.messages:
            return "ValidationReport (no messages)"
        
        errors = self.get_errors()
        warnings = self.get_warnings()
        infos = self.get_infos()
        
        lines = [
            f"ValidationReport ({len(errors)} errors, {len(warnings)} warnings, {len(infos)} infos):",
        ]
        
        if errors:
            lines.append("Errors:")
            for msg in errors:
                lines.append(f"  {msg}")
        
        if warnings:
            lines.append("Warnings:")
            for msg in warnings:
                lines.append(f"  {msg}")
        
        if infos:
            lines.append("Infos:")
            for msg in infos:
                lines.append(f"  {msg}")
        
        return "\n".join(lines)


class SchemaValidator:
    """Validates whether files have required columns for their roles."""
    
    # Define required columns by file role
    REQUIRED_BY_ROLE = {
        FileRole.DEMOGRAPHICS: ["patient_id"],
        FileRole.SCHEDULED_CONTENT: ["patient_id", "pathway_name", "content_name"],
        FileRole.ANSWERS: ["patient_id", "pathway_name", "content_name", "question", "answer"],
        FileRole.ENDPOINTS: ["patient_id"],
        FileRole.ADHERENCE: ["patient_id", "pathway_name"],
        FileRole.VARIABLE_MAPPING: ["source_column", "standard_question_text", "standard_variable_name"],
    }
    
    # Define optional but recommended columns by file role
    RECOMMENDED_BY_ROLE = {
        FileRole.DEMOGRAPHICS: ["age", "sex"],
        FileRole.SCHEDULED_CONTENT: ["entry_date", "scheduled_date"],
        FileRole.ANSWERS: ["entry_date", "scheduled_date"],
        FileRole.ENDPOINTS: ["admission_date", "discharge_date", "discharge_destination"],
    }
    
    @staticmethod
    def validate_file_for_role(df: pd.DataFrame, role: str, mapping: ColumnMapping,
                               file_name: str) -> ValidationReport:
        """
        Validate a file for a specific role.
        
        Parameters
        ----------
        df : pd.DataFrame
            The dataframe to validate
        role : str
            The FileRole
        mapping : ColumnMapping
            The column mapping for this file
        file_name : str
            Name of the file (for reporting)
        
        Returns
        -------
        ValidationReport
            Report with errors, warnings, and info messages
        """
        report = ValidationReport()
        
        # Check for required columns
        if role in SchemaValidator.REQUIRED_BY_ROLE:
            required = SchemaValidator.REQUIRED_BY_ROLE[role]
            
            # Check raw columns
            missing_raw = []
            for standard_col in required:
                raw_col = mapping.get_raw_column(standard_col)
                if raw_col is None or raw_col not in df.columns:
                    missing_raw.append(standard_col)
            
            if missing_raw:
                report.error(
                    f"[{file_name}] Missing required columns: {', '.join(missing_raw)}",
                    field=role
                )
        
        # Check for recommended columns
        if role in SchemaValidator.RECOMMENDED_BY_ROLE:
            recommended = SchemaValidator.RECOMMENDED_BY_ROLE[role]
            missing_recommended = []
            
            for standard_col in recommended:
                raw_col = mapping.get_raw_column(standard_col)
                if raw_col is None or raw_col not in df.columns:
                    missing_recommended.append(standard_col)
            
            if missing_recommended:
                report.warning(
                    f"[{file_name}] Missing recommended columns: {', '.join(missing_recommended)}",
                    field=role
                )
        
        # Check for empty dataframe
        if df.empty:
            report.warning(f"[{file_name}] File is empty", field=role)
        
        # Check for rows with all NaN in key columns
        if not df.empty and role in SchemaValidator.REQUIRED_BY_ROLE:
            required = SchemaValidator.REQUIRED_BY_ROLE[role]
            key_cols = []
            for standard_col in required:
                raw_col = mapping.get_raw_column(standard_col)
                if raw_col and raw_col in df.columns:
                    key_cols.append(raw_col)
            
            if key_cols:
                null_rows = df[key_cols].isna().all(axis=1).sum()
                if null_rows > 0:
                    report.warning(
                        f"[{file_name}] {null_rows} rows have all NaN in key columns",
                        field=role
                    )
        
        return report


class TransformationValidator:
    """Validates the overall transformation setup."""
    
    @staticmethod
    def validate_transformation_setup(file_role_mapping: Dict[str, Tuple[str, pd.DataFrame, ColumnMapping]]) -> ValidationReport:
        """
        Validate the overall transformation setup.
        
        Parameters
        ----------
        file_role_mapping : dict
            Maps file name to (role, dataframe, mapping)
        
        Returns
        -------
        ValidationReport
        """
        report = ValidationReport()
        
        # Check that we have at least the essential files
        roles_present = {role for _, (role, _, _) in file_role_mapping.items()}
        
        if FileRole.ANSWERS not in roles_present:
            report.error("No answers file provided. This is required for transformation.")
        
        if FileRole.SCHEDULED_CONTENT not in roles_present:
            report.warning("No scheduled content file provided. Row coverage validation will be limited.")
        
        # Validate each file
        for file_name, (role, df, mapping) in file_role_mapping.items():
            file_report = SchemaValidator.validate_file_for_role(df, role, mapping, file_name)
            report.messages.extend(file_report.messages)
        
        # Check for consistent patient IDs across files (if multiple files)
        if len(file_role_mapping) > 1:
            patient_ids_by_file = {}
            for file_name, (role, df, mapping) in file_role_mapping.items():
                patient_col = mapping.get_raw_column("patient_id")
                if patient_col and patient_col in df.columns:
                    patient_ids_by_file[file_name] = set(df[patient_col].dropna().unique())
            
            if len(patient_ids_by_file) > 1:
                all_patients = set()
                for pids in patient_ids_by_file.values():
                    all_patients.update(pids)
                
                for file_name, pids in patient_ids_by_file.items():
                    missing = all_patients - pids
                    if missing:
                        report.info(
                            f"[{file_name}] Missing {len(missing)} patient(s) that appear in other files",
                            field="patient_id_consistency"
                        )
        
        return report


def generate_validation_summary(report: ValidationReport) -> str:
    """Generate a human-readable summary of validation results."""
    lines = []
    
    errors = report.get_errors()
    warnings = report.get_warnings()
    infos = report.get_infos()
    
    lines.append(f"Validation Summary: {len(errors)} errors, {len(warnings)} warnings, {len(infos)} infos")
    lines.append("=" * 60)
    
    if errors:
        lines.append("\n🔴 ERRORS (transformation cannot proceed):")
        for msg in errors:
            lines.append(f"  • {msg.message}")
    
    if warnings:
        lines.append("\n🟡 WARNINGS (transformation can run with limitations):")
        for msg in warnings:
            lines.append(f"  • {msg.message}")
    
    if infos:
        lines.append("\n🔵 INFO:")
        for msg in infos:
            lines.append(f"  • {msg.message}")
    
    if not errors:
        lines.append("\n✅ Ready to proceed with transformation!")
    
    return "\n".join(lines)

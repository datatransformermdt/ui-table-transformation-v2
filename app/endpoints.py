"""
endpoints.py

Support for clinical endpoint detection, derivation, and reporting.
Helps identify which endpoints are available in the data and which can be derived.
"""

import pandas as pd
from typing import Dict, List, Optional, Tuple
from enum import Enum


class EndpointStatus(Enum):
    """Status of an endpoint in the dataset."""
    FOUND = "Found directly"
    DERIVABLE = "Derivable"
    MISSING = "Missing / requires additional source data"


class ClinicalEndpoint:
    """Represents a single clinical endpoint."""
    
    def __init__(self, name: str, aliases: List[str], description: str,
                 derivation_logic: Optional[str] = None):
        """
        Initialize an endpoint.
        
        Parameters
        ----------
        name : str
            Standard endpoint name (e.g., "length_of_stay_days")
        aliases : list of str
            Alternative names/column names for this endpoint
        description : str
            Human-readable description
        derivation_logic : str, optional
            Description of how to derive this endpoint if direct column not found
        """
        self.name = name
        self.aliases = aliases
        self.description = description
        self.derivation_logic = derivation_logic
        self.status = None
        self.source_field = None
        self.matched_alias = None
        self.action_needed = None
    
    def to_dict(self):
        return {
            "endpoint": self.name,
            "status": self.status.value if self.status else None,
            "description": self.description,
            "source_field": self.source_field,
            "matched_alias": self.matched_alias,
            "derivation_logic": self.derivation_logic,
            "action_needed": self.action_needed,
        }


class EndpointRegistry:
    """Registry of clinical endpoints requested by doctors."""
    
    STANDARD_ENDPOINTS = {
        "length_of_stay_days": ClinicalEndpoint(
            name="length_of_stay_days",
            aliases=[
                "length of stay", "los", "aufenthaltsdauer", "verweildauer",
                "hospital_stay_days", "admission_to_discharge_days"
            ],
            description="Length of hospital stay in days",
            derivation_logic="discharge_date - admission_date"
        ),
        "discharge_destination": ClinicalEndpoint(
            name="discharge_destination",
            aliases=[
                "discharge destination", "entlassungsziel", "entlassort",
                "nach hause", "reha", "pflege", "discharge location"
            ],
            description="Where patient was discharged to",
        ),
        "postoperative_mortality": ClinicalEndpoint(
            name="postoperative_mortality",
            aliases=[
                "mortality", "death", "verstorben", "tod", "sterblichkeit",
                "mortality_status", "died", "deceased", "postop_mortality"
            ],
            description="Whether patient died during hospital stay or shortly after",
        ),
        "pathway_adherence_pct": ClinicalEndpoint(
            name="pathway_adherence_pct",
            aliases=[
                "adherence", "compliance", "completion", "completed",
                "pathway_adherence", "adherence_percentage", "adherence_rate"
            ],
            description="Percentage of pathway content completed",
            derivation_logic="completed_content_count / scheduled_content_count * 100"
        ),
        "urinary_catheter_removed_by_pod1": ClinicalEndpoint(
            name="urinary_catheter_removed_by_pod1",
            aliases=[
                "katheter", "harnableitung", "1. postoperativen tag",
                "pod1", "foley removal", "catheter removed"
            ],
            description="Whether urinary catheter was removed by postoperative day 1",
        ),
        "mobility_minutes_out_of_bed_pod1": ClinicalEndpoint(
            name="mobility_minutes_out_of_bed_pod1",
            aliases=[
                "mobilisation", "außerhalb des bettes", "ausserhalb des bettes",
                "minuten", "outside bed", "mobility minutes", "out of bed"
            ],
            description="Minutes spent outside bed on postoperative day 1",
        ),
    }
    
    def __init__(self):
        self.endpoints: Dict[str, ClinicalEndpoint] = {}
        for name, endpoint in self.STANDARD_ENDPOINTS.items():
            self.endpoints[name] = ClinicalEndpoint(
                endpoint.name, endpoint.aliases, endpoint.description,
                endpoint.derivation_logic
            )
    
    def register_custom_endpoint(self, name: str, aliases: List[str], 
                                description: str, derivation_logic: Optional[str] = None):
        """Register a custom endpoint."""
        self.endpoints[name] = ClinicalEndpoint(name, aliases, description, derivation_logic)
    
    def search_in_columns(self, columns: List[str]) -> Dict[str, ClinicalEndpoint]:
        """
        Search for endpoints in a list of column names.
        
        Parameters
        ----------
        columns : list of str
            Column names to search
        
        Returns
        -------
        dict
            Maps endpoint name -> endpoint with matched column
        """
        results = {}
        columns_lower = {col.lower(): col for col in columns}
        
        for endpoint in self.endpoints.values():
            for alias in endpoint.aliases:
                if alias.lower() in columns_lower:
                    endpoint.status = EndpointStatus.FOUND
                    endpoint.source_field = columns_lower[alias.lower()]
                    endpoint.matched_alias = alias
                    results[endpoint.name] = endpoint
                    break
        
        return results
    
    def search_in_questions(self, df: pd.DataFrame, question_col: str = "question",
                           answer_col: str = "answer") -> Dict[str, ClinicalEndpoint]:
        """
        Search for endpoints in question text.
        
        Parameters
        ----------
        df : pd.DataFrame
            Dataframe with questions and answers
        question_col : str
            Column name for questions
        answer_col : str
            Column name for answers
        
        Returns
        -------
        dict
            Maps endpoint name -> endpoint with matched question
        """
        results = {}
        
        if question_col not in df.columns or answer_col not in df.columns:
            return results
        
        questions = df[question_col].dropna().unique()
        questions_lower = [q.lower() for q in questions]
        
        for endpoint in self.endpoints.values():
            for alias in endpoint.aliases:
                for i, q_lower in enumerate(questions_lower):
                    if alias.lower() in q_lower:
                        endpoint.status = EndpointStatus.FOUND
                        endpoint.source_field = f"Question: {questions[i]}"
                        endpoint.matched_alias = alias
                        results[endpoint.name] = endpoint
                        break
                if endpoint.status:
                    break
        
        return results
    
    def get_derivable_endpoints(self, df: pd.DataFrame) -> Dict[str, ClinicalEndpoint]:
        """
        Identify which endpoints can be derived from available data.
        
        Parameters
        ----------
        df : pd.DataFrame
            The transformed dataframe
        
        Returns
        -------
        dict
            Maps endpoint name -> endpoint marked as DERIVABLE
        """
        results = {}
        columns = [col.lower() for col in df.columns]
        
        # Length of stay: needs admission and discharge dates
        if "admission_date" in columns and "discharge_date" in columns:
            ep = self.endpoints["length_of_stay_days"]
            ep.status = EndpointStatus.DERIVABLE
            ep.source_field = "admission_date, discharge_date"
            ep.action_needed = "Calculate: discharge_date - admission_date"
            results["length_of_stay_days"] = ep
        
        # Pathway adherence: needs scheduled and completed counts
        if "scheduled_count" in columns and "completed_count" in columns:
            ep = self.endpoints["pathway_adherence_pct"]
            ep.status = EndpointStatus.DERIVABLE
            ep.source_field = "scheduled_count, completed_count"
            ep.action_needed = "Calculate: completed_count / scheduled_count * 100"
            results["pathway_adherence_pct"] = ep
        
        return results
    
    def get_all_endpoint_statuses(self, df: pd.DataFrame, 
                                 question_col: Optional[str] = None,
                                 answer_col: Optional[str] = None) -> Dict[str, ClinicalEndpoint]:
        """
        Get status of all endpoints in the dataset.
        
        Parameters
        ----------
        df : pd.DataFrame
            The dataframe (can be raw data or transformed)
        question_col : str, optional
            Column name for questions (for searching raw data)
        answer_col : str, optional
            Column name for answers (for searching raw data)
        
        Returns
        -------
        dict
            Maps endpoint name -> endpoint with status
        """
        # Reset all statuses
        for ep in self.endpoints.values():
            ep.status = EndpointStatus.MISSING
            ep.source_field = None
            ep.matched_alias = None
        
        results = {}
        
        # Search in columns
        found = self.search_in_columns(df.columns.tolist())
        results.update(found)
        
        # Search in questions (if question column provided)
        if question_col and question_col in df.columns:
            found_in_q = self.search_in_questions(df, question_col, answer_col or "answer")
            results.update(found_in_q)
        
        # Check derivable
        derivable = self.get_derivable_endpoints(df)
        for name, ep in derivable.items():
            if name not in results:
                results[name] = ep
        
        # Add endpoints not found
        for name, ep in self.endpoints.items():
            if name not in results:
                ep.status = EndpointStatus.MISSING
                results[name] = ep
        
        return results
    
    def get_endpoint_availability_report(self, df: pd.DataFrame,
                                        question_col: Optional[str] = None) -> pd.DataFrame:
        """
        Generate an endpoint availability report.
        
        Parameters
        ----------
        df : pd.DataFrame
            The dataframe
        question_col : str, optional
            Question column name for searching
        
        Returns
        -------
        pd.DataFrame
            Report with columns: endpoint, status, source_field, matched_alias, derivation_logic, action_needed
        """
        statuses = self.get_all_endpoint_statuses(df, question_col=question_col)
        
        rows = []
        for name, endpoint in statuses.items():
            rows.append({
                "endpoint": endpoint.name,
                "status": endpoint.status.value if endpoint.status else "Unknown",
                "description": endpoint.description,
                "source_field": endpoint.source_field or "",
                "matched_alias": endpoint.matched_alias or "",
                "derivation_logic": endpoint.derivation_logic or "",
                "action_needed": endpoint.action_needed or "",
            })
        
        return pd.DataFrame(rows)


class EndpointDeriver:
    """Derives endpoint values from available source data."""
    
    @staticmethod
    def derive_length_of_stay(df: pd.DataFrame, 
                             admission_col: str = "admission_date",
                             discharge_col: str = "discharge_date") -> pd.Series:
        """
        Derive length of stay in days.
        
        Parameters
        ----------
        df : pd.DataFrame
            Dataframe with admission and discharge dates
        admission_col : str
            Column name for admission date
        discharge_col : str
            Column name for discharge date
        
        Returns
        -------
        pd.Series
            Length of stay in days
        """
        if admission_col not in df.columns or discharge_col not in df.columns:
            return pd.Series([None] * len(df), index=df.index)
        
        admission = pd.to_datetime(df[admission_col], errors="coerce")
        discharge = pd.to_datetime(df[discharge_col], errors="coerce")
        
        los = (discharge - admission).dt.days
        
        # Only keep valid values (positive or zero)
        los = los.where(los >= 0, None)
        
        return los
    
    @staticmethod
    def derive_pathway_adherence(df: pd.DataFrame,
                               scheduled_col: str = "scheduled_count",
                               completed_col: str = "completed_count") -> pd.Series:
        """
        Derive pathway adherence percentage.
        
        Parameters
        ----------
        df : pd.DataFrame
            Dataframe with scheduled and completed counts
        scheduled_col : str
            Column name for scheduled count
        completed_col : str
            Column name for completed count
        
        Returns
        -------
        pd.Series
            Adherence percentage (0-100)
        """
        if scheduled_col not in df.columns or completed_col not in df.columns:
            return pd.Series([None] * len(df), index=df.index)
        
        scheduled = pd.to_numeric(df[scheduled_col], errors="coerce")
        completed = pd.to_numeric(df[completed_col], errors="coerce")
        
        # Avoid division by zero
        adherence = (completed / scheduled * 100).where(scheduled > 0, None)
        
        # Clip to 0-100
        adherence = adherence.clip(lower=0, upper=100)
        
        return adherence
    
    @staticmethod
    def apply_all_derivations(df: pd.DataFrame) -> pd.DataFrame:
        """
        Apply all available endpoint derivations.
        
        Parameters
        ----------
        df : pd.DataFrame
            Input dataframe
        
        Returns
        -------
        pd.DataFrame
            Dataframe with derived endpoints
        """
        df = df.copy()
        
        # Derive length of stay
        if "admission_date" in df.columns and "discharge_date" in df.columns:
            if "length_of_stay_days" not in df.columns:
                df["length_of_stay_days"] = EndpointDeriver.derive_length_of_stay(df)
        
        # Derive pathway adherence
        if "scheduled_count" in df.columns and "completed_count" in df.columns:
            if "pathway_adherence_pct" not in df.columns:
                df["pathway_adherence_pct"] = EndpointDeriver.derive_pathway_adherence(df)
        
        return df

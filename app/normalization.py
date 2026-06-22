"""
normalization.py

Normalizes question text, column names, and other text values to enable
reliable grouping and deduplication.
"""

import re
import unicodedata
import pandas as pd
from typing import Optional


def normalize_question_text(text: str) -> str:
    """
    Normalize question text for reliable grouping.
    
    Handles:
    - Unicode normalization (NFKC)
    - Whitespace normalization
    - Punctuation normalization
    - Trailing punctuation removal
    
    Parameters
    ----------
    text : str
        Raw question text
    
    Returns
    -------
    str
        Normalized question text
    """
    if pd.isna(text):
        return text
    
    text = str(text).strip()
    
    # Unicode normalization (NFKC decomposes combined characters)
    text = unicodedata.normalize("NFKC", text)
    
    # Normalize spaces around punctuation
    text = re.sub(r"\s+([:;,.?!])", r"\1", text)
    text = re.sub(r"([:;,.?!])(?=\S)", r"\1 ", text)
    
    # Normalize multiple whitespace to single space
    text = re.sub(r"\s+", " ", text).strip()
    
    # Remove trailing punctuation (?, !, etc.)
    text = re.sub(r"[?¿!。．\.]+$", "", text).strip()
    
    # Final whitespace cleanup
    text = re.sub(r"\s+", " ", text).strip()
    
    return text


def normalize_content_name(text: str) -> str:
    """
    Normalize content/module name.
    
    Parameters
    ----------
    text : str
        Raw content name
    
    Returns
    -------
    str
        Normalized content name
    """
    if pd.isna(text):
        return text
    
    text = str(text).strip()
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\s+", " ", text).strip()
    
    return text


def normalize_answer_value(value, answer_type: Optional[str] = None):
    """
    Normalize answer values.
    
    Parameters
    ----------
    value : any
        Raw answer value
    answer_type : str, optional
        Type of answer ("text", "numeric", "boolean", "date", etc.)
    
    Returns
    -------
    Normalized value
    """
    if pd.isna(value):
        return value
    
    if answer_type == "text":
        return str(value).strip()
    
    elif answer_type == "numeric":
        try:
            return float(value)
        except (ValueError, TypeError):
            return value
    
    elif answer_type == "boolean":
        if isinstance(value, bool):
            return value
        val_str = str(value).strip().lower()
        if val_str in ["yes", "y", "true", "1", "on"]:
            return True
        elif val_str in ["no", "n", "false", "0", "off"]:
            return False
        return value
    
    elif answer_type == "date":
        try:
            return pd.to_datetime(value)
        except (ValueError, TypeError):
            return value
    
    # Default: normalize as text
    return str(value).strip() if not pd.isna(value) else value


def normalize_dataframe_column(df: pd.DataFrame, col_name: str) -> pd.DataFrame:
    """
    Normalize values in a dataframe column in-place.
    
    Parameters
    ----------
    df : pd.DataFrame
        Dataframe to modify
    col_name : str
        Column name to normalize
    
    Returns
    -------
    pd.DataFrame
        The dataframe (modified in place)
    """
    if col_name not in df.columns:
        return df
    
    # Detect column type and normalize
    if pd.api.types.is_datetime64_any_dtype(df[col_name]):
        df[col_name] = pd.to_datetime(df[col_name], errors="coerce")
    elif pd.api.types.is_numeric_dtype(df[col_name]):
        df[col_name] = pd.to_numeric(df[col_name], errors="coerce")
    else:
        # Text column
        if col_name in ["Question", "question", "Content Name", "content_name", "module_name", "Content_Name_Normalized"]:
            df[col_name] = df[col_name].apply(normalize_question_text)
        else:
            df[col_name] = df[col_name].apply(lambda x: normalize_answer_value(x, "text"))
    
    return df


class TextNormalizer:
    """Stateful text normalizer that tracks variations and mappings."""
    
    def __init__(self):
        self.variations: dict = {}  # Maps normalized -> list of raw variations
        self.manual_mappings: dict = {}  # Maps raw -> standard
    
    def register_variation(self, raw_text: str):
        """Register a text variation."""
        normalized = normalize_question_text(raw_text)
        if normalized not in self.variations:
            self.variations[normalized] = []
        if raw_text not in self.variations[normalized]:
            self.variations[normalized].append(raw_text)
    
    def add_manual_mapping(self, raw_text: str, standard_text: str):
        """Add a manual mapping from raw to standard text."""
        self.manual_mappings[raw_text] = standard_text
    
    def normalize(self, raw_text: str) -> str:
        """
        Normalize text, checking manual mappings first.
        
        Parameters
        ----------
        raw_text : str
            Raw text to normalize
        
        Returns
        -------
        str
            Normalized or mapped text
        """
        if raw_text in self.manual_mappings:
            return self.manual_mappings[raw_text]
        return normalize_question_text(raw_text)
    
    def get_variations(self, normalized_text: str) -> list:
        """Get all raw variations for a normalized text."""
        return self.variations.get(normalized_text, [])
    
    def get_duplicate_groups(self) -> dict:
        """
        Get groups of raw texts that normalize to the same value.
        
        Returns
        -------
        dict
            Maps normalized text -> list of raw variations
        """
        return {k: v for k, v in self.variations.items() if len(v) > 1}


def find_duplicate_questions(df: pd.DataFrame, question_col: str = "Question") -> dict:
    """
    Find questions that normalize to the same text.
    
    Parameters
    ----------
    df : pd.DataFrame
        Dataframe with questions
    question_col : str
        Column name containing questions
    
    Returns
    -------
    dict
        Maps normalized question -> list of (raw question, count) tuples
    """
    if question_col not in df.columns:
        return {}
    
    normalizer = TextNormalizer()
    for q in df[question_col].dropna().unique():
        normalizer.register_variation(q)
    
    # Only return groups with duplicates
    duplicates = {}
    for normalized, raw_list in normalizer.variations.items():
        if len(raw_list) > 1:
            # Count occurrences in dataframe
            counts = [(raw, (df[question_col] == raw).sum()) for raw in raw_list]
            duplicates[normalized] = counts
    
    return duplicates


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and normalize column names.
    
    Parameters
    ----------
    df : pd.DataFrame
        Dataframe with potentially messy column names
    
    Returns
    -------
    pd.DataFrame
        Dataframe with cleaned column names
    """
    df.columns = [str(col).strip() for col in df.columns]
    return df

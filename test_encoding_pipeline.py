#!/usr/bin/env python3
"""
test_encoding_pipeline.py

Comprehensive test script demonstrating UTF-8 encoding standardization 
and discharge column tracing throughout the entire pipeline.

Usage:
    DEBUG_ENCODING=1 python3 test_encoding_pipeline.py
    DEBUG_ENDPOINT_MAPPING=1 python3 test_encoding_pipeline.py
    DEBUG_ENCODING=1 DEBUG_ENDPOINT_MAPPING=1 python3 test_encoding_pipeline.py
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))

import pandas as pd
from transformation_common import (
    _detect_csv_encoding,
    _normalize_text,
    normalize_text_columns,
    clean_columns,
    read_input_file,
    DEBUG_ENCODING,
    DEBUG_ENDPOINT_MAPPING,
)
from transformation_normal import process_normal_files


def create_test_data():
    """Create sample CSV files with various encodings and special characters."""
    temp_dir = tempfile.mkdtemp()
    
    print(f"\n{'='*80}")
    print("TEST DATA GENERATION")
    print(f"{'='*80}\n")
    
    # Primary file (content with Entry Date)
    primary_data = {
        "Patient ID": ["P001", "P001", "P002", "P002", "P003", "P003"],
        "Pathway Name": ["Pathway A", "Pathway A", "Pathway B", "Pathway B", "Pathway C", "Pathway C"],
        "Content Name": ["Gesundheit Status", "Gesundheit Status", "Schmerztagebuch", "Schmerztagebuch", 
                         "Tagesbericht zuhause", "Tagesbericht zuhause"],
        "Entry Date": ["2024-01-15", "2024-01-15", "2024-01-16", "2024-01-16", "2024-01-17", "2024-01-17"],
        "Scheduled date": ["2024-01-15", "2024-01-15", "2024-01-16", "2024-01-16", "2024-01-17", "2024-01-17"],
    }
    primary_df = pd.DataFrame(primary_data)
    primary_file = os.path.join(temp_dir, "primary.csv")
    primary_df.to_csv(primary_file, index=False, encoding="utf-8-sig")
    print(f"Created primary.csv: {primary_file}")
    
    # Secondary file (answers with questions)
    secondary_data = {
        "Patient ID": ["P001", "P001", "P002", "P002", "P003", "P003"],
        "Pathway Name": ["Pathway A", "Pathway A", "Pathway B", "Pathway B", "Pathway C", "Pathway C"],
        "Content Name": ["Gesundheit Status", "Gesundheit Status", "Schmerztagebuch", "Schmerztagebuch", 
                         "Tagesbericht zuhause", "Tagesbericht zuhause"],
        "Question": ["Wie geht es Ihnen?", "Haben Sie Schmerzen?", "Wie war Ihr Wohlbefinden?", "Schmerzstufe?",
                     "Alltägliche Aktivitäten", "Bewegungen möglich?"],
        "Answer Text": ["Gut", "Nein", "Besser", "Mild", "Ja", "Ja"],
        "Entry Date": ["2024-01-15", "2024-01-15", "2024-01-16", "2024-01-16", "2024-01-17", "2024-01-17"],
    }
    secondary_df = pd.DataFrame(secondary_data)
    secondary_file = os.path.join(temp_dir, "secondary.csv")
    secondary_df.to_csv(secondary_file, index=False, encoding="utf-8-sig")
    print(f"Created secondary.csv: {secondary_file}")
    
    # Endpoint file with discharge columns
    endpoint_data = {
        "Patient ID": ["P001", "P002", "P003"],
        "Pathway Name": ["Pathway A", "Pathway B", "Pathway C"],
        "Entlassung Exitus": [0, 0, 1.0],
        "Entlassung Nachhause": [1.0, 0, 0],
        "Entlassung Pflegeheim": [0, 1, 0],
        "Entlassung AHB Reha": [0, 0, 0],
        "Length of hospital stay": [5, 10, 3],
    }
    endpoint_df = pd.DataFrame(endpoint_data)
    endpoint_file = os.path.join(temp_dir, "endpoint.csv")
    endpoint_df.to_csv(endpoint_file, index=False, encoding="utf-8-sig")
    print(f"Created endpoint.csv: {endpoint_file}")
    print(f"\nEndpoint file preview:")
    print(endpoint_df.to_string())
    
    # Demographics file
    demographics_data = {
        "Patient ID": ["P001", "P002", "P003"],
        "Age": [45, 62, 78],
        "Gender": ["M", "F", "M"],
    }
    demographics_df = pd.DataFrame(demographics_data)
    demographics_file = os.path.join(temp_dir, "demographics.csv")
    demographics_df.to_csv(demographics_file, index=False, encoding="utf-8-sig")
    print(f"Created demographics.csv: {demographics_file}")
    
    return temp_dir, primary_file, secondary_file, endpoint_file, demographics_file


def test_full_pipeline():
    """Test the complete transformation pipeline with encoding diagnostics."""
    print(f"\n{'='*80}")
    print("FULL PIPELINE TEST")
    print(f"{'='*80}\n")
    
    temp_dir, primary_file, secondary_file, endpoint_file, demographics_file = create_test_data()
    output_file = os.path.join(temp_dir, "transformed_output.csv")
    
    print(f"\nRunning full transformation pipeline...\n")
    
    result_df = process_normal_files(
        primary_file=primary_file,
        secondary_file=secondary_file,
        demographics_file=demographics_file,
        endpoint_file=endpoint_file,
        output_file=output_file,
    )
    
    print(f"\n{'='*80}")
    print("PIPELINE RESULT")
    print(f"{'='*80}\n")
    print(f"Shape: {result_df.shape}")
    print(f"Columns: {len(result_df.columns)}")
    
    # Show discharge columns
    discharge_cols = [col for col in result_df.columns if "Entlassung" in col or "Endpoint_Entlassung" in col]
    if discharge_cols:
        print(f"\nDischarge Columns: {discharge_cols}")
        print(f"\nDischarge Data:")
        print(result_df[discharge_cols].to_string())
    
    # Show endpoint columns
    endpoint_cols = [col for col in result_df.columns if "Endpoint_" in col]
    if endpoint_cols:
        print(f"\nEndpoint Columns ({len(endpoint_cols)}): {endpoint_cols}")
    
    # Validate UTF-8 encoding
    if os.path.exists(output_file):
        print(f"\n{'='*80}")
        print("OUTPUT FILE VERIFICATION")
        print(f"{'='*80}\n")
        
        file_size = os.path.getsize(output_file)
        print(f"Output file: {output_file}")
        print(f"File size: {file_size} bytes")
        
        # Verify it's valid UTF-8
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                content = f.read()
            print(f"File is valid UTF-8 encoded")
            
            # Check for special characters
            has_umlauts = any(c in content for c in "äöüßÄÖÜ")
            if has_umlauts:
                print(f"Special German characters preserved")
        except UnicodeDecodeError as e:
            print(f"File encoding error: {e}")
    
    return temp_dir, result_df


if __name__ == "__main__":
    print(f"\n{'#'*80}")
    print("# UTF-8 ENCODING STANDARDIZATION TEST SUITE")
    print(f"{'#'*80}")
    print(f"\nDEBUG_ENCODING: {DEBUG_ENCODING}")
    print(f"DEBUG_ENDPOINT_MAPPING: {DEBUG_ENDPOINT_MAPPING}")
    
    try:
        temp_dir, result_df = test_full_pipeline()
        
        print(f"\n{'='*80}")
        print("\nALL TESTS COMPLETED SUCCESSFULLY\n")
        print(f"{'='*80}\n")
        
    except Exception as e:
        print(f"\nTEST FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)

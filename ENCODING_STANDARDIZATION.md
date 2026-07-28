# UTF-8 Encoding Standardization Implementation

## Overview

The entire file ingestion pipeline has been standardized to handle UTF-8 encoding consistently, with special attention to preserving German characters (ä, ö, ü, ß).

## Key Components

### 1. Encoding Detection (`_detect_csv_encoding`)
- Samples the first 10KB of CSV files
- Tries encodings in order: `utf-8-sig`, `utf-8`, `latin-1`, `cp1252`
- Falls back to `utf-8` if detection fails
- Logs detected encoding when `DEBUG_ENCODING=1`

### 2. Text Normalization (`_normalize_text`)
- Applies Unicode NFC (Canonical Composition) normalization
- Preserves special characters (ä → ä, not a)
- Strips leading/trailing whitespace
- Handles None/NaN values gracefully

### 3. Column Normalization (`clean_columns`)
- Normalizes all column names to NFC form
- Detects and warns about changes
- Validates expected German column names
- Logs validation status when `DEBUG_ENCODING=1`

### 4. Text Column Normalization (`normalize_text_columns`)
- Applies text normalization to all object (string) dtype columns
- Excludes key ID columns (Patient ID, Pathway Name) for efficiency
- Counts and logs number of normalized values when `DEBUG_ENCODING=1`

## Diagnostic Logging

Enable diagnostic output with environment variables:

```bash
# Encoding diagnostics only
DEBUG_ENCODING=1 python3 run_transformation.py ...

# Endpoint mapping diagnostics only
DEBUG_ENDPOINT_MAPPING=1 python3 run_transformation.py ...

# Both (comprehensive trace)
DEBUG_ENCODING=1 DEBUG_ENDPOINT_MAPPING=1 python3 run_transformation.py ...
```

### Debug Output Example

**Encoding Detection:**
```
✓ Detected encoding: utf-8-sig for endpoint.csv
📄 CSV file: endpoint.csv
   Detected encoding: utf-8-sig
   Loading as: utf-8
```

**Column Normalization:**
```
📋 Column Normalization:
   'Entlassung Exitus' → 'Entlassung Exitus'
   All 7 columns already normalized

🇩🇪 German Column Validation:
   ✓ Entlassung Exitus
   ✓ Entlassung Nachhause
   ✓ Entlassung Pflegeheim
   ✓ Entlassung AHB Reha
```

**Discharge Mapping Trace:**
```
DEBUG: BEFORE mapping - Entlassung Exitus
 dtype: float64
Entlassung Exitus
0.0    2
1.0    1
Name: count, dtype: int64

DEBUG: AFTER mapping - Entlassung Exitus
 dtype: str
Entlassung Exitus
NaN    2
Ja     1
Name: count, dtype: int64
```

**Endpoint Merge Trace:**
```
[BEFORE MERGE] Final dataframe columns:
  No discharge columns found

[AFTER PREPARE] Endpoint dataframe columns:
  Discharge-related columns: ['Endpoint_Entlassung Exitus', 'Endpoint_Entlassung Nachhause', ...]

[AFTER MERGE] Final dataframe columns:
  All discharge-related columns: ['Endpoint_Entlassung Exitus', 'Endpoint_Entlassung Nachhause', ...]
```

## Pipeline Processing Flow

### 1. File Reading (`read_input_file`)
- Detects CSV encoding before reading
- Reads with detected encoding
- Falls back to UTF-8 on error
- Excel files (XLSX/XLS) are handled natively by pandas

### 2. Column Cleaning (`clean_columns`)
- Normalizes column names to NFC
- Validates expected columns
- Logs changes

### 3. Text Normalization (`normalize_text_columns`)
- Applied to all content, answer, and endpoint files
- Preserves German characters
- Normalizes whitespace

### 4. Endpoint Processing (`prepare_endpoint_file`)
- Reads and normalizes endpoint CSV
- Detects discharge columns (Entlassung *)
- Maps numeric values (0/1/0.0/1.0) to text (pd.NA/"Ja")
- Renames columns with "Endpoint_" prefix
- Traces values at each stage when debugging

### 5. Export
- Writes CSV with UTF-8-sig encoding (BOM included)
- Preserves all special characters
- Creates valid UTF-8 output

## Discharge Column Mapping

The discharge column mapping is critical for data quality:

**Before Mapping:**
```
Entlassung Exitus: 0, 1.0, 0
Entlassung Nachhause: 1, 0, 0.0
```

**After Mapping:**
```
Entlassung Exitus: pd.NA, "Ja", pd.NA
Entlassung Nachhause: "Ja", pd.NA, pd.NA
```

**After Rename:**
```
Endpoint_Entlassung Exitus: pd.NA, "Ja", pd.NA
Endpoint_Entlassung Nachhause: "Ja", pd.NA, pd.NA
```

## Testing the Implementation

Run the comprehensive test suite:

```bash
# Test with full diagnostics
DEBUG_ENCODING=1 DEBUG_ENDPOINT_MAPPING=1 python3 test_encoding_pipeline.py

# Output shows:
# - Encoding detection for each file
# - Column normalization results
# - German character validation
# - Discharge value transformation at each pipeline stage
# - Final UTF-8 verification
```

## Files Modified

1. **app/transformation_common.py**
   - Added `_detect_csv_encoding()` for encoding detection
   - Added `_normalize_text()` for Unicode normalization
   - Added `normalize_text_columns()` for bulk text normalization
   - Updated `clean_columns()` with column validation logging
   - Updated `read_input_file()` to detect and use appropriate encoding
   - Updated `prepare_endpoint_file()` with comprehensive tracing
   - Updated all `build_*` functions to normalize text columns

2. **app/transformation_normal.py**
   - Added comprehensive endpoint merge tracing
   - Added export encoding diagnostics
   - Shows discharge columns before/after merge

3. **app/config_loader.py**
   - Added encoding detection for variable mapping CSV files
   - Tries multiple encodings for robustness

## Character Preservation Examples

All of these are preserved correctly:

| German Character | Example | Preserved |
|---|---|---|
| ä | Blähungen | ✓ |
| ö | Schmerzen möglich | ✓ |
| ü | Für Sie | ✓ |
| ß | Straße | ✓ |
| Ä | ÄNDERUNGEN | ✓ |
| Ö | GRÖSSE | ✓ |
| Ü | ÜBERSICHT | ✓ |

## Troubleshooting

### Issue: Encoding errors on import
**Solution:** Enable DEBUG_ENCODING to see which encoding was detected and fix the source file if needed.

### Issue: Column names don't match
**Solution:** Enable DEBUG_ENCODING to see column normalization results. Check for hidden characters.

### Issue: Discharge values not mapped correctly
**Solution:** Enable DEBUG_ENDPOINT_MAPPING to trace values at each stage. Check input data types.

### Issue: Output file has corrupted characters
**Solution:** Verify the file is read with UTF-8 encoding. All output uses utf-8-sig (BOM included).

## Performance Considerations

- Encoding detection samples only first 10KB of file (fast)
- Text normalization is applied lazily (only to necessary columns)
- Column validation is only logged in debug mode
- NaN/None values are handled efficiently

## Integration with Existing Code

The encoding standardization is transparent to existing code:
- All CSV reads now automatically detect and handle encoding
- All text is normalized to NFC form
- All output uses UTF-8-sig encoding
- Existing workflows continue to work without modification

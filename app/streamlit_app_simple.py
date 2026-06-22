"""
streamlit_app_simple.py

Simplified Streamlit app for quick data transformation.
Accepts multiple input files and transforms to wide format (one row per patient).
"""

import streamlit as st
import pandas as pd
import io
from pathlib import Path
from datetime import datetime

from transformation_common import read_input_file, clean_columns

st.set_page_config(
    page_title="Quick Patient Data Transformer",
    page_icon="📊",
    layout="wide",
)

st.markdown("# 📊 Quick Patient Data Transformer")
st.markdown("""
Upload your files and transform them to a simple wide format where each patient is one row 
and each question/field is a column. No complex configuration needed!
""")

st.markdown("---")

# File upload
st.subheader("📤 Upload Files")
st.info("Upload one or more CSV or Excel files. They'll be merged by patient ID into a single wide-format output.")

uploaded_files = st.file_uploader(
    "Choose files",
    type=["csv", "xlsx"],
    accept_multiple_files=True,
    key="file_uploader"
)

if not uploaded_files:
    st.warning("Please upload at least one file to get started.")
    st.stop()

st.success(f"✅ {len(uploaded_files)} file(s) uploaded")

# Display file info
with st.expander("📋 File Details"):
    for file in uploaded_files:
        try:
            df = read_input_file(file)
            df = clean_columns(df)
            st.caption(f"**{file.name}** — {len(df)} rows, {len(df.columns)} columns")
            st.dataframe(df.head(3), use_container_width=True)
        except Exception as e:
            st.error(f"Error reading {file.name}: {e}")

st.markdown("---")

# Configuration
st.subheader("⚙️ Configuration")

# Try to auto-detect columns
first_file = uploaded_files[0]
df_sample = read_input_file(first_file)
df_sample = clean_columns(df_sample)

col1, col2 = st.columns([1, 1])

with col1:
    st.write("**Patient ID Column**")
    st.caption("Which column uniquely identifies each patient?")
    
    potential_id_cols = [col for col in df_sample.columns if 'id' in col.lower() or 'patient' in col.lower()]
    default_id = potential_id_cols[0] if potential_id_cols else df_sample.columns[0]
    
    patient_id_col = st.selectbox(
        "Patient ID Column",
        df_sample.columns.tolist(),
        index=df_sample.columns.tolist().index(default_id),
        label_visibility="collapsed",
        key="patient_id_select"
    )

with col2:
    st.write("**Question Column**")
    st.caption("Which column contains the question/field names?")
    
    potential_q_cols = [col for col in df_sample.columns if 'question' in col.lower() or 'field' in col.lower()]
    default_q = potential_q_cols[0] if potential_q_cols else df_sample.columns[2] if len(df_sample.columns) > 2 else df_sample.columns[0]
    
    question_col = st.selectbox(
        "Question Column",
        df_sample.columns.tolist(),
        index=df_sample.columns.tolist().index(default_q),
        label_visibility="collapsed",
        key="question_select"
    )

col3, col4 = st.columns([1, 1])

with col3:
    st.write("**Answer Column**")
    st.caption("Which column contains the answers/values?")
    
    potential_answer_cols = [col for col in df_sample.columns if 'answer' in col.lower() or 'value' in col.lower() or 'result' in col.lower()]
    default_answer = potential_answer_cols[0] if potential_answer_cols else df_sample.columns[-1]
    
    answer_col = st.selectbox(
        "Answer Column",
        df_sample.columns.tolist(),
        index=df_sample.columns.tolist().index(default_answer),
        label_visibility="collapsed",
        key="answer_select"
    )

st.markdown("---")

st.markdown("---")

# Transform
st.subheader("▶️ Transform Data")

if st.button("🚀 Pivot to Wide Format (One Row Per Patient)", type="primary"):
    with st.spinner("Transforming your data..."):
        try:
            # Load all files
            dataframes = []
            for file in uploaded_files:
                df = read_input_file(file)
                df = clean_columns(df)
                dataframes.append((file.name, df))
            
            # Start with first file
            result_df = dataframes[0][1].copy()
            
            # Append remaining files (union)
            for file_name, df in dataframes[1:]:
                result_df = pd.concat([result_df, df], ignore_index=True)
            
            # Validate required columns exist
            if patient_id_col not in result_df.columns:
                st.error(f"Patient ID column '{patient_id_col}' not found")
                st.stop()
            if question_col not in result_df.columns:
                st.error(f"Question column '{question_col}' not found")
                st.stop()
            if answer_col not in result_df.columns:
                st.error(f"Answer column '{answer_col}' not found")
                st.stop()
            
            # Pivot: Transform long format to wide format
            # One row per patient, one column per question
            result_df = result_df.pivot_table(
                index=patient_id_col,
                columns=question_col,
                values=answer_col,
                aggfunc='first'  # If multiple values for same question, take first
            )
            result_df = result_df.reset_index()
            result_df.columns.name = None
            
            # Sort by patient ID
            result_df = result_df.sort_values(patient_id_col).reset_index(drop=True)
            
            st.session_state.result_df = result_df
            
            st.success("✅ Transformation complete!")
            
        except Exception as e:
            st.error(f"❌ Transformation failed: {e}")
            import traceback
            st.error(traceback.format_exc())

st.markdown("---")

# Results
st.subheader("📊 Results")

if "result_df" not in st.session_state:
    st.info("Click 'Transform to Wide Format' to see results.")
else:
    result_df = st.session_state.result_df
    
    st.success(f"✅ {len(result_df)} patients, {len(result_df.columns)} columns")
    
    # Preview
    st.markdown("### Preview")
    st.dataframe(result_df.head(10), use_container_width=True)
    
    # Statistics
    with st.expander("📈 Data Statistics"):
        st.write(f"**Total Patients:** {len(result_df)}")
        st.write(f"**Total Columns:** {len(result_df.columns)}")
        st.write(f"**Memory Usage:** {result_df.memory_usage(deep=True).sum() / 1024**2:.2f} MB")
        
        # Missing data
        st.write("**Missing Data by Column:**")
        missing = result_df.isnull().sum()
        missing = missing[missing > 0].sort_values(ascending=False)
        if len(missing) > 0:
            st.dataframe(missing)
        else:
            st.write("No missing values!")
    
    st.markdown("---")
    st.markdown("### 📥 Download Results")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # CSV download
        csv = result_df.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="⬇️ Download as CSV",
            data=csv,
            file_name=f"patient_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
    
    with col2:
        # Excel download
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            result_df.to_excel(writer, sheet_name="Patients", index=False)
        output.seek(0)
        
        st.download_button(
            label="⬇️ Download as Excel",
            data=output.getvalue(),
            file_name=f"patient_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    # Data dictionary option
    st.markdown("---")
    st.markdown("### 📖 Optional: Generate Data Dictionary")
    
    if st.button("Create data dictionary"):
        data_dict = pd.DataFrame({
            "Column": result_df.columns,
            "Data Type": result_df.dtypes.astype(str).values,
            "Non-Null Count": result_df.count().values,
            "Missing": result_df.isnull().sum().values,
            "Missing %": (result_df.isnull().sum().values / len(result_df) * 100).round(2),
        })
        
        csv = data_dict.to_csv(index=False, encoding="utf-8-sig")
        st.download_button(
            label="⬇️ Download data dictionary",
            data=csv,
            file_name=f"data_dictionary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )

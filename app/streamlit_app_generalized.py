"""
streamlit_app_generalized.py

Generalized Streamlit app supporting flexible column mapping and multiple hospital/project configurations.
Implements the workflow described in the instructions:
1. Upload files
2. Assign file roles
3. Map columns
4. Select iterative content
5. Configure non-iterative policy
6. Map endpoints
7. Validation preview
8. Download outputs
"""

import streamlit as st
import pandas as pd
import io
from pathlib import Path
from datetime import datetime

from schema_mapping import FileRole, FileRoleMapping, ColumnMapping, MappingBuilder
from validation import SchemaValidator, TransformationValidator, generate_validation_summary
from config_loader import ConfigLibrary, TransformationConfig, load_variable_mapping_file, apply_variable_mapping
from transformation_common import read_input_file, clean_columns, read_input_file_with_mapping, build_long_observation_table, normalize_long_table
from normalization import find_duplicate_questions
from endpoints import EndpointRegistry, EndpointDeriver
from data_dictionary import DataDictionaryGenerator
from quality_reports import QualityReportGenerator
from transformation_normal import process_normal_files
from transformation_iterative import process_iterative_files


st.set_page_config(
    page_title="Generalized Patient Data Transformer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Sidebar: Configuration Selection ──────────────────────────────────────────
st.sidebar.title("⚙️ Configuration")
config_name = st.sidebar.selectbox(
    "Select project configuration",
    ["ulm_erp", "generic"],
    format_func=lambda x: {"ulm_erp": "Ulm ERP", "generic": "Generic Template"}.get(x, x)
)

selected_config = ConfigLibrary.get_config(config_name)
st.sidebar.info(f"**{selected_config.name}**\n\n{selected_config.description}")

workflow_mode = st.sidebar.radio(
    "Transformation workflow",
    ["normal", "iterative"],
    format_func=lambda x: {"normal": "Normal (event-based)", "iterative": "Iterative (repeated events as columns)"}.get(x, x)
)

st.sidebar.markdown("---")
st.sidebar.markdown("**About this app**\n\nFlexible data transformation supporting multiple hospitals and data structures.")

# ── Main Title ────────────────────────────────────────────────────────────────
st.markdown("# 📊 Patient Data Transformer (Generalized)")
st.markdown("""
This app transforms hospital/pathway data into research-ready datasets with automatic quality checks,
data dictionaries, and clinical endpoint derivation. Works with different hospitals and data structures.
""")

# ── Tabs for multi-step workflow ──────────────────────────────────────────────
tabs = st.tabs([
    "1️⃣ Upload Files",
    "2️⃣ Map Columns",
    "3️⃣ Configuration",
    "4️⃣ Validation",
    "5️⃣ Transform",
    "6️⃣ Results",
])

# Initialize session state for tracking
if "uploaded_files" not in st.session_state:
    st.session_state.uploaded_files = {}
if "file_roles" not in st.session_state:
    st.session_state.file_roles = {}
if "column_mappings" not in st.session_state:
    st.session_state.column_mappings = {}
if "transformation_result" not in st.session_state:
    st.session_state.transformation_result = None
if "validation_report" not in st.session_state:
    st.session_state.validation_report = None

# ═════════════════════════════════════════════════════════════════════════════
# TAB 1: Upload Files
# ═════════════════════════════════════════════════════════════════════════════
with tabs[0]:
    st.subheader("Step 1: Upload Your Files")
    
    st.info("""
    Upload files for your transformation. Supported formats are **CSV** and **Excel (.xlsx)**.
    For each file, specify its role:
    - **Answers**: Patient responses to questionnaires (REQUIRED)
    - **Scheduled Content**: Pathway/content information
    - **Demographics**: Age, sex, other patient attributes
    - **Endpoints**: Clinical endpoints, dates, outcomes
    - **Adherence**: Pathway completion/adherence tracking
    
    The demographics role can accept multiple files; they will be concatenated and merged together.
    """)
    
    # File upload interface
    col1, col2 = st.columns([1, 1])
    
    with col1:
        uploaded_files = st.file_uploader(
            "Upload transformation files",
            type=["csv", "xlsx"],
            accept_multiple_files=True,
            key="file_uploader"
        )
    
    with col2:
        if uploaded_files:
            st.success(f"✅ {len(uploaded_files)} file(s) uploaded")
            st.caption("Tip: you can upload Excel or CSV files here. Assign any metadata/enrichment files to the Demographics role and multiple files will be merged together.")
            
            # Display uploaded file info
            for file in uploaded_files:
                file_name = file.name
                try:
                    df = read_input_file(file)
                    st.caption(f"📄 {file_name} — {len(df)} rows, {len(df.columns)} columns")
                except Exception as e:
                    st.error(f"Could not read {file_name}: {e}")
    
    # Store files and assign roles
    if uploaded_files:
        st.markdown("### Assign File Roles")
        
        for file in uploaded_files:
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.caption(f"📄 {file.name}")
            
            with col2:
                file_role = st.selectbox(
                    f"Role for {file.name}",
                    FileRole.ALL,
                    format_func=lambda x: FileRole.DESCRIPTIONS.get(x, x),
                    key=f"role_{file.name}",
                    label_visibility="collapsed"
                )
                
                st.session_state.file_roles[file.name] = file_role
                st.session_state.uploaded_files[file.name] = file
        
        if st.button("✅ Confirm File Uploads and Roles"):
            st.success("Files and roles confirmed! Proceed to next step.")

# ═════════════════════════════════════════════════════════════════════════════
# TAB 2: Map Columns
# ═════════════════════════════════════════════════════════════════════════════
with tabs[1]:
    st.subheader("Step 2: Map Columns to Standard Names")
    
    if not st.session_state.uploaded_files:
        st.warning("Please upload files in Step 1 first.")
    else:
        st.info("""
        Map your file columns to standard internal names. The app will auto-detect mappings,
        but you can override them here for better accuracy.
        """)
        
        for file_name, file_role in st.session_state.file_roles.items():
            file = st.session_state.uploaded_files[file_name]
            
            st.markdown(f"### {file_name} ({file_role})")
            
            try:
                df = read_input_file(file)
                df = clean_columns(df)
                
                # Auto-detect mapping
                auto_mapping = MappingBuilder.auto_detect_mapping(df)
                
                # Display and allow edits
                st.caption("Auto-detected mappings (edit if needed):")
                
                mapping_config = {}
                for standard_name, detected_raw in auto_mapping.items():
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        st.write(f"**{standard_name}**")
                    with col2:
                        selected = st.selectbox(
                            f"Map to column ({standard_name})",
                            [None] + df.columns.tolist(),
                            index=df.columns.tolist().index(detected_raw) + 1 if detected_raw and detected_raw in df.columns else 0,
                            key=f"mapping_{file_name}_{standard_name}",
                            label_visibility="collapsed"
                        )
                        mapping_config[standard_name] = selected
                
                st.session_state.column_mappings[file_name] = ColumnMapping(mapping_config)
                
            except Exception as e:
                st.error(f"Error processing {file_name}: {e}")

# ═════════════════════════════════════════════════════════════════════════════
# TAB 3: Configuration
# ═════════════════════════════════════════════════════════════════════════════
with tabs[2]:
    st.subheader("Step 3: Configure Transformation")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### Iterative Content")
        st.write("Content names that should preserve repeated entries as separate columns (_1, _2, _3...):")
        
        iterative_contents = st.multiselect(
            "Select iterative content",
            selected_config.iterative_contents if selected_config.iterative_contents else [],
            default=selected_config.iterative_contents if selected_config.iterative_contents else [],
            key="iterative_contents_selector"
        )
    
    with col2:
        st.markdown("### Non-Iterative Policy")
        st.write("How to handle repeated answers in non-iterative questionnaires:")
        
        policy = st.radio(
            "Policy",
            ["latest_non_blank", "first_non_blank", "preserve_all", "flag_only"],
            format_func=lambda x: {
                "latest_non_blank": "Keep latest non-blank answer",
                "first_non_blank": "Keep first non-blank answer",
                "preserve_all": "Preserve all as iterations",
                "flag_only": "Flag conflicts without changing data"
            }.get(x, x),
            key="non_iterative_policy_selector"
        )
        
        flag_conflicts = st.checkbox(
            "Flag conflicting repeated answers",
            value=True,
            key="flag_conflicts_selector"
        )

# ═════════════════════════════════════════════════════════════════════════════
# TAB 4: Validation
# ═════════════════════════════════════════════════════════════════════════════
with tabs[3]:
    st.subheader("Step 4: Validation Preview")
    
    if not st.session_state.uploaded_files:
        st.warning("Please upload files first.")
    else:
        if st.button("🔍 Run Validation"):
            # Load files with mappings
            file_role_mapping = {}
            for file_name, file_role in st.session_state.file_roles.items():
                file = st.session_state.uploaded_files[file_name]
                df = read_input_file(file)
                df = clean_columns(df)
                
                mapping = st.session_state.column_mappings.get(file_name)
                if mapping is None:
                    auto_mapping = MappingBuilder.auto_detect_mapping(df)
                    mapping = ColumnMapping(auto_mapping)
                
                file_role_mapping[file_name] = (file_role, df, mapping)
            
            # Validate
            validator = TransformationValidator()
            report = validator.validate_transformation_setup(file_role_mapping)
            st.session_state.validation_report = report
            
            # Display report
            if report.has_errors():
                st.error("❌ Validation failed. Fix errors before proceeding.")
                for error in report.get_errors():
                    st.error(f"• {error.message}")
            else:
                st.success("✅ Validation passed!")
                
                if report.get_warnings():
                    st.warning("⚠️ Warnings:")
                    for warning in report.get_warnings():
                        st.warning(f"• {warning.message}")
                
                if report.get_infos():
                    st.info("ℹ️ Info:")
                    for info in report.get_infos():
                        st.info(f"• {info.message}")

# ═════════════════════════════════════════════════════════════════════════════
# TAB 5: Transform
# ═════════════════════════════════════════════════════════════════════════════
with tabs[4]:
    st.subheader("Step 5: Run Transformation")
    
    if not st.session_state.uploaded_files:
        st.warning("Please upload files first.")
    elif st.session_state.validation_report and st.session_state.validation_report.has_errors():
        st.error("Please fix validation errors first.")
    else:
        if st.button("▶️ Run Transformation"):
            with st.spinner("Transforming data..."):
                try:
                    # Get files by role
                    answers_file = None
                    scheduled_file = None
                    demographics_files = []

                    for file_name, file_role in st.session_state.file_roles.items():
                        file = st.session_state.uploaded_files[file_name]
                        if file_role == FileRole.ANSWERS:
                            answers_file = file
                        elif file_role == FileRole.SCHEDULED_CONTENT:
                            scheduled_file = file
                        elif file_role == FileRole.DEMOGRAPHICS:
                            demographics_files.append(file)

                    # If multiple demographics/enrichment files were provided, read and concatenate them
                    demographics_file = None
                    if demographics_files:
                        demo_dfs = []
                        for f in demographics_files:
                            try:
                                dfd = read_input_file(f)
                                dfd = clean_columns(dfd)
                                demo_dfs.append(dfd)
                            except Exception as e:
                                st.warning(f"Could not read demographics file {getattr(f, 'name', str(f))}: {e}")

                        if demo_dfs:
                            try:
                                demographics_file = pd.concat(demo_dfs, ignore_index=True)
                            except Exception:
                                # fallback to first file if concat fails for any reason
                                demographics_file = demo_dfs[0]

                    # Run transformation using appropriate workflow
                    result_df = process_files(
                        answers_file,
                        scheduled_file,
                        demographics_file=demographics_file,
                        workflow=workflow_mode
                    )
                    
                    st.session_state.transformation_result = result_df
                    st.success("✅ Transformation complete!")
                    
                except Exception as e:
                    st.error(f"Transformation failed: {e}")
                    import traceback
                    st.code(traceback.format_exc())

# ═════════════════════════════════════════════════════════════════════════════
# TAB 6: Results & Downloads
# ═════════════════════════════════════════════════════════════════════════════
with tabs[5]:
    st.subheader("Step 6: Download Results")
    
    if st.session_state.transformation_result is None:
        st.info("Run the transformation in Step 5 to see results.")
    else:
        result_df = st.session_state.transformation_result
        
        st.success(f"✅ Transformation complete! {len(result_df)} rows, {len(result_df.columns)} columns")
        
        # Display preview
        st.markdown("### Output Preview")
        st.dataframe(result_df.head(10), use_container_width=True)
        
        # Generate supporting files
        st.markdown("### Generate Supporting Files")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📖 Generate Data Dictionary"):
                generator = DataDictionaryGenerator()
                generator.add_from_dataframe(result_df, source_file="output")
                dictionary = generator.to_dataframe()
                
                csv = dictionary.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    label="⬇️ Download data_dictionary.csv",
                    data=csv,
                    file_name="data_dictionary.csv",
                    mime="text/csv"
                )
        
        with col2:
            if st.button("📊 Generate Quality Report"):
                report_data = QualityReportGenerator.generate_complete_report(
                    result_df, result_df
                )
                
                # Create Excel workbook
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine="openpyxl") as writer:
                    for tab_name, df in report_data.items():
                        df.to_excel(writer, sheet_name=tab_name, index=False)
                output.seek(0)
                
                st.download_button(
                    label="⬇️ Download data_quality_report.xlsx",
                    data=output.getvalue(),
                    file_name="data_quality_report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        
        with col3:
            if st.button("📥 Download Main Output"):
                csv = result_df.to_csv(index=False, encoding="utf-8-sig")
                st.download_button(
                    label="⬇️ Download patient_data_transformed.csv",
                    data=csv,
                    file_name="patient_data_transformed.csv",
                    mime="text/csv"
                )


def process_files(answers_file, scheduled_file, demographics_file=None, workflow="normal"):
    """
    Process files using the appropriate workflow.
    
    This is a wrapper that delegates to the existing transformation modules.
    """
    if workflow == "normal":
        return process_normal_files(
            answers_file,
            scheduled_file,
            demographics_file=demographics_file
        )
    else:
        return process_iterative_files(
            answers_file,
            scheduled_file,
            demographics_file=demographics_file
        )


if __name__ == "__main__":
    pass

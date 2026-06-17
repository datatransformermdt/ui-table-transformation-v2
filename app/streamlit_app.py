import base64
import streamlit as st
from pathlib import Path
from transformation import process_files


def img_to_base64(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


st.set_page_config(
    page_title="Patient Data Transformer",
    page_icon="📊",
    layout="wide",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
        .stApp { background-color: #F5F5F5; }

        /* ── Hero ── */
        .hero {
            background: #fff;
            border: 0.5px solid #E0E0E0;
            border-radius: 12px;
            padding: 14px 20px;
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 24px;
        }
        .hero-logo {
            width: 38px; height: 38px;
            background: #005C9C;
            border-radius: 9px;
            display: flex; align-items: center; justify-content: center;
            flex-shrink: 0;
        }
        .hero-logo img {
            height: 24px;
            object-fit: contain;
            filter: brightness(0) invert(1);
        }
        .hero-title { font-size: 15px; font-weight: 700; color: #0F172A; margin: 0; }
        .hero-sub   { font-size: 12px; color: #64748B; margin: 2px 0 0 0; }
        .hero-badge {
            margin-left: auto;
            font-size: 11px; font-weight: 600;
            color: #185FA5; background: #E6F1FB;
            padding: 4px 12px; border-radius: 99px; white-space: nowrap;
        }

        /* ── Phase headers ── */
        .phase-header {
            display: flex; align-items: flex-start; gap: 12px;
            margin-bottom: 14px;
        }
        .phase-num {
            width: 28px; height: 28px; border-radius: 50%;
            background: #005C9C; color: #fff;
            font-size: 13px; font-weight: 700;
            display: flex; align-items: center; justify-content: center;
            flex-shrink: 0; margin-top: 2px;
        }
        .phase-num.done { background: #3B6D11; }
        .phase-num.pending { background: #CBD5E1; color: #64748B; }
        .phase-title { font-size: 14px; font-weight: 700; color: #0F172A; margin: 0; }
        .phase-hint  { font-size: 12px; color: #64748B; margin: 3px 0 0 0; }

        /* ── Upload cards ── */
        .upload-card {
            background: #fff;
            border: 0.5px solid #E0E0E0;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 4px;
        }
        .upload-card.done {
            border: 1.5px solid #3B6D11;
            background: #F4FAF0;
        }
        .upload-card-file-label {
            font-size: 10px; font-weight: 700; color: #94A3B8;
            text-transform: uppercase; letter-spacing: 0.07em;
            margin-bottom: 6px;
        }
        .upload-card-title { font-size: 14px; font-weight: 700; color: #0F172A; margin-bottom: 4px; }
        .upload-card-desc  { font-size: 12px; color: #64748B; line-height: 1.6; margin-bottom: 10px; }
        .upload-card-example {
            font-size: 11px; color: #64748B;
            background: #F1F5F9; border-radius: 6px;
            padding: 6px 10px; margin-bottom: 12px;
        }
        .upload-card-example span { color: #0C447C; font-weight: 600; }
        .upload-status {
            display: flex; align-items: center; gap: 8px;
            padding: 8px 12px; border-radius: 8px;
            background: #EAF3DE; border: 0.5px solid #C0DD97;
        }
        .upload-status-dot {
            width: 8px; height: 8px; border-radius: 50%;
            background: #3B6D11; flex-shrink: 0;
        }
        .upload-status-text { font-size: 12px; font-weight: 600; color: #27500A; }

        /* ── Workflow cards ── */
        .workflow-card {
            background: #fff;
            border: 0.5px solid #E0E0E0;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 4px;
        }
        .workflow-card.selected {
            border: 2px solid #005C9C;
            background: #F0F7FF;
        }
        .workflow-card-title    { font-size: 14px; font-weight: 700; color: #0F172A; margin-bottom: 4px; }
        .workflow-card-subtitle { font-size: 12px; color: #64748B; line-height: 1.6; margin-bottom: 12px; }
        .workflow-example-label {
            font-size: 10px; font-weight: 700; color: #94A3B8;
            text-transform: uppercase; letter-spacing: 0.07em; margin-bottom: 6px;
        }
        .mini-table {
            width: 100%; border-collapse: collapse;
            font-size: 11px; font-family: Arial, sans-serif;
        }
        .mini-table th {
            background: #EEF4FB; color: #185FA5; font-weight: 700;
            padding: 4px 7px; text-align: left; border: 0.5px solid #D0E4F5;
        }
        .mini-table td {
            padding: 4px 7px; border: 0.5px solid #E8EEF5; color: #3C3C3C;
        }
        .mini-table tr:nth-child(even) td { background: #F8FAFD; }
        .mini-table.green th { background: #EAF3DE; color: #3B6D11; border-color: #C0DD97; }
        .mini-table.green td { border-color: #E8F3DE; }
        .mini-table.green tr:nth-child(even) td { background: #F4FAF0; }

        /* ── Run button ── */
        div.stButton > button {
            background-color: #005C9C !important;
            color: white !important;
            border: none !important;
            border-radius: 10px !important;
            padding: 0.8rem 1.2rem !important;
            font-weight: 700 !important;
            font-size: 0.95rem !important;
            width: 100% !important;
        }
        div.stButton > button:hover { background-color: #004880 !important; }
        div.stButton > button:disabled {
            background-color: #E2E8F0 !important;
            color: #94A3B8 !important;
        }

        /* ── Download button ── */
        div.stDownloadButton > button {
            background-color: #3B6D11 !important;
            color: white !important;
            border: none !important;
            border-radius: 10px !important;
            padding: 0.75rem 1.2rem !important;
            font-weight: 700 !important;
            font-size: 0.9rem !important;
            width: 100% !important;
        }
        div.stDownloadButton > button:hover { background-color: #27500A !important; }

        /* ── Result status ── */
        .status-box {
            background: #EAF3DE; border: 0.5px solid #C0DD97;
            border-radius: 10px; padding: 14px 16px;
            font-size: 13px; color: #27500A; margin-bottom: 16px;
        }

        /* ── Reassurance bar ── */
        .reassurance {
            background: #fff; border: 0.5px solid #E0E0E0;
            border-radius: 10px; padding: 12px 16px;
            display: flex; align-items: flex-start; gap: 10px;
            margin-top: 12px;
        }
        .reassurance p { font-size: 12px; color: #64748B; line-height: 1.6; margin: 0; }
        .reassurance strong { color: #0F172A; }

        /* ── Notice (missing files) ── */
        .notice {
            background: #FFF8E6; border: 0.5px solid #FAC775;
            border-radius: 10px; padding: 10px 16px;
            font-size: 12px; color: #633806;
            text-align: center; margin-top: 8px;
        }

        .spacer { margin-bottom: 1.25rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session state ──────────────────────────────────────────────────────────────
primary_done      = st.session_state.get("primary_file") is not None
secondary_done    = st.session_state.get("secondary_file") is not None
demographics_done = st.session_state.get("demographics_file") is not None
required_done     = primary_done and secondary_done

# ── Hero ───────────────────────────────────────────────────────────────────────
app_dir = Path(__file__).parent.parent
logo_path = app_dir / "assets" / "medtronic_logo.png"
if logo_path.exists():
    logo_b64   = img_to_base64(logo_path)
    logo_inner = f'<img src="data:image/png;base64,{logo_b64}" alt="Medtronic">'
else:
    logo_inner = ""

st.markdown(
    f"""
    <div class="hero">
        <div class="hero-logo">{logo_inner}</div>
        <div>
            <p class="hero-title">Patient data transformer</p>
            <p class="hero-sub">Prepare questionnaire data for analysis — no technical knowledge needed</p>
        </div>
        <div class="hero-badge">Medtronic</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── STEP 1 — Upload files ──────────────────────────────────────────────────────
step1_num_cls = "done" if required_done else ""
st.markdown(
    f"""
    <div class="phase-header">
        <div class="phase-num {step1_num_cls}">{"✓" if required_done else "1"}</div>
        <div>
            <p class="phase-title">Step 1 — Upload your files</p>
            <p class="phase-hint">Upload the first two required files; the demographics file is optional.</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)

with col1:
    card_cls = "upload-card done" if primary_done else "upload-card"
    if primary_done:
        fname = st.session_state["primary_file"].name
        status_block = (
            '<div class="upload-status">'
            '<div class="upload-status-dot"></div>'
            '<div class="upload-status-text">' + fname + ' — uploaded</div>'
            '</div>'
        )
    else:
        status_block = ""
    st.markdown(
        '<div class="' + card_cls + '">'
        '<div class="upload-card-file-label">File 1 of 3</div>'
        '<div class="upload-card-title">Questions &amp; schedule</div>'
        '<div class="upload-card-desc">The file that lists which questionnaires each patient was assigned and when.</div>'
        '<div class="upload-card-example">'
        '<div class="workflow-example-label">Source columns</div>'
        '<table class="mini-table"><tr><th>Patient ID</th><th>Pathway Name</th><th>Content Name</th><th>Input Date</th><th>Scheduled date</th></tr></table>'
        '<div style="margin-top:8px;font-size:11px;color:#64748B;">Example file name: <span>data.csv</span></div>'
        '</div>'
        + status_block + '</div>',
        unsafe_allow_html=True,
    )
    st.file_uploader(
        "Questions & schedule file",
        type=["csv", "xlsx"],
        key="primary_file",
        label_visibility="collapsed",
    )

with col2:
    card_cls = "upload-card done" if secondary_done else "upload-card"
    if secondary_done:
        fname = st.session_state["secondary_file"].name
        status_block = (
            '<div class="upload-status">'
            '<div class="upload-status-dot"></div>'
            '<div class="upload-status-text">' + fname + ' — uploaded</div>'
            '</div>'
        )
    else:
        status_block = ""
    st.markdown(
        '<div class="' + card_cls + '">'
        '<div class="upload-card-file-label">File 2 of 3</div>'
        '<div class="upload-card-title">Patient answers</div>'
        '<div class="upload-card-desc">The file that contains how each patient responded to each question.</div>'
        '<div class="upload-card-example">'
        '<div class="workflow-example-label">Source columns</div>'
        '<table class="mini-table"><tr><th>Patient ID</th><th>Pathway Name</th><th>Content Name</th><th>Entry Date</th><th>Question</th><th>Answer Text</th><th>Answer Value</th></tr></table>'
        '<div style="margin-top:8px;font-size:11px;color:#64748B;">Example file name: <span>data.csv</span></div>'
        '</div>'
        + status_block + '</div>',
        unsafe_allow_html=True,
    )
    st.file_uploader(
        "Patient answers file",
        type=["csv", "xlsx"],
        key="secondary_file",
        label_visibility="collapsed",
    )

with col3:
    card_cls = "upload-card done" if demographics_done else "upload-card"
    if demographics_done:
        fname = st.session_state["demographics_file"].name
        status_block = (
            '<div class="upload-status">'
            '<div class="upload-status-dot"></div>'
            '<div class="upload-status-text">' + fname + ' — uploaded</div>'
            '</div>'
        )
    else:
        status_block = ""
    st.markdown(
        '<div class="' + card_cls + '">'
        '<div class="upload-card-file-label">File 3 of 3 (optional)</div>'
        '<div class="upload-card-title">Patient metadata / enrichment file</div>'
        '<div class="upload-card-desc">Optional file with extra patient or pathway-level columns. It merges by Patient ID and Pathway Name when available.</div>'
        '<div class="upload-card-example">'
        '<div class="workflow-example-label">Source columns</div>'
        '<table class="mini-table"><tr><th>Patient ID</th><th>Pathway Name</th><th>Age</th><th>Sex</th><th>Other fields</th></tr></table>'
        '<div style="margin-top:8px;font-size:11px;color:#64748B;">Optional file name: <span>metadata.csv</span></div>'
        '</div>'
        + status_block + '</div>',
        unsafe_allow_html=True,
    )
    st.file_uploader(
        "Patient metadata / enrichment file",
        type=["csv", "xlsx"],
        key="demographics_file",
        label_visibility="collapsed",
    )

st.markdown('<div class="spacer"></div>', unsafe_allow_html=True)

# ── STEP 2 — Questionnaire type ───────────────────────────────────────────────
step2_num_cls = "" if required_done else "pending"
st.markdown(
    f"""
    <div class="phase-header">
        <div class="phase-num {step2_num_cls}">2</div>
        <div>
            <p class="phase-title">Step 2 — What kind of questionnaire is this?</p>
            <p class="phase-hint">Choose the option that matches how your patients filled it in</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

wf_col1, wf_col2 = st.columns(2)

with wf_col1:
    st.markdown(
        """
        <div class="workflow-card" id="wf-normal">
            <div class="workflow-card-title">Filled in once</div>
            <div class="workflow-card-subtitle">
                Each patient completed this questionnaire a single time —
                for example, an intake form or a one-off assessment.
            </div>
            <div class="workflow-example-label">Your output will look like this</div>
            <table class="mini-table">
                <tr><th>Patient</th><th>Date</th><th>Weight</th><th>BMI</th></tr>
                <tr><td>P001</td><td>Jan 10</td><td>70</td><td>22.1</td></tr>
                <tr><td>P002</td><td>Jan 15</td><td>65</td><td>21.0</td></tr>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )

with wf_col2:
    st.markdown(
        """
        <div class="workflow-card">
            <div class="workflow-card-title">Filled in repeatedly</div>
            <div class="workflow-card-subtitle">
                Each patient completed this questionnaire multiple times —
                for example, a weekly check-in or a follow-up at every visit.
            </div>
            <div class="workflow-example-label">Your output will look like this</div>
            <table class="mini-table green">
                <tr><th>Patient</th><th>Weight 1</th><th>Weight 2</th><th>BMI 1</th><th>BMI 2</th></tr>
                <tr><td>P001</td><td>70</td><td>72</td><td>22.1</td><td>22.8</td></tr>
                <tr><td>P002</td><td>65</td><td>—</td><td>21.0</td><td>—</td></tr>
            </table>
        </div>
        """,
        unsafe_allow_html=True,
    )

workflow = st.radio(
    "Questionnaire type",
    options=["normal", "iterative"],
    format_func=lambda x: {
        "normal":    "Filled in once — one row per questionnaire event, dates included",
        "iterative": "Filled in repeatedly — one row per patient, answers shown as Visit 1, Visit 2 …",
    }[x],
    label_visibility="collapsed",
)

st.markdown('<div class="spacer"></div>', unsafe_allow_html=True)

# ── STEP 3 — Generate ──────────────────────────────────────────────────────────
step3_num_cls = "" if required_done else "pending"
st.markdown(
    f"""
    <div class="phase-header">
        <div class="phase-num {step3_num_cls}">3</div>
        <div>
            <p class="phase-title">Step 3 — Generate your file</p>
            <p class="phase-hint">This usually takes a few seconds. A ready-to-open Excel file will be downloaded.</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if required_done:
    if st.button("▶  Generate transformed file"):
        try:
            with st.spinner("Processing your data…"):
                result_df = process_files(
                    st.session_state["primary_file"],
                    st.session_state["secondary_file"],
                    workflow=workflow,
                    demographics_file=st.session_state.get("demographics_file"),
                )

            display_df = result_df.copy()
            display_df = display_df.astype(object).where(result_df.notna(), "")
            display_df = display_df.astype(str)

            n_patients = result_df["Patient ID"].nunique() if "Patient ID" in result_df.columns else len(result_df)
            n_cols     = len(result_df.columns)

            st.markdown(
                f"""
                <div class="status-box">
                    <strong>Your file is ready.</strong><br>
                    {n_patients} patients &nbsp;·&nbsp; {n_cols} columns of data
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown('<div class="section-label" style="font-size:10px;font-weight:700;color:#94A3B8;text-transform:uppercase;letter-spacing:.07em;margin-bottom:8px;">Preview — first rows of your output</div>', unsafe_allow_html=True)
            st.dataframe(display_df, width='stretch', height=380)

            csv_data = result_df.to_csv(index=False).encode("utf-8-sig")

            st.markdown('<div class="spacer"></div>', unsafe_allow_html=True)
            st.download_button(
                label="⬇  Download your Excel-ready file (.csv)",
                data=csv_data,
                file_name="patient_data_transformed.csv",
                mime="text/csv",
            )

        except Exception as e:
            st.error(
                f"Something went wrong while processing your files. "
                f"Please check that you uploaded the correct files and try again.\n\n"
                f"Technical detail: {e}"
            )
else:
    st.button("▶  Generate transformed file", disabled=True)
    missing = []
    if not primary_done:
        missing.append("the questions & schedule file")
    if not secondary_done:
        missing.append("the patient answers file")
    st.markdown(
        f'<div class="notice">Please upload {" and ".join(missing)} above to continue</div>',
        unsafe_allow_html=True,
    )

# ── Reassurance footer ─────────────────────────────────────────────────────────
st.markdown(
    """
    <div class="reassurance">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" style="flex-shrink:0;margin-top:1px;">
            <circle cx="9" cy="9" r="7.5" stroke="#94A3B8" stroke-width="1.2"/>
            <line x1="9" y1="8" x2="9" y2="13" stroke="#94A3B8" stroke-width="1.4" stroke-linecap="round"/>
            <circle cx="9" cy="5.5" r="0.9" fill="#94A3B8"/>
        </svg>
        <p>
            <strong>Your data is not stored.</strong>
            Files are processed in memory only and discarded as soon as the transformation
            is complete. Nothing is saved to any server.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

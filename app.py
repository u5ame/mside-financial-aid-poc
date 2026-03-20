import json
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from services.pipeline import (
    build_case_summary_with_ai,
    build_openai_client,
    process_document_with_ai,
)

load_dotenv()

st.set_page_config(page_title="Financial Aid Document Processing Assistant", layout="wide")

# Morningside brand colors
MAROON = "#350609"
MAROON_LIGHT = "#4a1a1e"
MAROON_LIGHTER = "#5e2e32"
ACCENT = "#0073CE"

st.markdown(
    """
    <style>
    .stApp {
        background-color: #350609;
        color: #ffffff;
    }

    .block-container {
        max-width: 1060px;
        padding-top: 2rem;
    }

    h1, h2, h3, h4, h5, h6, p, span, label, .stMarkdown,
    [data-testid="stText"], [data-testid="stCaption"] {
        color: #ffffff !important;
    }

    .stCaption, caption {
        color: #d4c5c6 !important;
    }

    header[data-testid="stHeader"] {
        background-color: #350609 !important;
    }

    input, textarea, [data-baseweb="select"] {
        background-color: #4a1a1e !important;
        color: #ffffff !important;
        border-color: #5e2e32 !important;
    }

    [data-baseweb="select"] * {
        color: #ffffff !important;
    }

    [data-baseweb="select"] div {
        background-color: transparent !important;
    }

    [data-baseweb="select"] input {
        background-color: transparent !important;
    }

    [data-baseweb="select"] > div {
        padding-left: 10px !important;
        overflow: visible !important;
        border-color: #5e2e32 !important;
    }

    div[data-baseweb="popover"] {
        background-color: #4a1a1e !important;
    }

    div[data-baseweb="popover"] li {
        color: #ffffff !important;
    }

    div[data-baseweb="popover"] li:hover {
        background-color: #5e2e32 !important;
    }

    .stButton > button[kind="primary"],
    button[data-testid="stBaseButton-primary"] {
        background-color: #0073CE !important;
        color: #ffffff !important;
        border: none !important;
        font-weight: 700 !important;
    }

    .stButton > button[kind="primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover {
        background-color: #005fa3 !important;
    }

    .stButton > button {
        background-color: #5e2e32 !important;
        color: #ffffff !important;
        border: 1px solid #ffffff30 !important;
    }

    .stButton > button:hover {
        background-color: #7a4246 !important;
    }

    [data-testid="stExpander"] {
        border: 1px solid #ffffff20 !important;
        border-radius: 8px !important;
        background: #4a1a1e !important;
    }

    [data-testid="stExpander"] summary p {
        color: #ffffff !important;
        font-weight: 700 !important;
    }

    [data-testid="stDataFrame"] {
        border: 1px solid #ffffff20 !important;
        border-radius: 8px !important;
    }

    hr {
        border-color: #ffffff20 !important;
    }

    [data-testid="stInfo"] {
        background: #4a1a1e !important;
        border: 1px solid #ffffff20 !important;
    }

    [data-testid="stMarkdownContainer"] a {
        color: #0073CE !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🎓 Morningside Financial Aid Document Processing Assistant (Prototype)")
st.caption("AI-first intake triage for Morningside University financial aid workflows")

tab_tool, tab_architecture = st.tabs(["📄 Document Processing Tool", "🏗️ Architecture — POC vs Production"])

client = build_openai_client()
if client is None:
    st.error(
        "OPENAI_API_KEY is required for this AI-first version. Add it to `.env`, then restart Streamlit."
    )
    st.stop()

OCR_MODE = "always"


class LocalUpload:
    def __init__(self, path: Path):
        self.path = path
        self.name = path.name

    def getvalue(self) -> bytes:
        return self.path.read_bytes()


def get_sample_packages() -> Dict[str, Path]:
    root = Path(__file__).resolve().parent / "sample_data" / "student_packages"
    if not root.exists():
        return {}
    packages = {}
    for package_dir in sorted(root.iterdir()):
        if package_dir.is_dir():
            label = package_dir.name.replace("_", " ").title()
            packages[label] = package_dir
    return packages


def load_package_manifest(package_dir: Path) -> Dict[str, Any]:
    manifest_path = package_dir / "manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_sample_package_options() -> Dict[str, Dict[str, Any]]:
    options: Dict[str, Dict[str, Any]] = {}
    for base_label, package_dir in get_sample_packages().items():
        manifest = load_package_manifest(package_dir)
        catches = manifest.get("expected_catches", [])
        catch_descriptions: List[str] = []
        for item in catches:
            if not isinstance(item, dict):
                continue
            desc = str(item.get("description", "")).strip()
            if not desc:
                continue
            desc = desc.replace("AI should flag", "").replace("AI should", "").strip()
            if desc.lower().startswith("that "):
                desc = desc[5:].strip()
            if desc:
                desc = desc[0].upper() + desc[1:]
            desc = desc.rstrip(".")
            catch_descriptions.append(desc)

        expected_text = "; ".join(catch_descriptions) if catch_descriptions else "General intake gaps"
        display_label = f"{base_label} — Expected catches: {expected_text}"
        options[display_label] = {"path": package_dir, "manifest": manifest, "base_label": base_label}
    return options


sample_option_map = get_sample_package_options()
sample_options = ["None"] + list(sample_option_map.keys())

with tab_tool:
    with st.expander("POC Context", expanded=True):
        st.markdown(
            "We have created three student document packages to demonstrate the AI-assisted intake process."
            "AI classifies each document, extracts key fields, and flags likely missing or unclear items."
        )
        st.markdown("**Documents in every package and what AI checks**")

        any_manifest = next(
            (value.get("manifest") for value in sample_option_map.values() if value.get("manifest")),
            {},
        )
        docs = any_manifest.get("documents", []) if isinstance(any_manifest, dict) else []
        if docs:
            for d in docs:
                st.markdown(
                    f"- `{d.get('file', '')}` ({d.get('document_type', '')}): {d.get('purpose', '')}"
                )
        else:
            st.markdown("- FAFSA Confirmation: SAI/school-code routing and basic enrollment context")
            st.markdown("- Income Verification Form: household size, tax-year, wages, and income fields")
            st.markdown("- Tax Return: AGI/tax-year support and transcript completeness signals")
            st.markdown("- Iowa Financial Aid Application: residency and state-aid support details")
            st.markdown("- SAP Appeal Documentation: GPA/credits and support-document readiness")

    st.header("1) Upload Document Packet")
    selected_sample = st.selectbox(
        "Optional: preload a sample student package",
        options=sample_options,
        index=0,
    )

    uploads = st.file_uploader(
        "Upload student packet (PDFs)",
        accept_multiple_files=True,
        type=["pdf"],
    )

    has_input = bool(uploads) or selected_sample != "None"
    if st.button("Process Packet", type="primary", disabled=not has_input):
        input_files: List[Any] = []
        if selected_sample != "None":
            package_dir = sample_option_map[selected_sample]["path"]
            package_files = sorted(package_dir.glob("*.pdf"))
            input_files.extend(LocalUpload(path) for path in package_files)
        if uploads:
            input_files.extend(uploads)

        records: List[Dict[str, Any]] = []
        progress_line = st.empty()
        with st.spinner("Running OCR + AI analysis..."):
            total_docs = len(input_files)
            for idx, file_obj in enumerate(input_files, start=1):
                doc_id = f"DOC-{idx:03d}"
                progress_line.markdown(
                    f"`Step {idx}/{total_docs}: Processing {doc_id} (OCR -> classification -> extraction)`"
                )
                record = process_document_with_ai(
                    file_obj=file_obj,
                    client=client,
                    doc_id=doc_id,
                    ocr_mode=OCR_MODE,
                )
                records.append(record)
            progress_line.markdown("`Final step: Building case summary and follow-up actions`")

        case_summary = build_case_summary_with_ai(records=records, client=client)
        progress_line.empty()
        st.session_state["records"] = records
        st.session_state["case_summary"] = case_summary
        st.success(f"Processed {len(records)} document(s).")

    records = st.session_state.get("records", [])
    case_summary = st.session_state.get("case_summary", {})

    if records:
        st.header("2) Advisor Queue View")
        queue_rows = []
        for r in records:
            signature = r["extraction"].get("signature_status", "unclear")
            if signature == "present":
                review_status = "Ready for field review"
            elif signature == "missing":
                review_status = "Needs signature follow-up"
            else:
                review_status = "Signature verification needed"

            queue_rows.append(
                {
                    "Document ID": r["doc_id"],
                    "Document Type": r["classification"]["document_type"],
                    "Signature": signature.title(),
                    "Review Status": review_status,
                }
            )

        st.dataframe(pd.DataFrame(queue_rows), use_container_width=True, hide_index=True)

        with st.expander("Original filenames (hidden in main workflow to avoid bias)", expanded=False):
            name_rows = [{"Document ID": r["doc_id"], "Original Filename": r["filename"]} for r in records]
            st.dataframe(pd.DataFrame(name_rows), use_container_width=True, hide_index=True)

        st.header("3) Per-Document Review Cards")
        for r in records:
            ext = r["extraction"]
            with st.container(border=True):
                st.subheader(f"{r['doc_id']} - {r['classification']['document_type']}")
                st.write(f"**Student:** {ext.get('student_name') or 'Unknown'}")
                st.write(f"**Signature:** {ext.get('signature_status', 'unclear').title()}")

                key_fields = {
                    "Household Income": ext.get("household_income"),
                    "Tax Year": ext.get("tax_year"),
                    "Tax Page Indicator": ext.get("tax_page_indicator"),
                    "Household Size": ext.get("household_size"),
                    "Enrollment Status": ext.get("enrollment_status"),
                    "Residency": ext.get("residency"),
                    "Residency Evidence": ext.get("residency_evidence"),
                    "GPA": ext.get("gpa"),
                    "Attempted Credits": ext.get("attempted_credits"),
                    "Earned Credits": ext.get("earned_credits"),
                    "Third-Party Documentation": ext.get("third_party_documentation"),
                    "Advisor Plan Status": ext.get("advisor_plan_status"),
                }
                visible_fields = {k: v for k, v in key_fields.items() if v not in (None, "", "null")}
                if visible_fields:
                    st.write("**Extracted fields:**")
                    st.dataframe(
                        pd.DataFrame(
                            [{"Field": k, "Value": v} for k, v in visible_fields.items()]
                        ),
                        use_container_width=True,
                        hide_index=True,
                    )

                missing_items = ext.get("missing_items", [])
                advisor_notes = ext.get("advisor_notes", [])
                combined_highlights: List[str] = []
                combined_highlights.extend([str(item).strip() for item in missing_items if str(item).strip()])
                combined_highlights.extend([str(note).strip() for note in advisor_notes if str(note).strip()])

                if combined_highlights:
                    unique_highlights: List[str] = []
                    seen = set()
                    for text in combined_highlights:
                        key = text.lower()
                        if key in seen:
                            continue
                        seen.add(key)
                        unique_highlights.append(text)

                    with st.container(border=True):
                        st.markdown("**Review highlights**")
                        st.markdown(
                            "\n".join([f"- {item}" for item in unique_highlights])
                        )

        st.header("4) Case Summary and Follow-up")
        overall_status = case_summary.get("overall_status", "needs_follow_up")
        if overall_status == "ready_for_review":
            st.success(f"Case status: {overall_status}")
        elif overall_status == "incomplete_packet":
            st.error(f"Case status: {overall_status}")
        else:
            st.warning(f"Case status: {overall_status}")
        with st.container(border=True):
            st.subheader("Intake Findings and Recommended Actions")
            findings_col, actions_col = st.columns(2)
            with findings_col:
                st.markdown("**What was found**")
                findings = case_summary.get("priority_issues", [])
                if findings:
                    for item in findings:
                        st.markdown(f"- {item}")
                else:
                    st.markdown("- No high-priority findings.")
            with actions_col:
                st.markdown("**Recommended actions**")
                actions = case_summary.get("follow_up_actions", [])
                if actions:
                    for action in actions:
                        st.markdown(f"- {action}")
                else:
                    st.markdown("- No additional actions recommended.")

        st.header("5) Draft Response Email (Staff Review Required)")
        default_email = (
            f"Subject: {case_summary.get('draft_email_subject', 'Additional Information Needed for Financial Aid File')}\n\n"
            f"{case_summary.get('draft_email_body', '')}"
        ).strip()
        edited = st.text_area("Draft Email", value=default_email, height=300)
        st.download_button(
            "Download Draft Email",
            data=edited,
            file_name="financial_aid_draft_email.txt",
            mime="text/plain",
        )

with tab_architecture:
    st.divider()

    st.header("How This Prototype Works")
    st.markdown(
        """
    In this POC, the AI handles every step of document intake. Each uploaded PDF
    is rendered to images, OCR'd via OpenAI Vision, then classified and field-extracted
    by a single LLM call. A final LLM call summarizes the full case and drafts a
    follow-up email. There are no rule-based checks — the AI operates end-to-end.
    """
    )

    st.markdown(
        """
    <div style="background:#4a1a1e;border-radius:10px;padding:1.5rem;
                border:1px solid #ffffff15;margin:0.5rem 0 1.5rem 0;">
    <div style="text-align:center;font-size:0.95rem;line-height:2.2;">
    <span style="background:#0073CE;padding:6px 14px;border-radius:6px;font-weight:700;">
    Uploaded PDFs (scanned forms)</span>
    <br>
    <span style="font-size:1.4rem;">⬇</span><br>
    <span style="background:#b8860b;padding:6px 14px;border-radius:6px;font-weight:700;">
    🤖 OCR via OpenAI Vision — render pages to images, extract text</span>
    <br>
    <span style="font-size:1.4rem;">⬇</span><br>
    <span style="background:#b8860b;padding:6px 14px;border-radius:6px;font-weight:700;">
    🤖 LLM — classify document type + extract all key fields</span>
    <br>
    <span style="font-size:1.4rem;">⬇</span><br>
    <span style="background:#b8860b;padding:6px 14px;border-radius:6px;font-weight:700;">
    🤖 LLM — build case summary, flag gaps, draft follow-up email</span>
    <br>
    <span style="font-size:1.4rem;">⬇</span><br>
    <span style="background:#1b5e20;padding:6px 14px;border-radius:6px;font-weight:700;">
    Advisor Review & Decision</span>
    </div></div>
    """,
        unsafe_allow_html=True,
    )
    st.markdown("**Strengths of this approach (for a POC):**")
    st.markdown(
        """
    - Fast to build — no form templates, no field-mapping rules to write.
    - Demonstrates the full intake experience: upload → triage → email in one flow.
    - The AI naturally handles varied document formats without per-form configuration.
    - Soft judgments (e.g. "is this signature present or unclear?") are well-suited to LLMs.
    """
    )

    st.markdown("**Limitations that would matter in production:**")
    st.markdown(
        """
    - No correctness guarantee. The LLM may misread OCR'd text, hallucinate field
      values, or miss items it should flag.
    - No validation layer. AI output is displayed as-is — there's no programmatic
      cross-check against known form structures.
    - Cost & latency. Every page is rendered, OCR'd, and analyzed via API calls.
      A 20-page packet can take 30–60 seconds and cost several dollars, which is not efficient.
    - Non-deterministic. The same document can produce slightly different extractions
      on each run, making audits difficult.
    - No integration. Student data isn't cross-referenced with SIS, FAFSA databases,
      or institutional records.
    """
    )

    st.divider()

    st.header("🏗️ Recommended Production Architecture")
    st.markdown(
        """
    In a production system, the work is split between deterministic rules and AI —
    each handling what it does best. Rules enforce known form structures and
    business logic; AI handles ambiguity, unstructured content, and natural-language
    communication.
    """
    )

    st.markdown(
        """
    <div style="background:#4a1a1e;border-radius:10px;padding:1.5rem;
                border:1px solid #ffffff15;margin:0.5rem 0 1.5rem 0;">
    <div style="text-align:center;font-size:0.95rem;line-height:2.2;">
    <span style="background:#0073CE;padding:6px 14px;border-radius:6px;font-weight:700;">
    Uploaded PDFs</span>
    <br>
    <span style="font-size:1.4rem;">⬇</span><br>
    <span style="background:#5e2e32;padding:8px 14px;border-radius:6px;font-weight:700;
          border:2px solid #ffffff40;">
    🗄️ Layer 1 — Ingestion &amp; Pre-Processing (deterministic)</span>
    <br>
    <span style="color:#d4c5c6;font-size:0.8rem;">Native text extraction · OCR for scanned pages ·
    Barcode / QR detection · Form-template matching · Page splitting</span>
    <br>
    <span style="font-size:1.4rem;">⬇</span><br>
    <span style="background:#5e2e32;padding:8px 14px;border-radius:6px;font-weight:700;
          border:2px solid #ffffff40;">
    📋 Layer 2 — Rule-Based Classification &amp; Extraction</span>
    <br>
    <span style="color:#d4c5c6;font-size:0.8rem;">Template matching for known forms (1040, FAFSA, state apps) ·
    Regex extraction for SSN, EFC, AGI · Required-field checklists per form type</span>
    <br>
    <span style="font-size:1.4rem;">⬇</span>
    <span style="color:#d4c5c6;font-size:0.8rem;">&nbsp; unrecognized or ambiguous documents</span>
    <br>
    <span style="background:#b8860b;padding:8px 14px;border-radius:6px;font-weight:700;
          border:2px solid #ffffff40;">
    🤖 Layer 3 — AI Analysis (LLM)</span>
    <br>
    <span style="color:#d4c5c6;font-size:0.8rem;">Classify unknown documents · Extract fields from unstructured text ·
    Infer signature status · Detect anomalies &amp; inconsistencies · Draft advisor notes</span>
    <br>
    <span style="font-size:1.4rem;">⬇</span><br>
    <span style="background:#5e2e32;padding:8px 14px;border-radius:6px;font-weight:700;
          border:2px solid #ffffff40;">
    ✅ Layer 4 — Validation &amp; Cross-Reference</span>
    <br>
    <span style="color:#d4c5c6;font-size:0.8rem;">Cross-check AI output against SIS/ISIR data ·
    Verify completeness per federal checklist · Flag discrepancies · Audit logging</span>
    <br>
    <span style="font-size:1.4rem;">⬇</span><br>
    <span style="background:#b8860b;padding:8px 14px;border-radius:6px;font-weight:700;
          border:2px solid #ffffff40;">
    🤖 Layer 5 — AI Case Summary &amp; Communication</span>
    <br>
    <span style="color:#d4c5c6;font-size:0.8rem;">Synthesize findings into advisor briefing ·
    Generate student-facing follow-up email · Priority ranking</span>
    <br>
    <span style="font-size:1.4rem;">⬇</span><br>
    <span style="background:#1b5e20;padding:6px 14px;border-radius:6px;font-weight:700;">
    Advisor Review &amp; Decision</span>
    </div></div>
    """,
        unsafe_allow_html=True,
    )

    st.divider()

    st.header("Layer-by-Layer Breakdown")

    st.subheader("Layer 1 — Ingestion & Pre-Processing")
    st.markdown(
        """
    Pure code, no AI. Standard document ingestion that normalizes input before
    any analysis begins.
    """
    )
    st.markdown(
        """
    - Extract native text from digital PDFs (fast, free, accurate).
    - Run OCR only on scanned/image-based pages — skip it when native text is available.
    - Detect barcodes or QR codes embedded in standardized forms (e.g. IRS transcripts).
    - Split multi-document uploads into individual forms by page breaks or separator sheets.
    - Normalize page orientation, DPI, and image quality before downstream processing.
    """
    )

    st.subheader("Layer 2 — Rule-Based Classification & Extraction")
    st.markdown(
        """
    Deterministic logic for known form types. Financial aid offices work with a finite
    set of recurring forms — these can be handled with high accuracy using templates and rules.
    """
    )
    st.code(
        '''KNOWN_FORMS = {
    "1040":   {"markers": ["Form 1040", "Department of the Treasury"],
               "fields": ["AGI", "filing_status", "tax_year"]},
    "FAFSA":  {"markers": ["FAFSA", "Student Aid Index"],
               "fields": ["SAI", "school_code", "dependency_status"]},
    "W-2":    {"markers": ["Wage and Tax Statement"],
               "fields": ["employer", "wages", "federal_tax_withheld"]},
}

def classify_by_template(text: str) -> str | None:
    """Return form type if known markers are found, else None."""
    for form_type, spec in KNOWN_FORMS.items():
        if all(marker.lower() in text.lower() for marker in spec["markers"]):
            return form_type
    return None  # hand off to AI for unknown documents''',
        language="python",
    )
    st.markdown(
        """
    - Known forms (FAFSA, 1040, W-2, state applications) are classified instantly
      by matching header text or form identifiers.
    - Key fields are extracted with targeted regex or positional rules
    - Required-field checklists per form type flag missing data immediately,
      without needing an LLM.
    - Documents not matching any template are forwarded to the AI layer.
    """
    )

    st.subheader("Layer 3 — AI Analysis")
    st.markdown(
        """
    The LLM handles what rules cannot: ambiguous documents, unstructured text,
    and soft judgments.
    """
    )
    st.markdown(
        """
    | Task | Who does it | Why |
    |---|---|---|
    | Classify known forms (FAFSA, 1040, W-2) | **Rules** | Deterministic — AI adds no value |
    | Classify unknown or atypical documents | **AI** | Requires reading comprehension |
    | Extract AGI from line 11 of a 1040 | **Rules** | Fixed position, regex-reliable |
    | Extract data from free-form letters | **AI** | Unstructured text, variable layouts |
    | Check if page 2 of a tax return is present | **Rules** | Page count is deterministic |
    | Infer if a signature is present or smudged | **AI** | Visual judgment call |
    | Detect inconsistencies across documents | **AI** | Cross-document reasoning |
    """
    )
    st.markdown(
        """
    Because the AI only processes documents that rules couldn't handle — typically
    20–30% of a packet — API costs drop significantly and latency improves.
    """
    )

    st.subheader("Layer 4 — Validation & Cross-Reference")
    st.markdown(
        """
    Programmatic verification before anything reaches the advisor. This layer
    catches AI mistakes and enriches findings with institutional data.
    """
    )
    st.markdown(
        """
    - Cross-reference extracted student name and ID against the Student Information System (SIS).
    - Compare FAFSA SAI against the ISIR (Institutional Student Information Record) on file.
    - Verify that every document required by the federal verification checklist is present.
    - Flag discrepancies: e.g. tax year on the 1040 doesn't match the verification year.
    - Write every classification, extraction, and flag to an audit log for compliance.
    """
    )

    st.subheader("Layer 5 — AI Case Summary & Communication")
    st.markdown(
        """
    After validation, the AI synthesizes the full picture into advisor-ready output:
    """
    )
    st.markdown(
        """
    - Produce a concise case briefing: what's complete, what's missing, what's suspect.
    - Rank issues by priority (missing signature > unclear residency > minor formatting).
    - Draft a student-facing email listing exactly what needs to be submitted.
    - Adapt tone and language to institutional communication standards.
    """
    )

    st.divider()

    st.header("Side-by-Side Comparison")
    col_poc, col_prod = st.columns(2)
    with col_poc:
        st.markdown("**This Prototype (POC)**")
        st.markdown(
            """
        | Aspect | Detail |
        |---|---|
        | Document classification | LLM classifies every document |
        | Field extraction | LLM extracts all fields |
        | OCR | Every page, every time |
        | Missing-item detection | LLM infers gaps |
        | Validation | None — AI output shown as-is |
        | Data cross-reference | None |
        | Cost per packet | ~$0.50–$2.00 (5 docs, OCR + analysis) |
        | Latency | 30–60 seconds |
        | Auditability | None |
        | Time to build | Days |
        """
        )
    with col_prod:
        st.markdown("**Production System**")
        st.markdown(
            """
        | Aspect | Detail |
        |---|---|
        | Document classification | Rules for known forms, AI for unknowns |
        | Field extraction | Rules for structured fields, AI for free text |
        | OCR | Only scanned pages (skip native text) |
        | Missing-item detection | Checklist rules + AI for edge cases |
        | Validation | Programmatic re-check of all outputs |
        | Data cross-reference | SIS, ISIR, federal databases |
        | Cost per packet | ~$0.05–$0.20 (AI only for unknowns) |
        | Latency | 2–5 seconds |
        | Auditability | Full decision log |
        | Time to build | Months |
        """
        )

    st.divider()
    st.caption(
        "This architecture comparison is provided as part of the proof-of-concept to "
        "illustrate the path from prototype to production-ready system."
    )


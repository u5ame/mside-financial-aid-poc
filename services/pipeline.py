import base64
import io
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber

try:
    import fitz
except Exception:
    fitz = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


MORNINGSIDE_DEADLINES = {
    "FAFSA Submission Grant": "Submit FAFSA to Morningside by Feb 28.",
    "All Iowa Opportunity Scholarship": "Submit FAFSA and Iowa application by Apr 1.",
    "Iowa Tuition Grant / State Aid": "Submit FAFSA by Jul 1.",
}


DOC_TYPES = [
    "FAFSA Confirmation",
    "Income Verification Form",
    "Tax Return",
    "Iowa Financial Aid Application",
    "SAP Appeal Documentation",
    "Outside Scholarship Notice",
    "Loan Counseling/MPN Confirmation",
    "Scholarship Application",
    "Other",
]

REQUIRED_FIELDS_BY_DOC = {
    "FAFSA Confirmation": ["student_name", "enrollment_status", "residency"],
    "Income Verification Form": ["student_name", "tax_year", "household_income", "household_size"],
    "Tax Return": ["student_name", "tax_year", "household_income"],
    "Iowa Financial Aid Application": ["student_name", "residency"],
    "SAP Appeal Documentation": ["student_name", "gpa", "attempted_credits", "earned_credits"],
    "Outside Scholarship Notice": ["student_name"],
    "Loan Counseling/MPN Confirmation": ["student_name"],
    "Scholarship Application": ["student_name"],
    "Other": [],
}


def build_openai_client() -> Optional[Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or OpenAI is None:
        return None
    return OpenAI(api_key=api_key)


def process_document_with_ai(
    file_obj: Any,
    client: Any,
    doc_id: str,
    ocr_mode: str = "always",
) -> Dict[str, Any]:
    raw = file_obj.getvalue()
    suffix = Path(file_obj.name).suffix.lower()

    native_text = ""
    page_images: List[str] = []
    if suffix == ".pdf":
        native_text = _extract_native_pdf_text(raw)
        page_images = _render_pdf_pages_to_base64(raw, max_pages=6)
    else:
        try:
            native_text = raw.decode("utf-8", errors="ignore").strip()
        except Exception:
            native_text = ""

    ocr_attempted = bool(page_images and ocr_mode in {"always", "auto"})
    ocr_text = ""
    if page_images and ocr_mode == "always":
        ocr_text = _run_ocr_on_images(client, page_images)
    elif page_images and ocr_mode == "auto" and len(native_text.strip()) < 250:
        ocr_text = _run_ocr_on_images(client, page_images)

    analysis = _analyze_document(
        client=client,
        native_text=native_text,
        ocr_text=ocr_text,
        page_images=page_images,
    )
    normalized = _normalize_document_analysis(analysis)

    return {
        "doc_id": doc_id,
        "filename": file_obj.name,
        "classification": {
            "document_type": normalized.get("document_type", "Other"),
            "confidence": float(normalized.get("document_type_confidence", 0.0)),
            "method": "ai",
        },
        "extraction": {
            "student_name": normalized.get("student_name"),
            "household_income": normalized.get("household_income"),
            "tax_year": normalized.get("tax_year"),
            "tax_page_indicator": normalized.get("tax_page_indicator"),
            "household_size": normalized.get("household_size"),
            "enrollment_status": normalized.get("enrollment_status"),
            "residency": normalized.get("residency"),
            "gpa": normalized.get("gpa"),
            "attempted_credits": normalized.get("attempted_credits"),
            "earned_credits": normalized.get("earned_credits"),
            "tax_doc_completeness": normalized.get("tax_doc_completeness"),
            "residency_evidence": normalized.get("residency_evidence"),
            "third_party_documentation": normalized.get("third_party_documentation"),
            "advisor_plan_status": normalized.get("advisor_plan_status"),
            "signature_status": normalized.get("signature_status", "unclear"),
            "signature_confidence": float(normalized.get("signature_confidence", 0.0)),
            "missing_items": normalized.get("missing_items", []),
            "advisor_notes": normalized.get("advisor_notes", []),
            "method": "ai",
        },
        "processing_trace": {
            "native_text_chars": len(native_text),
            "ocr_text_chars": len(ocr_text),
            "ocr_attempted": ocr_attempted,
            "ocr_used": bool(ocr_text.strip()),
        },
    }


def build_case_summary_with_ai(records: List[Dict[str, Any]], client: Any) -> Dict[str, Any]:
    brief = []
    for r in records:
        ext = r["extraction"]
        brief.append(
            {
                "doc_id": r["doc_id"],
                "document_type": r["classification"]["document_type"],
                "student_name": ext.get("student_name"),
                "signature_status": ext.get("signature_status"),
                "missing_items": ext.get("missing_items", []),
                "advisor_notes": ext.get("advisor_notes", []),
                "key_fields": {
                    "household_income": ext.get("household_income"),
                    "tax_year": ext.get("tax_year"),
                    "tax_page_indicator": ext.get("tax_page_indicator"),
                    "household_size": ext.get("household_size"),
                    "enrollment_status": ext.get("enrollment_status"),
                    "residency": ext.get("residency"),
                    "gpa": ext.get("gpa"),
                    "attempted_credits": ext.get("attempted_credits"),
                    "earned_credits": ext.get("earned_credits"),
                    "tax_doc_completeness": ext.get("tax_doc_completeness"),
                    "residency_evidence": ext.get("residency_evidence"),
                    "third_party_documentation": ext.get("third_party_documentation"),
                    "advisor_plan_status": ext.get("advisor_plan_status"),
                },
            }
        )

    prompt = (
        "You are supporting Morningside University's Office of Student Financial Planning. "
        "Given document-level AI extraction outputs, produce case-level intake summary.\n\n"
        "Return strict JSON with keys:\n"
        "{\n"
        '  "student_name": string|null,\n'
        '  "overall_status": "ready_for_review" | "needs_follow_up" | "incomplete_packet",\n'
        '  "priority_issues": [string],\n'
        '  "follow_up_actions": [string],\n'
        '  "draft_email_subject": string,\n'
        '  "draft_email_body": string\n'
        "}\n\n"
        "Keep tone professional and non-decisional. Do not make aid eligibility decisions.\n\n"
        f"Document summaries JSON:\n{json.dumps(brief, ensure_ascii=True)}"
    )
    result = _call_json_model(
        client,
        prompt,
        model=os.getenv("OPENAI_SUMMARY_MODEL", os.getenv("OPENAI_ANALYSIS_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))),
    )
    if result:
        return _normalize_case_summary(result, records)

    fallback_name = next(
        (r["extraction"].get("student_name") for r in records if r["extraction"].get("student_name")),
        None,
    )
    fallback_issues = []
    for r in records:
        fallback_issues.extend(r["extraction"].get("missing_items", []))
        if r["extraction"].get("signature_status") in {"missing", "unclear"}:
            fallback_issues.append(
                f"{r['doc_id']}: Signature status is {r['extraction'].get('signature_status')} and requires review."
            )

    return {
        "student_name": fallback_name,
        "overall_status": "needs_follow_up" if fallback_issues else "ready_for_review",
        "priority_issues": fallback_issues[:10],
        "follow_up_actions": ["Staff review all flagged items before sending outreach."],
        "draft_email_subject": "Additional Information Needed for Financial Aid File",
        "draft_email_body": (
            f"Dear {fallback_name or 'Student'},\n\n"
            "Thank you for submitting your financial aid documents. During intake review, we identified items that may "
            "need clarification or additional documentation. Please review the Office of Student Financial Planning "
            "request and submit any updates at your earliest convenience.\n\n"
            "This message is a draft for staff review."
        ),
    }


def _extract_native_pdf_text(raw_pdf: bytes) -> str:
    try:
        pages: List[str] = []
        with pdfplumber.open(io.BytesIO(raw_pdf)) as pdf:
            for page in pdf.pages:
                pages.append(page.extract_text() or "")
        return "\n".join(pages).strip()
    except Exception:
        return ""


def _render_pdf_pages_to_base64(raw_pdf: bytes, max_pages: int = 6) -> List[str]:
    if fitz is None:
        return []
    try:
        pdf = fitz.open(stream=raw_pdf, filetype="pdf")
        images: List[str] = []
        for idx, page in enumerate(pdf):
            if idx >= max_pages:
                break
            pix = page.get_pixmap(matrix=fitz.Matrix(1.8, 1.8), alpha=False)
            images.append(base64.b64encode(pix.tobytes("png")).decode("ascii"))
        return images
    except Exception:
        return []


def _run_ocr_on_images(client: Any, page_images: List[str]) -> str:
    prompt = (
        "Perform OCR on all attached document pages. "
        "Return plain text only. Preserve key labels and values."
    )
    result = _call_json_model(
        client=client,
        prompt=(
            "Return strict JSON: {\"ocr_text\": \"...\"}. "
            + prompt
        ),
        images=page_images,
        model=os.getenv("OPENAI_OCR_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini")),
    )
    if result and isinstance(result.get("ocr_text"), str):
        return result["ocr_text"]
    return ""


def _analyze_document(
    client: Any,
    native_text: str,
    ocr_text: str,
    page_images: List[str],
) -> Dict[str, Any]:
    prompt = (
        "You are an AI intake assistant for Morningside University's Office of Student Financial Planning.\n"
        "Classify the document and extract useful intake fields.\n"
        "IMPORTANT:\n"
        "- Do NOT use filename-based assumptions.\n"
        "- If signatures are graphical/ink only, evaluate visually from the page images.\n"
        "- Signature status must be one of: present, missing, unclear.\n"
        "- Only extract values that are supported by evidence.\n\n"
        f"Allowed document_type values: {', '.join(DOC_TYPES)}\n\n"
        "Return strict JSON with keys:\n"
        "{\n"
        '  "document_type": string,\n'
        '  "document_type_confidence": number,\n'
        '  "student_name": string|null,\n'
        '  "household_income": string|null,\n'
        '  "tax_year": string|null,\n'
        '  "tax_page_indicator": string|null,\n'
        '  "household_size": string|null,\n'
        '  "enrollment_status": string|null,\n'
        '  "residency": string|null,\n'
        '  "gpa": string|null,\n'
        '  "attempted_credits": string|null,\n'
        '  "earned_credits": string|null,\n'
        '  "tax_doc_completeness": string|null,\n'
        '  "residency_evidence": string|null,\n'
        '  "third_party_documentation": string|null,\n'
        '  "advisor_plan_status": string|null,\n'
        '  "signature_status": "present"|"missing"|"unclear",\n'
        '  "signature_confidence": number,\n'
        '  "missing_items": [string],\n'
        '  "advisor_notes": [string]\n'
        "}\n\n"
        "Native extracted text:\n"
        f"{native_text[:12000]}\n\n"
        "OCR text:\n"
        f"{ocr_text[:12000]}"
    )
    result = _call_json_model(
        client=client,
        prompt=prompt,
        images=page_images,
        model=os.getenv("OPENAI_ANALYSIS_MODEL", os.getenv("OPENAI_MODEL", "gpt-4.1-mini")),
    )
    if not result:
        return {
            "document_type": "Other",
            "document_type_confidence": 0.0,
            "student_name": None,
            "household_income": None,
            "tax_year": None,
            "tax_page_indicator": None,
            "household_size": None,
            "enrollment_status": None,
            "residency": None,
            "gpa": None,
            "attempted_credits": None,
            "earned_credits": None,
            "tax_doc_completeness": None,
            "residency_evidence": None,
            "third_party_documentation": None,
            "advisor_plan_status": None,
            "signature_status": "unclear",
            "signature_confidence": 0.0,
            "missing_items": ["AI extraction failed to return structured output."],
            "advisor_notes": ["Retry processing or manually review this document."],
        }
    return result


def _normalize_document_analysis(analysis: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(analysis or {})
    doc_type = str(normalized.get("document_type") or "Other")
    if doc_type not in DOC_TYPES:
        doc_type = "Other"
    normalized["document_type"] = doc_type

    sig = str(normalized.get("signature_status") or "unclear").lower()
    sig_conf = float(normalized.get("signature_confidence") or 0.0)
    if sig not in {"present", "missing", "unclear"}:
        sig = "unclear"
    if sig in {"present", "missing"} and sig_conf < 0.85:
        sig = "unclear"
    normalized["signature_status"] = sig
    normalized["signature_confidence"] = sig_conf

    for key in [
        "student_name",
        "household_income",
        "tax_year",
        "tax_page_indicator",
        "household_size",
        "enrollment_status",
        "residency",
        "gpa",
        "attempted_credits",
        "earned_credits",
        "tax_doc_completeness",
        "residency_evidence",
        "third_party_documentation",
        "advisor_plan_status",
    ]:
        value = normalized.get(key)
        if isinstance(value, str):
            value = value.strip()
            if value.lower() in {"", "null", "none", "n/a", "unknown", "not provided"}:
                value = None
        normalized[key] = value

    ai_missing = normalized.get("missing_items", [])
    if not isinstance(ai_missing, list):
        ai_missing = []
    ai_missing = [str(item).strip() for item in ai_missing if str(item).strip()]

    filtered_ai_missing = [
        item
        for item in _filter_missing_items_for_doc(doc_type, ai_missing)
        if not _is_low_information_issue(item)
    ]
    required_gaps = _compute_required_field_gaps(doc_type, normalized)
    scenario_gaps = _compute_scenario_specific_gaps(doc_type, normalized)
    merged = _drop_subsumed_issues(_unique_preserve_order(required_gaps + scenario_gaps + filtered_ai_missing))
    normalized["missing_items"] = merged

    notes = normalized.get("advisor_notes", [])
    if not isinstance(notes, list):
        notes = []
    normalized["advisor_notes"] = _unique_preserve_order([str(n).strip() for n in notes if str(n).strip()])
    return normalized


def _compute_required_field_gaps(doc_type: str, data: Dict[str, Any]) -> List[str]:
    label_map = {
        "student_name": "student name",
        "household_income": "household income",
        "tax_year": "tax year",
        "household_size": "household size",
        "enrollment_status": "enrollment status",
        "residency": "residency",
        "gpa": "cumulative GPA",
        "attempted_credits": "attempted credits",
        "earned_credits": "earned credits",
    }
    gaps: List[str] = []
    for field in REQUIRED_FIELDS_BY_DOC.get(doc_type, []):
        if not data.get(field):
            gaps.append(f"Missing required field for {doc_type}: {label_map.get(field, field)}.")
    return gaps


def _compute_scenario_specific_gaps(doc_type: str, data: Dict[str, Any]) -> List[str]:
    gaps: List[str] = []
    tax_status = str(data.get("tax_doc_completeness") or "").lower()
    page_indicator = str(data.get("tax_page_indicator") or "").lower()
    if doc_type == "Tax Return":
        if "page 2 missing" in tax_status:
            gaps.append("Tax return transcript appears incomplete: page 2 is missing.")
        elif "1 of 2" in page_indicator or "page 1 of 2" in page_indicator:
            gaps.append("Tax return transcript appears incomplete: only page 1 of 2 is present.")

    residency_evidence = str(data.get("residency_evidence") or "").lower()
    if doc_type == "Iowa Financial Aid Application":
        if not residency_evidence:
            gaps.append("Iowa aid packet is missing residency evidence.")
        elif any(token in residency_evidence for token in ["not provided", "missing", "pending", "not submitted", "blank"]):
            gaps.append("Iowa aid packet is missing residency evidence.")

    sap_docs = str(data.get("third_party_documentation") or "").lower()
    advisor_plan = str(data.get("advisor_plan_status") or "").lower()
    if doc_type == "SAP Appeal Documentation":
        if not sap_docs or any(token in sap_docs for token in ["no", "missing", "not provided", "none", "pending"]):
            gaps.append("SAP appeal is missing required third-party documentation.")
        if any(token in advisor_plan for token in ["draft", "not filed", "pending"]):
            gaps.append("SAP appeal academic advisor plan is not finalized.")

    if data.get("signature_status") == "missing":
        gaps.append(f"{doc_type}: required signature appears missing.")
    elif data.get("signature_status") == "unclear":
        gaps.append(f"{doc_type}: signature evidence is unclear and needs manual verification.")
    return gaps


def _filter_missing_items_for_doc(doc_type: str, items: List[str]) -> List[str]:
    allowed_keywords = {
        "FAFSA Confirmation": ["sai", "school code", "submission", "signature", "student name", "enrollment", "residency"],
        "Income Verification Form": ["household", "income", "tax year", "wage", "signature", "student name"],
        "Tax Return": ["tax", "agi", "income", "transcript", "page", "signature", "student name", "record id"],
        "Iowa Financial Aid Application": ["iowa", "residency", "icaps", "signature", "enrollment", "state aid"],
        "SAP Appeal Documentation": ["sap", "gpa", "attempted", "earned", "third-party", "documentation", "signature", "advisor plan"],
        "Outside Scholarship Notice": ["outside scholarship", "award", "donor", "signature", "student name"],
        "Loan Counseling/MPN Confirmation": ["mpn", "counseling", "loan", "signature", "student name"],
        "Scholarship Application": ["scholarship", "gpa", "signature", "student name"],
        "Other": [],
    }
    keywords = allowed_keywords.get(doc_type, [])
    if not keywords:
        return items
    filtered = []
    disallowed_phrases = {
        "FAFSA Confirmation": ["household income", "tax year", "household size", "gpa", "attempted credits", "earned credits"],
        "Iowa Financial Aid Application": ["household income", "tax year", "gpa", "attempted credits", "earned credits"],
        "Tax Return": ["gpa", "attempted credits", "earned credits"],
    }
    blocked = disallowed_phrases.get(doc_type, [])
    for item in items:
        lower = item.lower()
        if any(phrase in lower for phrase in blocked):
            continue
        if any(k in lower for k in keywords):
            filtered.append(item)
    return filtered


def _normalize_case_summary(summary: Dict[str, Any], records: List[Dict[str, Any]]) -> Dict[str, Any]:
    normalized = dict(summary or {})
    doc_level_missing: List[str] = []
    for r in records:
        doc_level_missing.extend(r["extraction"].get("missing_items", []))

    ai_issues = normalized.get("priority_issues", [])
    if not isinstance(ai_issues, list):
        ai_issues = []
    if doc_level_missing:
        merged_issues = _unique_preserve_order(doc_level_missing)
    else:
        merged_issues = _unique_preserve_order([str(x) for x in ai_issues if str(x).strip()])
    grouped_issues, grouped_actions = _group_issues_and_actions(merged_issues)

    normalized["priority_issues"] = grouped_issues
    ai_actions = normalized.get("follow_up_actions", [])
    if not isinstance(ai_actions, list):
        ai_actions = []
    normalized["follow_up_actions"] = _unique_preserve_order(grouped_actions + [str(x) for x in ai_actions if str(x).strip()])

    status = str(normalized.get("overall_status") or "").strip()
    if not status:
        status = "needs_follow_up" if grouped_issues else "ready_for_review"
    if grouped_issues and status == "ready_for_review":
        status = "needs_follow_up"
    normalized["overall_status"] = status
    return normalized


def _group_issues_and_actions(issues: List[str]) -> tuple[List[str], List[str]]:
    if not issues:
        return [], []
    grouped: List[str] = []
    actions: List[str] = []

    lower_issues = [i.lower() for i in issues]
    if any("signature appears missing" in x or "signature evidence is unclear" in x for x in lower_issues):
        grouped.append("One or more documents have missing or unclear signatures.")
        actions.append("Request signatures where missing and manually verify unclear signature areas.")

    if any("page 2" in x and "tax" in x for x in lower_issues):
        grouped.append("Tax return transcript appears incomplete (page 2 missing).")
        actions.append("Request the missing page 2 of the IRS tax return transcript.")

    if any("residency evidence" in x for x in lower_issues):
        grouped.append("Iowa aid documentation is missing residency evidence.")
        actions.append("Collect residency evidence for Iowa state aid review.")

    if any("third-party documentation" in x and "sap" in x for x in lower_issues):
        grouped.append("SAP appeal packet is missing third-party documentation.")
        actions.append("Request third-party support documentation for SAP appeal review.")

    for issue in issues:
        low = issue.lower()
        if "signature" in low or ("page 2" in low and "tax" in low) or "residency evidence" in low:
            continue
        if "third-party documentation" in low and "sap" in low:
            continue
        if issue not in grouped:
            grouped.append(issue)

    return _unique_preserve_order(grouped), _unique_preserve_order(actions)


def _unique_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in items:
        key = item.strip()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _is_low_information_issue(text: str) -> bool:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower()).strip()
    words = [w for w in cleaned.split() if w]
    return len(words) <= 4


def _drop_subsumed_issues(items: List[str]) -> List[str]:
    out: List[str] = []
    lowered = [i.lower() for i in items]
    for idx, item in enumerate(items):
        low = lowered[idx]
        if any(idx != j and low in lowered[j] and len(low) >= 12 for j in range(len(items))):
            continue
        out.append(item)
    return out


def _call_json_model(
    client: Any,
    prompt: str,
    images: Optional[List[str]] = None,
    model: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    try:
        content: List[Dict[str, Any]] = [{"type": "input_text", "text": prompt}]
        for image_b64 in images or []:
            content.append(
                {
                    "type": "input_image",
                    "image_url": f"data:image/png;base64,{image_b64}",
                }
            )

        response = client.responses.create(
            model=model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            temperature=0,
            input=[{"role": "user", "content": content}],
        )
        output = (response.output_text or "").strip()
        try:
            return json.loads(output)
        except Exception:
            match = re.search(r"\{.*\}", output, re.DOTALL)
            if not match:
                return None
            return json.loads(match.group(0))
    except Exception:
        return None


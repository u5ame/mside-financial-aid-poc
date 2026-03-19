from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import fitz


PAGE_WIDTH = 612
PAGE_HEIGHT = 792
MARGIN_X = 46


def draw_header(page: fitz.Page, title: str, subtitle: str) -> int:
    y = 48
    page.insert_text((MARGIN_X, y), title, fontsize=15, fontname="helv")
    y += 20
    page.insert_text((MARGIN_X, y), subtitle, fontsize=10, fontname="helv")
    y += 16
    page.draw_line((MARGIN_X, y), (PAGE_WIDTH - MARGIN_X, y), color=(0.2, 0.2, 0.2), width=1)
    return y + 18


def draw_label_value(page: fitz.Page, y: int, label: str, value: str) -> int:
    page.insert_text((MARGIN_X, y), f"{label}: {value}", fontsize=11, fontname="helv")
    return y + 18


def draw_signature_block(page: fitz.Page, y: int, label: str) -> int:
    page.insert_text((MARGIN_X, y), f"{label}:", fontsize=11, fontname="helv")
    y += 4
    sig_line_y = y + 14
    page.draw_line((MARGIN_X + 85, sig_line_y), (PAGE_WIDTH - MARGIN_X - 50, sig_line_y), color=(0, 0, 0), width=0.8)
    return y + 28


def rasterize_to_image_only_pdf(output_pdf: Path, draw_fn) -> None:
    src = fitz.open()
    page = src.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    draw_fn(page)

    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    png_bytes = pix.tobytes("png")
    src.close()

    out = fitz.open()
    out_page = out.new_page(width=PAGE_WIDTH, height=PAGE_HEIGHT)
    out_page.insert_image(out_page.rect, stream=png_bytes)
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    out.save(output_pdf)
    out.close()


def make_verification_worksheet(path: Path, student: Dict[str, str]) -> None:
    def draw(page: fitz.Page) -> None:
        y = draw_header(
            page,
            "Morningside University - 2025-2026 Verification Worksheet (Synthetic)",
            "Office of Student Financial Planning | V1 style structure for prototype testing",
        )
        y = draw_label_value(page, y, "Student Name", student["name"])
        y = draw_label_value(page, y, "Student ID", student["student_id"])
        y = draw_label_value(page, y, "Last 4 SSN", student["ssn4"])
        y = draw_label_value(page, y, "Date of Birth", student["dob"])
        y = draw_label_value(page, y, "Email", student["email"])
        y = draw_label_value(page, y, "Phone", student["phone"])
        y = draw_label_value(page, y, "Dependency Status", student["dependency_status"])
        y += 8
        page.insert_text((MARGIN_X, y), "Household Information", fontsize=12, fontname="helv")
        y += 18
        y = draw_label_value(page, y, "Household Size", student["household_size"])
        y = draw_label_value(page, y, "Household Members in College", student["members_in_college"])
        y += 8
        page.insert_text((MARGIN_X, y), "Income Information", fontsize=12, fontname="helv")
        y += 18
        y = draw_label_value(page, y, "Tax Year", student["tax_year"])
        y = draw_label_value(page, y, "Adjusted Gross Income (AGI)", student["agi"])
        y = draw_label_value(page, y, "Wages Parent 1", student["wages_parent_1"])
        y = draw_label_value(page, y, "Wages Parent 2", student["wages_parent_2"])
        if student.get("verification_note"):
            y += 8
            page.insert_text((MARGIN_X, y), student["verification_note"], fontsize=10, fontname="helv")
        y += 8
        page.insert_text(
            (MARGIN_X, y),
            "Certification: By signing, we certify all information is complete and accurate.",
            fontsize=10,
            fontname="helv",
        )
        y += 18
        draw_signature_block(page, y, "Student Signature")

    rasterize_to_image_only_pdf(path, draw)


def make_fafsa_summary(path: Path, student: Dict[str, str]) -> None:
    def draw(page: fitz.Page) -> None:
        y = draw_header(
            page,
            "FAFSA Submission Summary (Synthetic)",
            "Federal Student Aid record excerpt for Morningside intake testing",
        )
        y = draw_label_value(page, y, "Student Name", student["name"])
        y = draw_label_value(page, y, "FAFSA Award Year", "2025-2026")
        y = draw_label_value(page, y, "Student Aid Index (SAI)", student["sai"])
        y = draw_label_value(page, y, "School Code Sent", "001879")
        y = draw_label_value(page, y, "School Name", "Morningside University")
        y = draw_label_value(page, y, "Submission Date", student["fafsa_date"])
        y = draw_label_value(page, y, "Enrollment Status", student["enrollment"])
        y = draw_label_value(page, y, "Residency", student["residency"])
        y = draw_label_value(page, y, "Dependency Status", student["dependency_status"])
        y += 12
        draw_signature_block(page, y, "Student Signature")

    rasterize_to_image_only_pdf(path, draw)


def make_tax_transcript(path: Path, student: Dict[str, str]) -> None:
    def draw(page: fitz.Page) -> None:
        y = draw_header(
            page,
            "IRS Tax Return Transcript (Synthetic)",
            "Financial aid intake copy",
        )
        y = draw_label_value(page, y, "Student Name", student["name"])
        y = draw_label_value(page, y, "Transcript Page", student["tax_page_indicator"])
        y = draw_label_value(page, y, "Tax Year", student["tax_year"])
        y = draw_label_value(page, y, "Adjusted Gross Income (AGI)", student["agi"])
        y = draw_label_value(page, y, "Taxable Income", student["taxable_income"])
        y = draw_label_value(page, y, "Filing Status", student["filing_status"])
        y = draw_label_value(page, y, "IRS Record ID", student["tax_record_id"])
        y += 10
        draw_signature_block(page, y, "Taxpayer Signature")

    rasterize_to_image_only_pdf(path, draw)


def make_iowa_state_aid(path: Path, student: Dict[str, str]) -> None:
    def draw(page: fitz.Page) -> None:
        y = draw_header(
            page,
            "Iowa Financial Aid Application Extract (Synthetic)",
            "ICAPS-style fields for ITG/AIOS eligibility review",
        )
        y = draw_label_value(page, y, "Student Name", student["name"])
        y = draw_label_value(page, y, "Program", "Iowa Tuition Grant (ITG)")
        y = draw_label_value(page, y, "Program", "All Iowa Opportunity Scholarship (AIOS)")
        y = draw_label_value(page, y, "Iowa Residency", student["residency"])
        y = draw_label_value(page, y, "Residency Evidence", student["residency_evidence"])
        y = draw_label_value(page, y, "Enrollment Intensity", student["enrollment_intensity"])
        y = draw_label_value(page, y, "FAFSA Filed", "Yes")
        y = draw_label_value(page, y, "ICAPS Submission Date", student["icaps_date"])
        y += 8
        page.insert_text((MARGIN_X, y), "Reminder: ITG/State aid filing timing often references Jul 1.", fontsize=10, fontname="helv")
        y += 16
        draw_signature_block(page, y, "Applicant Signature")

    rasterize_to_image_only_pdf(path, draw)


def make_sap_appeal(path: Path, student: Dict[str, str]) -> None:
    def draw(page: fitz.Page) -> None:
        y = draw_header(
            page,
            "Satisfactory Academic Progress (SAP) Appeal (Synthetic)",
            "Student-submitted appeal with recovery plan",
        )
        y = draw_label_value(page, y, "Student Name", student["name"])
        y = draw_label_value(page, y, "Cumulative GPA", student["gpa"])
        y = draw_label_value(page, y, "Attempted Credits", student["attempted_credits"])
        y = draw_label_value(page, y, "Earned Credits", student["earned_credits"])
        y = draw_label_value(page, y, "Third-Party Documentation", student["third_party_docs"])
        y = draw_label_value(page, y, "Academic Advisor Plan Status", student["advisor_plan_status"])
        y += 8
        page.insert_text((MARGIN_X, y), "Appeal Statement:", fontsize=11, fontname="helv")
        y += 16
        page.insert_text(
            (MARGIN_X, y),
            student["sap_statement"],
            fontsize=10,
            fontname="helv",
        )
        y += 16
        page.insert_text((MARGIN_X, y), "- Meet advisor every 2 weeks", fontsize=10, fontname="helv")
        y += 14
        page.insert_text((MARGIN_X, y), "- Complete 12 credits with no withdrawals", fontsize=10, fontname="helv")
        y += 14
        page.insert_text((MARGIN_X, y), "- Use writing center and tutoring support", fontsize=10, fontname="helv")
        y += 20
        draw_signature_block(page, y, "Student Signature")

    rasterize_to_image_only_pdf(path, draw)


def build_student_packet(root: Path, slug: str, student: Dict[str, str]) -> None:
    packet_dir = root / slug
    packet_dir.mkdir(parents=True, exist_ok=True)
    for old_pdf in packet_dir.glob("*.pdf"):
        old_pdf.unlink()

    make_fafsa_summary(packet_dir / "scan_01.pdf", student)
    make_verification_worksheet(packet_dir / "scan_02.pdf", student)
    make_tax_transcript(packet_dir / "scan_03.pdf", student)
    make_iowa_state_aid(packet_dir / "scan_04.pdf", student)
    make_sap_appeal(packet_dir / "scan_05.pdf", student)

    (packet_dir / "README.md").write_text(
        "\n".join(
            [
                f"# Student Package: {student['name']}",
                "",
                "Image-only synthetic packet for OCR-focused intake testing.",
                "- Signature lines are intentionally blank so signatures can be added manually.",
                "- Contains FAFSA summary, verification worksheet, tax transcript, Iowa state aid extract, and SAP appeal.",
                f"- Scenario focus: {student['scenario_focus']}",
            ]
        ),
        encoding="utf-8",
    )

    manifest = {
        "student_name": student["name"],
        "scenario_focus": student["scenario_focus"],
        "documents": [
            {
                "file": "scan_01.pdf",
                "document_type": "FAFSA Confirmation",
                "purpose": "Confirms FAFSA submission details, SAI, and school code routing.",
            },
            {
                "file": "scan_02.pdf",
                "document_type": "Income Verification Form",
                "purpose": "Provides household and income verification fields used for review.",
            },
            {
                "file": "scan_03.pdf",
                "document_type": "Tax Return",
                "purpose": "Provides AGI/tax-year support and transcript completeness status.",
            },
            {
                "file": "scan_04.pdf",
                "document_type": "Iowa Financial Aid Application",
                "purpose": "Captures Iowa state-aid context and residency support details.",
            },
            {
                "file": "scan_05.pdf",
                "document_type": "SAP Appeal Documentation",
                "purpose": "Includes SAP context, attempted/earned credits, and support docs status.",
            },
        ],
        "expected_catches": student["expected_catches"],
    }
    (packet_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def build_dataset(base_dir: Path) -> None:
    packages_root = base_dir / "sample_data" / "student_packages"
    packages_root.mkdir(parents=True, exist_ok=True)

    students: Dict[str, Dict[str, str]] = {
        "jordan_lee": {
            "name": "Jordan Lee",
            "student_id": "MORN-884201",
            "ssn4": "1429",
            "dob": "2006-04-12",
            "email": "jordan.lee@email.example",
            "phone": "712-555-0192",
            "dependency_status": "Dependent",
            "household_size": "4",
            "members_in_college": "2",
            "tax_year": "2024",
            "agi": "$68,400",
            "wages_parent_1": "$44,200",
            "wages_parent_2": "$24,200",
            "verification_note": "Household and income fields are complete in this worksheet.",
            "taxable_income": "$49,700",
            "filing_status": "Married filing jointly",
            "tax_page_indicator": "1 of 2",
            "tax_record_id": "TRX-2024-88731",
            "sai": "2450",
            "fafsa_date": "2026-01-22",
            "enrollment": "Full-time",
            "residency": "Iowa resident",
            "residency_evidence": "Iowa driver's license uploaded",
            "enrollment_intensity": "Full-time (12+ credits)",
            "icaps_date": "2026-01-25",
            "gpa": "1.82 GPA",
            "attempted_credits": "46",
            "earned_credits": "28",
            "third_party_docs": "Yes - provider letter attached",
            "advisor_plan_status": "On file",
            "sap_statement": "I fell below SAP pace due to family medical disruptions. I now have an academic recovery plan.",
            "scenario_focus": "Tax transcript appears to include only page 1 while indicating multiple pages.",
            "expected_catches": [
                {
                    "title": "Tax transcript completeness gap",
                    "description": "Tax transcript appears incomplete because only page 1 is present while the document indicates multiple pages.",
                    "keywords": ["page 2", "tax return", "missing", "transcript"],
                }
            ],
        },
        "maya_patel": {
            "name": "Maya Patel",
            "student_id": "MORN-903517",
            "ssn4": "7712",
            "dob": "2005-09-03",
            "email": "maya.patel@email.example",
            "phone": "515-555-0174",
            "dependency_status": "Dependent",
            "household_size": "",
            "members_in_college": "1",
            "tax_year": "2024",
            "agi": "$52,900",
            "wages_parent_1": "$38,100",
            "wages_parent_2": "",
            "verification_note": "Parent 2 wage documentation pending submission from employer.",
            "taxable_income": "$36,200",
            "filing_status": "Head of household",
            "tax_page_indicator": "1 of 1",
            "tax_record_id": "TRX-2024-55129",
            "sai": "1320",
            "fafsa_date": "2026-02-09",
            "enrollment": "Full-time",
            "residency": "Iowa resident",
            "residency_evidence": "Iowa state ID uploaded",
            "enrollment_intensity": "Three-quarter time (9-11 credits)",
            "icaps_date": "2026-02-11",
            "gpa": "2.11 GPA",
            "attempted_credits": "61",
            "earned_credits": "47",
            "third_party_docs": "Yes - advisor memo attached",
            "advisor_plan_status": "On file",
            "sap_statement": "Course withdrawals during a family relocation affected my pace, and I am following an advisor-approved plan.",
            "scenario_focus": "Verification worksheet missing household size and one wage field.",
            "expected_catches": [
                {
                    "title": "Verification worksheet field gaps",
                    "description": "Household size is blank and Parent 2 wage value is missing on the verification worksheet.",
                    "keywords": ["household size", "parent 2", "wage", "verification"],
                }
            ],
        },
        "noah_garcia": {
            "name": "Noah Garcia",
            "student_id": "MORN-917044",
            "ssn4": "3095",
            "dob": "2004-12-19",
            "email": "noah.garcia@email.example",
            "phone": "319-555-0128",
            "dependency_status": "Independent",
            "household_size": "5",
            "members_in_college": "2",
            "tax_year": "2024",
            "agi": "$74,300",
            "wages_parent_1": "$49,500",
            "wages_parent_2": "$24,800",
            "verification_note": "Income fields are complete in this worksheet.",
            "taxable_income": "$55,900",
            "filing_status": "Married filing jointly",
            "tax_page_indicator": "1 of 1",
            "tax_record_id": "TRX-2024-99084",
            "sai": "3410",
            "fafsa_date": "2026-03-01",
            "enrollment": "Part-time",
            "residency": "Iowa resident",
            "residency_evidence": "",
            "enrollment_intensity": "Part-time (6-8 credits)",
            "icaps_date": "2026-03-04",
            "gpa": "1.95 GPA",
            "attempted_credits": "79",
            "earned_credits": "52",
            "third_party_docs": "Pending",
            "advisor_plan_status": "Draft only",
            "sap_statement": "Medical leave and reduced enrollment impacted progress, and I am requesting probation with a return-to-full-load plan.",
            "scenario_focus": "Residency evidence missing for Iowa aid and SAP third-party documentation missing.",
            "expected_catches": [
                {
                    "title": "Iowa residency evidence gap",
                    "description": "Residency evidence is blank in the Iowa aid form and should be requested for state-aid review.",
                    "keywords": ["residency evidence", "iowa", "not provided", "state aid"],
                },
                {
                    "title": "SAP support documentation gap",
                    "description": "SAP appeal lists third-party documentation as pending and advisor plan status as draft only.",
                    "keywords": ["sap", "third-party", "documentation", "missing"],
                },
            ],
        },
    }

    for slug, profile in students.items():
        build_student_packet(packages_root, slug, profile)

    (packages_root / "README.md").write_text(
        "\n".join(
            [
                "# Sample Student Packages",
                "",
                "Use these folders to test the package preselect workflow in the app.",
                "- jordan_lee (tax transcript completeness gap)",
                "- maya_patel (verification worksheet missing income/household fields)",
                "- noah_garcia (state-aid residency evidence + SAP support-doc gap)",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    build_dataset(Path(__file__).resolve().parents[1])
    print("Scanned-style synthetic PDFs generated successfully.")


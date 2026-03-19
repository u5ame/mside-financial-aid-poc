from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Iterable, List


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def write_text_pdf(path: Path, pages: List[List[str]]) -> None:
    objects: List[bytes] = []
    page_obj_ids: List[int] = []

    # 1: Catalog, 2: Pages container
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"<< /Type /Pages /Kids [] /Count 0 >>")

    for page_lines in pages:
        page_obj_id = len(objects) + 1
        content_obj_id = page_obj_id + 1
        page_obj_ids.append(page_obj_id)

        text_cmds = ["BT", "/F1 11 Tf", "72 760 Td", "14 TL"]
        for line in page_lines:
            text_cmds.append(f"({_pdf_escape(line)}) Tj")
            text_cmds.append("T*")
        text_cmds.append("ET")
        stream_data = ("\n".join(text_cmds) + "\n").encode("latin-1", errors="replace")
        content_obj = (
            b"<< /Length " + str(len(stream_data)).encode("ascii") + b" >>\nstream\n" + stream_data + b"endstream"
        )

        page_obj = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 "
            + str(3 + 2 * len(pages)).encode("ascii")
            + b" 0 R >> >> "
            b"/Contents "
            + str(content_obj_id).encode("ascii")
            + b" 0 R >>"
        )

        objects.append(page_obj)
        objects.append(content_obj)

    font_obj = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    objects.append(font_obj)

    kids = " ".join(f"{obj_id} 0 R" for obj_id in page_obj_ids).encode("ascii")
    objects[1] = b"<< /Type /Pages /Kids [" + kids + b"] /Count " + str(len(page_obj_ids)).encode("ascii") + b" >>"

    pdf = bytearray()
    pdf.extend(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{idx} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_pos = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(pdf)


def wrap_lines(lines: Iterable[str], width: int = 90) -> List[str]:
    wrapped: List[str] = []
    for line in lines:
        if not line:
            wrapped.append("")
            continue
        wrapped.extend(textwrap.wrap(line, width=width, break_long_words=False, break_on_hyphens=False))
    return wrapped


def build_dataset(base_dir: Path) -> None:
    packet_dir = base_dir / "sample_data" / "morningside_fa_packet_a"
    packet_dir.mkdir(parents=True, exist_ok=True)
    for old_pdf in packet_dir.glob("*.pdf"):
        old_pdf.unlink()

    docs = {
        "doc_01.pdf": [
            [
                "Morningside University - FAFSA Submission Summary (Synthetic)",
                "Student Name: Jordan Lee",
                "Morningside Federal School Code: 001879",
                "FAFSA Cycle: 2025-2026",
                "Submission Date: January 22, 2026",
                "Student Aid Index (SAI): 2450",
                "Dependency Status: Dependent",
                "Enrollment Status: Full-time",
                "Residency: Iowa resident",
                "Confirmation Source: studentaid.gov",
                "",
                "Attestation: This synthetic summary is for prototype testing only.",
                "Signature: ____________________",
            ]
        ],
        "doc_02.pdf": [
            [
                "Office of Student Financial Planning",
                "Income Verification Worksheet - 2025-2026 (Synthetic)",
                "Student Name: Jordan Lee",
                "Tax Year: 2024",
                "Household Size: 4",
                "Household Income: $68,400",
                "Parent 1 Wages: $44,200",
                "Parent 2 Wages: $24,200",
                "Enrollment Status: Full-time",
                "Residency: Iowa resident",
                "",
                "Certification Section",
                "I certify this information is complete and accurate.",
                "Student Signature: ____________________",
                "Date: ____________________",
            ]
        ],
        "doc_03.pdf": [
            [
                "IRS Tax Return Transcript (Synthetic for POC)",
                "Student Name: Jordan Lee",
                "Tax Year: 2024",
                "Adjusted Gross Income (AGI): $68,400",
                "Taxable Income: $49,700",
                "Filing Status: Married filing jointly",
                "Transcript status: Partial upload by student",
                "",
                "Page 1 of 2",
                "Notice: Page 2 not included in this upload packet.",
                "Signature: ____________________",
            ],
            [
                "Appendix Marker - Missing Page Simulation",
                "This page intentionally states that original page 2 was not included.",
                "Financial aid staff should review whether a complete transcript is required.",
            ],
        ],
        "doc_04.pdf": [
            [
                "Iowa Financial Aid Application Extract (Synthetic)",
                "Student Name: Jordan Lee",
                "Program Interest: Iowa Tuition Grant (ITG)",
                "Program Interest: All Iowa Opportunity Scholarship (AIOS)",
                "Iowa Residency Status: Iowa resident",
                "Expected Enrollment: Full-time (12+ credits)",
                "Applicant confirmed FAFSA filing and Iowa application filing in ICAPS portal.",
                "",
                "Compliance Reminder",
                "Submit FAFSA by Jul 1 for key Iowa programs.",
                "AIOS on-time filing target: Apr 1.",
                "Signature: ____________________",
            ]
        ],
        "doc_05.pdf": [
            [
                "Outside Scholarship Notification (Synthetic)",
                "Student Name: Jordan Lee",
                "Scholarship Name: Siouxland STEM Community Award",
                "Award Amount: $2,500",
                "Disbursement: $1,250 Fall / $1,250 Spring",
                "Donor requires proof of full-time enrollment each semester.",
                "",
                "Student Statement",
                "I understand outside scholarships must be reported to the Office of Student Financial Planning.",
                "Signature: ____________________",
            ]
        ],
        "doc_06.pdf": [
            [
                "Satisfactory Academic Progress (SAP) Appeal - Synthetic",
                "Student Name: Jordan Lee",
                "Current Cumulative GPA: 1.82 GPA",
                "Attempted Credits: 46",
                "Earned Credits: 28",
                "Enrollment Status: Full-time",
                "",
                "Appeal Summary",
                "I received a financial aid warning after not meeting pace due to family medical disruptions in Fall.",
                "I completed tutoring and weekly advising this spring.",
                "I request aid probation while following the attached academic recovery plan.",
                "",
                "Academic Plan",
                "- Meet advisor bi-weekly.",
                "- Complete minimum 12 credits with no withdrawals.",
                "- Attend writing center and math lab support sessions.",
                "Signature: ____________________",
            ]
        ],
    }

    for filename, page_groups in docs.items():
        pages = [wrap_lines(lines) for lines in page_groups]
        write_text_pdf(packet_dir / filename, pages)

    manifest = packet_dir / "README.md"
    manifest.write_text(
        "\n".join(
            [
                "# Morningside Financial Aid Sample Packet A",
                "",
                "This folder contains synthetic PDFs for realistic POC testing.",
                "",
                "## Included Scenarios",
                "- FAFSA confirmation with Morningside school code and SAI",
                "- Income verification worksheet with blank signature line",
                "- Tax return transcript upload with incomplete page marker",
                "- Iowa state aid extract with ITG/AIOS references",
                "- Outside scholarship notice",
                "- SAP appeal documentation with academic plan",
                "- All signature lines are intentionally blank for manual signature testing",
                "",
                "## Expected Behavior in App",
                "- Classification should map each file to a meaningful intake category.",
                "- Extraction should pull student name, income/tax year, enrollment, residency, and SAP metrics where present.",
                "- Signature status may be unclear until manual signatures are added.",
                "- Draft email should reference missing items and keep staff-review language.",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    build_dataset(Path(__file__).resolve().parents[1])
    print("Synthetic sample PDFs generated successfully.")


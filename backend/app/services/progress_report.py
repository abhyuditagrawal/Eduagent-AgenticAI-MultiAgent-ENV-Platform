"""Generate PDF progress reports for students."""

import io
from datetime import datetime, timezone

import structlog
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.student_state import (
    get_mastery_summary,
    get_weak_concepts,
    get_overdue_concepts,
    get_study_priority_queue,
)

logger = structlog.get_logger()


async def generate_progress_pdf(
    db: AsyncSession,
    student_id,
    subject_id,
    student_name: str,
    subject_name: str,
) -> bytes:
    """Generate a PDF progress report and return as bytes."""
    mastery = await get_mastery_summary(db, student_id, subject_id)
    weak = await get_weak_concepts(db, student_id, subject_id, threshold=0.5)
    overdue = await get_overdue_concepts(db, student_id, subject_id)
    priority = await get_study_priority_queue(db, student_id, subject_id)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle", parent=styles["Title"],
        fontSize=20, spaceAfter=6,
    )
    heading_style = ParagraphStyle(
        "CustomHeading", parent=styles["Heading2"],
        fontSize=14, spaceAfter=8, spaceBefore=16,
        textColor=colors.HexColor("#1e40af"),
    )
    body_style = styles["BodyText"]

    elements = []

    # Header
    elements.append(Paragraph("EduAgent Progress Report", title_style))
    elements.append(Spacer(1, 4))

    now = datetime.now(timezone.utc)
    meta_data = [
        ["Student:", student_name],
        ["Subject:", subject_name],
        ["Generated:", now.strftime("%B %d, %Y at %H:%M UTC")],
    ]
    meta_table = Table(meta_data, colWidths=[2 * inch, 4 * inch])
    meta_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 8))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.grey))

    # Overall Mastery
    elements.append(Paragraph("Overall Mastery", heading_style))
    overall_pct = round(mastery.get("overall_score", 0) * 100)
    total_concepts = mastery.get("total_concepts", 0)
    mastered_count = mastery.get("mastered", 0)
    elements.append(Paragraph(
        f"Overall mastery score: <b>{overall_pct}%</b> "
        f"({mastered_count}/{total_concepts} concepts mastered)", body_style
    ))
    elements.append(Paragraph(
        f"Overdue reviews: <b>{mastery.get('overdue_reviews', 0)}</b>", body_style
    ))
    elements.append(Spacer(1, 8))

    # Chapter Breakdown
    chapters = mastery.get("chapters", [])
    if chapters:
        elements.append(Paragraph("Chapter Breakdown", heading_style))
        ch_data = [["Chapter", "Concepts", "Avg Mastery"]]
        for ch in chapters:
            concepts = ch.get("concepts", [])
            avg = sum(c.get("confidence", 0) for c in concepts) / max(len(concepts), 1)
            ch_data.append([
                ch.get("chapter", "Unknown"),
                str(len(concepts)),
                f"{round(avg * 100)}%",
            ])
        ch_table = Table(ch_data, colWidths=[3 * inch, 1.5 * inch, 1.5 * inch])
        ch_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e40af")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4ff")]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(ch_table)
        elements.append(Spacer(1, 8))

    # Weak Points
    if weak:
        elements.append(Paragraph("Weak Points (Needs Attention)", heading_style))
        wp_data = [["Concept", "Confidence", "Priority"]]
        for w in weak[:10]:
            conf = round(w.get("confidence", 0) * 100)
            label = "Critical" if conf < 20 else "Weak" if conf < 40 else "Needs work"
            wp_data.append([w["concept_name"], f"{conf}%", label])
        wp_table = Table(wp_data, colWidths=[3 * inch, 1.5 * inch, 1.5 * inch])
        wp_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#dc2626")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]))
        elements.append(wp_table)
        elements.append(Spacer(1, 8))

    # Study Priority Queue
    if priority:
        elements.append(Paragraph("Recommended Study Order", heading_style))
        for i, p in enumerate(priority[:8], 1):
            elements.append(Paragraph(
                f"{i}. <b>{p['concept_name']}</b> — Priority score: {round(p.get('priority_score', 0), 1)}",
                body_style,
            ))
        elements.append(Spacer(1, 8))

    # Overdue Reviews
    if overdue:
        elements.append(Paragraph("Overdue Reviews", heading_style))
        for o in overdue[:8]:
            days = o.get("days_overdue", 0)
            elements.append(Paragraph(
                f"- <b>{o['concept_name']}</b>: {days} day(s) overdue",
                body_style,
            ))

    # Footer
    elements.append(Spacer(1, 24))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    elements.append(Paragraph(
        "<i>Generated by EduAgent — Multi-Agent AI Educational Platform</i>",
        ParagraphStyle("Footer", parent=body_style, fontSize=8, textColor=colors.grey),
    ))

    doc.build(elements)
    return buffer.getvalue()

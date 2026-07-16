from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..entities import Incident


def generate_draft_report(incident: Incident, output: Path, evidence_images: list[Path] | None = None) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    document = SimpleDocTemplate(str(output), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm)
    measurements = incident.measurements_json or {}
    rows = [
        ("Incident", incident.incident_number),
        ("Date and time", incident.created_at.isoformat() if incident.created_at else "Unknown"),
        ("Camera / source", f"Uploaded analysis job {incident.job_id}" if incident.job_id else "Simulation source"),
        ("Camera location", "Not specified by operator"),
        ("Violation type", incident.category),
        ("Vehicle class", incident.vehicle_class or "Unknown"),
        ("Plate", incident.plate_text or "Unreadable"),
        ("OCR confidence", f"{incident.plate_confidence:.0%}" if incident.plate_confidence else "Insufficient confidence"),
        ("Measured speed", f"{measurements.get('speed_kph')} km/h" if measurements.get("speed_kph") is not None else "Not measured"),
        ("Speed limit", f"{measurements.get('speed_limit_kph')} km/h" if measurements.get("speed_limit_kph") is not None else "Not configured"),
        ("Review decision", incident.review_status), ("Operator notes", incident.operator_notes or "None"),
    ]
    table = Table(rows, colWidths=[45 * mm, 115 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#192025")),
        ("TEXTCOLOR", (0, 0), (0, -1), colors.white), ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 7),
    ]))
    story = [
        Paragraph("TrafficVision — Draft Violation Review", styles["Title"]), Spacer(1, 8 * mm), table,
        Spacer(1, 8 * mm),
    ]
    for path in (evidence_images or [])[:3]:
        if path.is_file():
            story.extend([Image(str(path), width=160 * mm, height=90 * mm), Spacer(1, 3 * mm)])
    story.extend([
        Spacer(1, 5 * mm), Paragraph(
            "EDUCATIONAL PROTOTYPE: This draft is not a certified enforcement record. All detections, "
            "OCR readings, measurements, and classifications require trained human review.", styles["BodyText"]
        ),
    ])
    document.build(story)
    return output

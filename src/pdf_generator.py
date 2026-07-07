import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle
)


def escape_text(text):
    if text is None:
        return ""

    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def format_time(seconds):
    seconds = float(seconds or 0)
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)

    return f"{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def get_visible_speaker(segment):
    speaker = segment.get("speaker", "SPEAKER_UNKNOWN")
    speaker_name = segment.get("speaker_name", "").strip()

    return speaker_name if speaker_name else speaker


def get_review_state(segment):
    if segment.get("human_reviewed"):
        return {
            "key": "human",
            "label": "Humano comprobado"
        }

    similarity = segment.get("similarity_percent", "")

    if similarity != "" and similarity >= 90:
        return {
            "key": "ai_ok",
            "label": "IA consistente"
        }

    return {
        "key": "ai_doubt",
        "label": "Consistencia de IA menor del 90%"
    }


def build_speaker_summary(segments):
    speakers = {}

    for segment in segments:
        original = segment.get("speaker", "SPEAKER_UNKNOWN")
        visible = get_visible_speaker(segment)

        if original not in speakers:
            speakers[original] = visible

    return speakers


def merge_consecutive_segments_by_speaker(segments):
    """
    Une segmentos consecutivos del mismo hablante, pero conserva
    el estado de revisión de cada segmento por separado.

    Así, si un hablante tiene varios segmentos seguidos, se muestran juntos,
    pero cada fragmento mantiene su color de revisión.
    """
    merged = []

    for segment in segments:
        speaker = get_visible_speaker(segment)
        text = segment.get("text", "").strip()

        if not text:
            continue

        state = get_review_state(segment)

        text_part = {
            "text": text,
            "state": state,
            "start": segment.get("start", 0),
            "end": segment.get("end", 0)
        }

        if merged and merged[-1]["speaker"] == speaker:
            merged[-1]["end"] = segment.get("end", merged[-1]["end"])
            merged[-1]["parts"].append(text_part)
            continue

        merged.append({
            "speaker": speaker,
            "start": segment.get("start", 0),
            "end": segment.get("end", 0),
            "parts": [text_part]
        })

    return merged


def build_colored_dialog_text(parts):
    html_parts = []

    for part in parts:
        text = escape_text(part["text"])
        state = part["state"]

        if state["key"] == "human":
            html_parts.append(f"<b>{text}</b>")
        elif state["key"] == "ai_doubt":
            html_parts.append(
                f'<font backColor="#ffe7a3">{text}</font>'
            )
        else:
            html_parts.append(text)

    return " ".join(html_parts)

def generate_transcript_pdf(segments, meeting, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=1.7 * cm,
        leftMargin=1.7 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        spaceAfter=16,
        textColor=colors.HexColor("#304463")
    )

    section_style = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        spaceBefore=10,
        spaceAfter=8,
        textColor=colors.HexColor("#304463")
    )

    normal_style = ParagraphStyle(
        "NormalCustom",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#2e3b52")
    )

    small_style = ParagraphStyle(
        "SmallStyle",
        parent=normal_style,
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#66758a")
    )

    speaker_style = ParagraphStyle(
        "SpeakerStyle",
        parent=normal_style,
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=13,
        textColor=colors.HexColor("#1f2937")
    )

    dialog_style = ParagraphStyle(
        "DialogStyle",
        parent=normal_style,
        fontName="Helvetica",
        fontSize=10.5,
        leading=15,
        spaceAfter=8,
        textColor=colors.HexColor("#2e3b52")
    )

    story = []

    title = meeting["title"] if meeting and "title" in meeting.keys() else "Transcripcion"
    created_at = meeting["created_at"] if meeting and "created_at" in meeting.keys() else ""

    story.append(Paragraph(f"Transcripcion de la reunion: {escape_text(title)}", title_style))
    story.append(Paragraph(f"<b>Fecha de la grabacion:</b> {escape_text(created_at)}", normal_style))
    story.append(Spacer(1, 0.3 * cm))

    # =========================
    # Hablantes
    # =========================

    story.append(Paragraph("Hablantes identificados", section_style))

    speakers = build_speaker_summary(segments)

    speaker_table_data = [
        [
            Paragraph("<b>Hablante detectado</b>", normal_style),
            Paragraph("<b>Nombre mostrado</b>", normal_style)
        ]
    ]

    for original, visible in speakers.items():
        speaker_table_data.append([
            Paragraph(escape_text(original), normal_style),
            Paragraph(escape_text(visible), speaker_style)
        ])

    speaker_table = Table(
        speaker_table_data,
        colWidths=[6 * cm, 9 * cm],
        hAlign="LEFT"
    )

    speaker_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef4ff")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d7e0ea")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(speaker_table)
    story.append(Spacer(1, 0.4 * cm))

    # =========================
    # Leyenda
    # =========================

    story.append(Paragraph("Leyenda de revision", section_style))

    legend_data = [
        [
            Paragraph("<b>Texto en negrita</b>", normal_style),
            Paragraph("Comprobado por un humano", normal_style)
        ],
        [
            Paragraph("Texto normal", normal_style),
            Paragraph("IA consistente", normal_style)
        ],
        [
            Paragraph(
                '<font backColor="#ffe7a3">&nbsp;Texto con fondo amarillo&nbsp;</font>',
                normal_style
            ),
            Paragraph("Consistencia de IA menor del 90%", normal_style)
        ],
    ]

    legend_table = Table(
        legend_data,
        colWidths=[7 * cm, 8 * cm],
        hAlign="LEFT"
    )

    legend_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 2), (0, 2), colors.HexColor("#ffe7a3")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d7e0ea")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    story.append(legend_table)
    story.append(Spacer(1, 0.4 * cm))

    # =========================
    # Diálogo como texto
    # =========================

    story.append(Paragraph("Dialogo de la reunion", section_style))

    merged_blocks = merge_consecutive_segments_by_speaker(segments)

    for block in merged_blocks:
        start = format_time(block["start"])
        end = format_time(block["end"])
        speaker = escape_text(block["speaker"])
        colored_text = build_colored_dialog_text(block["parts"])

        paragraph = Paragraph(
            f'''
            <b>{speaker}</b>
            <font size="8" color="#66758a">[{escape_text(start)} - {escape_text(end)}]</font>
            <br/>
            {colored_text}
            ''',
            dialog_style
        )

        story.append(paragraph)

    doc.build(story)

    return output_path
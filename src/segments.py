import json
import html
import re
import colorsys
from difflib import SequenceMatcher


def format_time(seconds):
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)

    return f"{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def save_segments_json(segments, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(segments, f, indent=2, ensure_ascii=False)


def normalize_word(word):
    word = word.lower()
    word = re.sub(r"[^\wáéíóúüñ]", "", word)
    return word


def hsv_to_hex(h, s=1.0, v=1.0):
    r, g, b = colorsys.hsv_to_rgb(h, s, v)

    return "#{:02x}{:02x}{:02x}".format(
        int(r * 255),
        int(g * 255),
        int(b * 255)
    )


def generate_speaker_colors(speakers):
    """
    Genera colores distinguibles para los hablantes usando HSV.

    Los tonos se reparten de forma equiespaciada entre 0 y 1.
    Saturation y Value se dejan al máximo.
    """
    total = len(speakers)

    if total == 0:
        return {}

    speaker_colors = {}

    for index, speaker in enumerate(speakers):
        hue = index / total
        speaker_colors[speaker] = hsv_to_hex(hue, 0.25, 0.95)

    return speaker_colors


def highlight_differences(text_a, text_b):
    """
    Devuelve dos textos en HTML:
    - El primero corresponde a text_a.
    - El segundo corresponde a text_b.
    Las palabras distintas aparecen en negrita.
    """

    words_a = text_a.split()
    words_b = text_b.split()

    norm_a = [normalize_word(w) for w in words_a]
    norm_b = [normalize_word(w) for w in words_b]

    matcher = SequenceMatcher(None, norm_a, norm_b)

    highlighted_a = []
    highlighted_b = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        part_a = words_a[i1:i2]
        part_b = words_b[j1:j2]

        if tag == "equal":
            highlighted_a.extend(html.escape(w) for w in part_a)
            highlighted_b.extend(html.escape(w) for w in part_b)
        else:
            highlighted_a.extend(
                f'<strong class="diff-word">{html.escape(w)}</strong>'
                for w in part_a
            )
            highlighted_b.extend(
                f'<strong class="diff-word">{html.escape(w)}</strong>'
                for w in part_b
            )

    return " ".join(highlighted_a), " ".join(highlighted_b)

def generate_html(segments, audio_path, output, job_id=None):
    rows = ""
    markers = []
    speaker_markers = []

    speakers = sorted({
        s.get("speaker", "SPEAKER_UNKNOWN")
        for s in segments
        if s.get("speaker", "SPEAKER_UNKNOWN")
    })

    speaker_colors = generate_speaker_colors(speakers)

    speaker_names = {}

    for s in segments:
        speaker = s.get("speaker", "SPEAKER_UNKNOWN")

        if speaker not in speaker_names:
            speaker_names[speaker] = s.get("speaker_name", "")

    speaker_rows = ""

    for speaker in speakers:
        saved_name = speaker_names.get(speaker, "")
        speaker_color = speaker_colors.get(speaker, "#3f7ad9")

        speaker_rows += f"""
            <tr>
                <td>
                    <button
                        type="button"
                        class="speaker-jump-btn"
                        data-speaker="{html.escape(speaker)}"
                    >
                        <span
                            class="speaker-pill"
                            style="background-color: {speaker_color};"
                        >
                            {html.escape(speaker)}
                        </span>
                    </button>
                </td>
                <td>
                    <input
                        class="speaker-name-input"
                        data-speaker="{html.escape(speaker)}"
                        placeholder="Nombre"
                        value="{html.escape(saved_name)}"
                    >
                </td>
            </tr>
        """

    total_duration = 0.0
    if segments:
        total_duration = max(s["end"] for s in segments)

    for idx, s in enumerate(segments):
        similarity_percent = s.get("similarity_percent", "")
        uncertain = s.get("uncertain", False)
        speaker = s.get("speaker", "SPEAKER_UNKNOWN")
        speaker_name = s.get("speaker_name", "").strip()
        visible_speaker = speaker_name if speaker_name else speaker
        speaker_color = speaker_colors.get(speaker, "#3f7ad9")

        if similarity_percent == "":
            similarity_class = "sim-neutral"
            similarity_label = "-"
        elif similarity_percent >= 90:
            similarity_class = "sim-good"
            similarity_label = f"{similarity_percent}%"
        elif similarity_percent >= 75:
            similarity_class = "sim-medium"
            similarity_label = f"{similarity_percent}%"
        else:
            similarity_class = "sim-bad"
            similarity_label = f"{similarity_percent}%"

        review_needed = (
            similarity_percent != "" and similarity_percent < 90
        )

        human_reviewed = s.get("human_reviewed", False)

        if human_reviewed:
            row_class = "row-human-reviewed"
            reviewed_at = s.get("reviewed_at", "")
            reviewed_info = f" · {html.escape(reviewed_at)}" if reviewed_at else ""
            badge_html = f'<span class="badge badge-human-reviewed">Humano comprobado{reviewed_info}</span>'
        elif review_needed:
            row_class = "row-ai-inconsistent"
            badge_html = f'<span class="badge badge-ai-inconsistent">IA inconsistente · {similarity_label}</span>'
        else:
            row_class = "row-ai-consistent"
            badge_html = f'<span class="badge badge-ai-consistent">IA consistente · {similarity_label}</span>'

        slow_text = s.get("slow_text", "")
        fast_text = s.get("fast_text", "")
        final_text = s.get("text", "")

        if human_reviewed:
            text_cell_html = f"""
                <textarea class="final-editor reviewed-editor" data-index="{idx}" disabled>{html.escape(final_text)}</textarea>
            """

            status_html = f"""
                {badge_html}
                
            """

        elif similarity_percent == 100:
            text_cell_html = f"""
                <textarea class="final-editor" data-index="{idx}">{html.escape(final_text)}</textarea>
            """

            status_html = f"""
                {badge_html}
                
            """

        else:
            slow_highlighted, fast_highlighted = highlight_differences(slow_text, fast_text)

            status_html = f"""
                {badge_html}
                <div class="status-content">
                    <div class="meta">
                        <span class="meta-reason">{html.escape(s.get("review_reason", ""))}</span>
                    </div>

                    <div class="version-label">Transcripción lenta</div>
                    <div class="text-slow">{slow_highlighted}</div>

                    <div class="version-label">Transcripción rápida</div>
                    <div class="text-fast">{fast_highlighted}</div>
                </div>
            """

            text_cell_html = f"""
                <textarea class="final-editor" data-index="{idx}">{html.escape(final_text)}</textarea>
            """
        rows += f"""
        <tr
            class="{row_class} segment-row"
            id="row-{idx}"
            data-index="{idx}"
            data-start="{s['start']}"
            data-end="{s['end']}"
            tabindex="0"
        >
            <td class="time-cell">
                <div class="time-start">
                    <span class="time-label">Inicio</span>
                    <strong>{format_time(s['start'])}</strong>
                </div>

                <div class="time-end">
                    <span class="time-label">Fin</span>
                    <strong>{format_time(s['end'])}</strong>
                </div>
            </td>

            <td class="speaker-cell">
                <span 
                    class="speaker-pill segment-speaker"
                    data-original-speaker="{html.escape(speaker)}"
                    style="background-color: {speaker_color};"
                >
                    {html.escape(visible_speaker)}
                </span>
            </td>

            <td class="text-cell">
                {text_cell_html}
            </td>

            <td class="status-cell">
                {status_html}
            </td>

            <td class="actions-cell">
                <button class="action-btn" onclick="playSegment({idx})">▶</button>
                {'' if human_reviewed else f'<button class="action-btn reviewed-btn" onclick="markAsReviewed({idx})">Revisado</button>'}
            </td>
        </tr>
        """

        if total_duration > 0:
            left = (s["start"] / total_duration) * 100

            if human_reviewed:
                marker_class = "marker human-marker"
            elif review_needed:
                marker_class = "marker review-marker"
            else:
                marker_class = "marker ai-marker"

            markers.append(
                f'<div class="{marker_class}" id="marker-{idx}" style="left:{left:.3f}%;" onclick="playSegment({idx})"></div>'
            )

            speaker_markers.append(
                f'''
                <div
                    class="speaker-marker"
                    id="speaker-marker-{idx}"
                    style="left:{left:.3f}%; background-color:{speaker_color};"
                    title="{html.escape(visible_speaker)}"
                    onclick="playSegment({idx})"
                ></div>
                '''
            )

    markers_html = "".join(markers)

    speaker_markers_html = "".join(speaker_markers)

    html_content = f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Editor de transcripción</title>

<style>
* {{
    box-sizing: border-box;
}}

body {{
    font-family: Arial, sans-serif;
    margin: 0;
    background: #eef2f7;
    color: #2e3b52;
}}

.pdf-generating-message {{
    display: none;
    position: fixed;
    top: 72px;
    right: 24px;
    z-index: 3500;
    background: #304463;
    color: white;
    padding: 12px 16px;
    border-radius: 10px;
    font-weight: 800;
    box-shadow: 0 8px 22px rgba(0,0,0,0.22);
}}

.pdf-generating-message.visible {{
    display: block;
}}

.keyboard-help-btn {{
    position: fixed;
    top: 17px;
    left: 20px;
    z-index: 2500;
    width: 38px;
    height: 38px;
    border-radius: 50%;
    border: 1px solid rgba(255,255,255,0.45);
    background: rgba(255,255,255,0.18);
    color: white;
    font-size: 20px;
    font-weight: 900;
    cursor: pointer;
    box-shadow: 0 4px 12px rgba(0,0,0,0.18);
}}

.keyboard-help-btn:hover {{
    background: rgba(255,255,255,0.30);
}}

.keyboard-help-modal {{
    display: none;
    position: fixed;
    inset: 0;
    z-index: 3000;
    background: rgba(15, 23, 42, 0.45);
    align-items: flex-start;
    justify-content: flex-start;
    padding: 70px 0 0 20px;
}}

.keyboard-help-modal.open {{
    display: flex;
}}

.keyboard-help-box {{
    width: 440px;
    max-width: calc(100vw - 40px);
    background: white;
    color: #2e3b52;
    border-radius: 14px;
    box-shadow: 0 16px 36px rgba(0,0,0,0.22);
    border: 1px solid #dbe3ee;
    overflow: hidden;
}}

.keyboard-help-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    padding: 18px 20px;
    background: #f7faff;
    border-bottom: 1px solid #e1e8f2;
}}

.keyboard-help-header h2 {{
    margin: 0;
    font-size: 20px;
    color: #304463;
}}

.keyboard-help-close {{
    border: none;
    background: transparent;
    font-size: 28px;
    line-height: 1;
    cursor: pointer;
    color: #66758a;
}}

.keyboard-help-close:hover {{
    color: #304463;
}}

.keyboard-help-content {{
    padding: 16px 20px 20px 20px;
}}

.shortcut-row {{
    display: grid;
    grid-template-columns: 150px 1fr;
    gap: 12px;
    align-items: center;
    padding: 10px 0;
    border-bottom: 1px solid #edf2f7;
}}

.shortcut-row:last-child {{
    border-bottom: none;
}}

.shortcut-key {{
    display: inline-block;
    background: #eef4ff;
    color: #2f63c6;
    border: 1px solid #d4e2ff;
    border-radius: 8px;
    padding: 6px 8px;
    font-weight: 800;
    font-size: 13px;
    text-align: center;
}}

.top-player {{
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 1000;
    background: #5e7394;
    color: white;
    padding: 16px 22px 18px 76px;
    box-shadow: 0 4px 14px rgba(0,0,0,0.15);
}}

.top-player-inner {{
    max-width: 1280px;
    margin: 0 auto;
}}

.speaker-map-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 20px;
    margin-bottom: 16px;
}}

.speaker-map-header h2 {{
    margin: 0 0 8px 0;
}}

.speaker-map-header p {{
    margin: 0;
}}

.pdf-btn {{
    text-decoration: none;
    background: #3f7ad9;
    color: white;
    border: 1px solid #326bc8;
    padding: 10px 14px;
    border-radius: 10px;
    font-weight: 800;
    white-space: nowrap;
    margin-top: 8px;
}}

.pdf-btn:hover {{
    background: #326bc8;
}}

audio {{
    width: 100%;
}}

.timeline-wrapper {{
    position: relative;
    margin-top: 10px;
    height: 24px;
    background: rgba(255,255,255,0.16);
    border-radius: 8px;
    overflow: hidden;
}}

.speaker-timeline-wrapper {{
    position: relative;
    margin-top: 8px;
    height: 18px;
    background: rgba(255,255,255,0.10);
    border-radius: 999px;
    overflow: hidden;
}}

.speaker-marker {{
    position: absolute;
    top: 4px;
    width: 10px;
    height: 10px;
    transform: translateX(-50%);
    border-radius: 50%;
    cursor: pointer;
    border: 1px solid rgba(0, 0, 0, 0.25);
    box-shadow: 0 0 0 1px rgba(255,255,255,0.35);
}}

.speaker-marker.active {{
    width: 14px;
    height: 14px;
    top: 2px;
    border: 2px solid white;
    box-shadow: 0 0 0 2px rgba(255,255,255,0.25);
}}

.marker {{
    position: absolute;
    top: 3px;
    width: 3px;
    height: 18px;
    border-radius: 2px;
    cursor: pointer;
    opacity: 0.9;
}}

.ai-marker {{
    background: #9bbcff;
}}

.review-marker {{
    background: #ffd166;
}}

.human-marker {{
    background: #55b87a;
}}

.marker.active {{
    width: 6px;
    background: #ffffff;
    box-shadow: 0 0 0 2px rgba(255,255,255,0.25);
}}

.page {{
    max-width: 1280px;
    margin: 0 auto;
    padding: 150px 20px 40px 20px;
}}

.editor-card {{
    margin-top: 150px;
    background: white;
    border-radius: 14px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.06);
    border: 1px solid #dbe3ee;
    overflow: hidden;
}}

.editor-header {{
    padding: 22px 24px;
    border-bottom: 1px solid #e6edf5;
}}

.editor-header h1 {{
    margin: 0;
    color: #304463;
}}

table {{
    border-collapse: collapse;
    width: 100%;
    background: white;
}}

td, th {{
    border-bottom: 1px solid #e7edf5;
    padding: 12px;
    vertical-align: top;
}}

th {{
    background: #f7faff;
    text-align: left;
    color: #65758c;
}}

td[contenteditable] {{
    background: #fbfcfe;
    min-width: 320px;
}}

.row-ai-consistent {{
    background: #eef4ff;
}}

.row-ai-consistent td {{
    background: #eef4ff;
}}

.row-ai-inconsistent {{
    background: #fff3bf;
}}

.row-ai-inconsistent td {{
    background: #fff3bf;
}}

.row-human-reviewed {{
    background: #e7f7ed;
}}

.row-human-reviewed td {{
    background: #e7f7ed;
}}

.segment-row.active-row {{
    outline: 3px solid #4b79cf;
    outline-offset: -3px;
}}

.segment-row:focus {{
    outline: 3px solid #2f63c6;
    outline-offset: -3px;
}}

.badge {{
    display: inline-block;
    padding: 5px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: bold;
    margin-bottom: 8px;
}}

.badge-ai-consistent {{
    background: #3f7ad9;
    color: white;
}}

.badge-ai-inconsistent {{
    background: #e9b949;
    color: white;
}}

.badge-human-reviewed {{
    background: #55b87a;
    color: white;
}}

.review-box {{
    margin-top: 6px;
    font-size: 12px;
    line-height: 1.6;
    color: #56677f;
    max-width: 460px;
}}

.speaker-pill {{
    display: inline-block;
    padding: 6px 10px;
    border-radius: 999px;
    color: #111827;
    font-size: 12px;
    font-weight: 800;
    white-space: nowrap;
    border: 1px solid rgba(0, 0, 0, 0.18);
}}

.speaker-jump-btn {{
    border: none;
    background: transparent;
    padding: 0;
    cursor: pointer;
}}

.speaker-jump-btn:hover .speaker-pill {{
    filter: brightness(0.92);
}}

.speaker-jump-btn {{
    border: none;
    background: transparent;
    padding: 0;
    cursor: pointer;
}}


.speaker-map-box {{
    padding: 20px 24px;
    border-bottom: 1px solid #e6edf5;
    background: #fbfdff;
}}

.speaker-map-box h2 {{
    margin: 0 0 8px 0;
    color: #304463;
    font-size: 20px;
}}

.speaker-map-box p {{
    margin: 0;
    color: #66758a;
    font-size: 14px;
}}

.speaker-map-table {{
    max-width: 620px;
}}

.speaker-map-table td,
.speaker-map-table th {{
    padding: 10px 12px;
}}

.speaker-name-input {{
    width: 100%;
    padding: 9px 11px;
    border-radius: 8px;
    border: 1px solid #d7e0ea;
    font-size: 14px;
}}

.segment-speaker {{
    transition: background 0.2s ease, color 0.2s ease;
}}

.sim-pill {{
    display: inline-block;
    padding: 4px 8px;
    border-radius: 999px;
    font-weight: bold;
    font-size: 12px;
}}

.sim-good {{
    background: #e7f7ed;
    color: #207245;
}}

.sim-medium {{
    background: #fff4d8;
    color: #9a6b00;
}}

.sim-bad {{
    background: #fdeaea;
    color: #b53a3a;
}}

.sim-neutral {{
    background: #eef2f7;
    color: #607086;
}}

.action-btn {{
    cursor: pointer;
    margin-right: 6px;
    border: 1px solid #d7e0ea;
    background: #f7faff;
    border-radius: 8px;
    padding: 7px 10px;
}}

.note {{
    padding: 20px 24px;
    color: #66758a;
    font-size: 14px;
    border-top: 1px solid #e6edf5;
    background: #fbfdff;
}}

.text-slow {{
    font-weight: 600;
    color: #2e3b52;
    margin-bottom: 4px;
}}

.text-fast {{
    font-size: 13px;
    color: #7a8aa3;
    margin-bottom: 6px;
}}

.text-final {{
    font-weight: 600;
    color: #2e3b52;
    font-size: 14px;
    line-height: 1.6;
}}

.version-label {{
    font-size: 11px;
    font-weight: bold;
    color: #8390a5;
    text-transform: uppercase;
    margin-top: 6px;
    margin-bottom: 2px;
}}

.diff-word {{
    font-weight: 800;
    color: #1f2d3d;
    background: rgba(233, 185, 73, 0.35);
    padding: 1px 3px;
    border-radius: 4px;
}}

.meta {{
    display: flex;
    gap: 8px;
    align-items: center;
    font-size: 12px;
}}

.meta-reason {{
    color: #8a98ad;
}}

.final-editor {{
    width: 100%;
    min-height: 80px;
    resize: none;
    border: 1px solid #d7e0ea;
    border-radius: 10px;
    padding: 10px 12px;
    font-family: Arial, sans-serif;
    font-size: 18px;
    line-height: 1.5;
    color: #2e3b52;
    background: #fbfcfe;
    margin-bottom: 10px;
}}

.final-editor:focus {{
    outline: 2px solid #8fb4f2;
    background: #ffffff;
}}

.time-cell {{
    width: 120px;
    min-width: 120px;
}}

.time-cell {{
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    min-height: 150px;
    gap: 24px;
}}

.time-start,
.time-end {{
    display: flex;
    flex-direction: column;
    gap: 4px;
}}

.time-label {{
    font-size: 11px;
    color: #8390a5;
    text-transform: uppercase;
    font-weight: 800;
}}

.speaker-cell {{
    width: 150px;
    min-width: 150px;
}}

.text-cell {{
    width: 42%;
    min-width: 340px;
}}

.status-cell {{
    width: 34%;
    min-width: 300px;
}}

.actions-cell {{
    width: 120px;
    min-width: 120px;
    white-space: nowrap;
}}

.status-content {{
    margin-top: 8px;
    font-size: 13px;
    line-height: 1.55;
    color: #56677f;
}}

.status-summary {{
    margin-bottom: 8px;
    color: #56677f;
}}


.reviewed-editor {{
    background: #eef7f1;
    color: #2e3b52;
}}

.text-slow,
.text-fast {{
    padding: 8px 10px;
    border-radius: 8px;
    background: rgba(255,255,255,0.55);
    margin-bottom: 8px;
}}

.text-slow {{
    font-weight: 600;
    color: #2e3b52;
}}

.text-fast {{
    color: #596a82;
}}

</style>
</head>

<body>

<button class="keyboard-help-btn" onclick="openKeyboardHelp()" title="Ver atajos de teclado">
    ?
</button>

<div class="keyboard-help-modal" id="keyboardHelpModal">
    <div class="keyboard-help-box">
        <div class="keyboard-help-header">
            <h2>Atajos de teclado</h2>
            <button class="keyboard-help-close" onclick="closeKeyboardHelp()">×</button>
        </div>

        <div class="keyboard-help-content">
            <div class="shortcut-row">
                <span class="shortcut-key">Alt + ↓ / →</span>
                <span>Ir al siguiente segmento</span>
            </div>

            <div class="shortcut-row">
                <span class="shortcut-key">Alt + ↑ / ←</span>
                <span>Ir al segmento anterior</span>
            </div>

            <div class="shortcut-row">
                <span class="shortcut-key">Ctrl + ↓ / →</span>
                <span>Ir al siguiente segmento no revisado</span>
            </div>

            <div class="shortcut-row">
                <span class="shortcut-key">Ctrl + ↑ / ←</span>
                <span>Ir al segmento no revisado anterior</span>
            </div>

            <div class="shortcut-row">
                <span class="shortcut-key">P</span>
                <span>Reproducir el segmento seleccionado</span>
            </div>

            <div class="shortcut-row">
                <span class="shortcut-key">E</span>
                <span>Editar el texto del segmento seleccionado</span>
            </div>

            <div class="shortcut-row">
                <span class="shortcut-key">Esc</span>
                <span>Cerrar esta ayuda</span>
            </div>
        </div>
    </div>
</div>

<div class="pdf-generating-message" id="pdfGeneratingMessage">
    Generando acta PDF...
</div>

<div class="top-player">
    <div class="top-player-inner">
        <audio id="media" controls src="{audio_path}"></audio>

        <div class="timeline-wrapper" id="timeline">
            {markers_html}
        </div>

        <div class="speaker-timeline-wrapper" id="speakerTimeline">
            {speaker_markers_html}
        </div>
    </div>
</div>

<div class="editor-card">
    <div class="editor-header">
        <h1>Editor de transcripción</h1>
    </div>

   <div class="speaker-map-box">
        <div class="speaker-map-header">
            <div>
                <h2>Identificación de hablantes</h2>
                <p>
                    Cambia el nombre de cada hablante detectado automáticamente.
                    Los cambios se aplican a todos los segmentos de la tabla.
                </p>
            </div>

            <a
                href="/acta_pdf/__JOB_ID__"
                class="pdf-btn"
                target="_blank"
                onclick="showPdfGeneratingMessage()"
            >
                Generar acta PDF
            </a>
        </div>

        <table class="speaker-map-table">
            <tr>
                <th>Hablante detectado</th>
                <th>Nombre real</th>
            </tr>
            {speaker_rows}
        </table>
    </div>

    <table>
            <tr>
                <th>Tiempo</th>
                <th>Hablante</th>
                <th>Texto</th>
                <th>Estado</th>
                <th>Acciones</th>
            </tr>
            {rows}
        </table>

        <div class="note">
           Azul = IA consistente. Amarillo = IA inconsistente. Verde = humano comprobado. La columna de hablante indica el locutor estimado automáticamente por diarización.
        </div>
    </div>
</div>

<script>
const media = document.getElementById("media");
const jobId = "__JOB_ID__";
const rows = Array.from(document.querySelectorAll(".segment-row"));
let stopTimer = null;

function logAppEvent(module, action, shortcut = "", details = {{}}) {{
    fetch("/log_event", {{
        method: "POST",
        headers: {{
            "Content-Type": "application/json"
        }},
        body: JSON.stringify({{
            module: module,
            action: action,
            job_id: jobId,
            shortcut: shortcut,
            details: details
        }})
    }}).catch(() => {{
        // No bloqueamos la interfaz si falla el log
    }});
}}

let activeSegmentIndex = rows.length > 0 ? parseInt(rows[0].dataset.index, 10) : null;

function showPdfGeneratingMessage() {{
    logAppEvent("pdf", "pdf_button_clicked");
    const message = document.getElementById("pdfGeneratingMessage");

    if (!message) return;

    message.classList.add("visible");

    setTimeout(() => {{
        message.classList.remove("visible");
    }}, 5000);
}}

function autoResizeTextarea(textarea) {{
    if (!textarea) return;

    textarea.style.height = "auto";
    textarea.style.height = textarea.scrollHeight + "px";
}}

function autoResizeAllTextareas() {{
    document.querySelectorAll(".final-editor").forEach((textarea) => {{
        autoResizeTextarea(textarea);

        textarea.addEventListener("input", () => {{
            autoResizeTextarea(textarea);
        }});
    }});
}}

const keyboardHelpModal = document.getElementById("keyboardHelpModal");

function openKeyboardHelp() {{
    if (keyboardHelpModal) {{
        keyboardHelpModal.classList.add("open");
    }}
}}

function closeKeyboardHelp() {{
    if (keyboardHelpModal) {{
        keyboardHelpModal.classList.remove("open");
    }}
}}

if (keyboardHelpModal) {{
    keyboardHelpModal.addEventListener("click", (event) => {{
        if (event.target === keyboardHelpModal) {{
            closeKeyboardHelp();
        }}
    }});
}}

function setActiveSegment(index, shouldFocus = false) {{
    const numericIndex = parseInt(index, 10);

    rows.forEach(row => row.classList.remove("active-row"));
    document.querySelectorAll(".marker").forEach(m => m.classList.remove("active"));
    document.querySelectorAll(".speaker-marker").forEach(m => m.classList.remove("active"));
    
    const row = document.getElementById(`row-${{numericIndex}}`);
    const marker = document.getElementById(`marker-${{numericIndex}}`);
    const speakerMarker = document.getElementById(`speaker-marker-${{numericIndex}}`);
    
    if (row) {{
        row.classList.add("active-row");
        activeSegmentIndex = numericIndex;

        if (shouldFocus) {{
            row.focus({{ preventScroll: true }});
        }}
    }}

    if (marker) {{
        marker.classList.add("active");
    }}

    if (speakerMarker) {{
        speakerMarker.classList.add("active");
    }}
}}

function scrollToSegment(index) {{
    const row = document.getElementById(`row-${{index}}`);

    if (!row) return;

    row.scrollIntoView({{
        behavior: "smooth",
        block: "center"
    }});
}}

function getCurrentRowPosition() {{
    if (activeSegmentIndex === null && rows.length > 0) {{
        return 0;
    }}

    const currentPosition = rows.findIndex(row => {{
        return parseInt(row.dataset.index, 10) === activeSegmentIndex;
    }});

    return currentPosition >= 0 ? currentPosition : 0;
}}

function goToSegmentByPosition(position) {{
    if (rows.length === 0) return;

    const safePosition = Math.max(0, Math.min(position, rows.length - 1));
    const row = rows[safePosition];
    const index = parseInt(row.dataset.index, 10);

    setActiveSegment(index, true);
    scrollToSegment(index);
}}

function goToNextSegment() {{
    goToSegmentByPosition(getCurrentRowPosition() + 1);
}}

function goToPreviousSegment() {{
    goToSegmentByPosition(getCurrentRowPosition() - 1);
}}

function isReviewedRow(row) {{
    return row.classList.contains("row-human-reviewed");
}}

function goToNextUnreviewedSegment() {{
    const currentPosition = getCurrentRowPosition();

    for (let i = currentPosition + 1; i < rows.length; i++) {{
        if (!isReviewedRow(rows[i])) {{
            const index = parseInt(rows[i].dataset.index, 10);
            setActiveSegment(index, true);
            scrollToSegment(index);
            return;
        }}
    }}

    alert("No hay más segmentos pendientes de revisar.");
}}

function goToPreviousUnreviewedSegment() {{
    const currentPosition = getCurrentRowPosition();

    for (let i = currentPosition - 1; i >= 0; i--) {{
        if (!isReviewedRow(rows[i])) {{
            const index = parseInt(rows[i].dataset.index, 10);
            setActiveSegment(index, true);
            scrollToSegment(index);
            return;
        }}
    }}

    alert("No hay segmentos pendientes anteriores.");
}}

function playActiveSegment() {{
    if (activeSegmentIndex === null) return;

    playSegment(activeSegmentIndex);
}}

function focusActiveSegmentEditor() {{
    if (activeSegmentIndex === null) return;

    const row = document.getElementById(`row-${{activeSegmentIndex}}`);
    if (!row) return;

    const editor = row.querySelector(".final-editor");

    if (editor) {{
        editor.focus();
        editor.setSelectionRange(editor.value.length, editor.value.length);
    }}
}}


function playSegment(index) {{
        logAppEvent("editor", "play_segment", "", {{
            segment_index: index
        }});

    const row = document.getElementById(`row-${{index}}`);
    const start = parseFloat(row.dataset.start);
    const end = parseFloat(row.dataset.end);

    setActiveSegment(index);
    media.currentTime = start;
    media.play();

    row.scrollIntoView({{ behavior: "smooth", block: "center" }});

    if (stopTimer) {{
        clearInterval(stopTimer);
    }}

    stopTimer = setInterval(() => {{
        if (media.currentTime >= end) {{
            media.pause();
            clearInterval(stopTimer);
        }}
    }}, 100);
}}

async function markAsReviewed(index) {{
    const row = document.getElementById(`row-${{index}}`);
    const marker = document.getElementById(`marker-${{index}}`);

    if (!row) return;

    const editor = row.querySelector(".final-editor");
    const reviewedText = editor ? editor.value.trim() : "";

    if (!reviewedText) {{
        alert("El texto revisado no puede estar vacío.");
        return;
    }}

    const button = row.querySelector(".reviewed-btn");
    if (button) {{
        button.disabled = true;
        button.textContent = "Guardando...";
    }}

    try {{
        const response = await fetch(`/review_segment/${{jobId}}/${{index}}`, {{
            method: "POST",
            headers: {{
                "Content-Type": "application/json"
            }},
            body: JSON.stringify({{
                text: reviewedText
            }})
        }});

        const data = await response.json();

        if (!response.ok || !data.ok) {{
            throw new Error(data.error || "No se ha podido guardar el segmento");
        }}

        row.classList.remove("row-ai-consistent");
        row.classList.remove("row-ai-inconsistent");
        row.classList.add("row-human-reviewed");

        const badge = row.querySelector(".badge");
        if (badge) {{
            badge.classList.remove("badge-ai-consistent");
            badge.classList.remove("badge-ai-inconsistent");
            badge.classList.add("badge-human-reviewed");

            const reviewedAt = data.reviewed_at || "";

            badge.textContent = reviewedAt
                ? `Humano comprobado · ${{reviewedAt}}`
                : "Humano comprobado";
                    }}

        if (marker) {{
            marker.classList.remove("ai-marker");
            marker.classList.remove("review-marker");
            marker.classList.add("human-marker");
        }}

        const statusCell = row.querySelector(".status-cell");
            
        if (statusCell) {{
            const oldBadgeText = badge ? badge.textContent : "Humano comprobado";

            statusCell.innerHTML = `
                <span class="badge badge-human-reviewed">${{oldBadgeText}}</span>
            `;
        }}

        if (editor) {{
            editor.value = reviewedText;
            editor.disabled = true;
            editor.classList.add("reviewed-editor");
            autoResizeTextarea(editor);
        }}
        if (button) {{
            button.remove();
        }}

    }} catch (error) {{
        alert(error.message);

        if (button) {{
            button.disabled = false;
            button.textContent = "Revisado";
        }}
    }}
}}

document.addEventListener("keydown", (event) => {{
    const key = event.key;
    const target = event.target;

    if (key === "Escape") {{
        closeKeyboardHelp();
        return;
    }}

    const isTyping =
        target.tagName === "TEXTAREA" ||
        target.tagName === "INPUT" ||
        target.isContentEditable;

    const isNextArrow = key === "ArrowDown" || key === "ArrowRight";
    const isPreviousArrow = key === "ArrowUp" || key === "ArrowLeft";

    if (event.altKey && isNextArrow) {{
        event.preventDefault();
        logAppEvent("keyboard", "shortcut_used", `Alt+${{key}}`, {{
            meaning: "next_segment"
        }});
        goToNextSegment();
        return;
    }}

    if (event.altKey && isPreviousArrow) {{
        event.preventDefault();
        logAppEvent("keyboard", "shortcut_used", `Alt+${{key}}`, {{
            meaning: "previous_segment"
        }});
        goToPreviousSegment();
        return;
    }}

    if (event.ctrlKey && isNextArrow) {{
        event.preventDefault();
        logAppEvent("keyboard", "shortcut_used", `Ctrl+${{key}}`, {{
            meaning: "next_unreviewed_segment"
        }});
        goToNextUnreviewedSegment();
        return;
    }}

    if (event.ctrlKey && isPreviousArrow) {{
        event.preventDefault();
        logAppEvent("keyboard", "shortcut_used", `Ctrl+${{key}}`, {{
            meaning: "previous_unreviewed_segment"
        }});
        goToPreviousUnreviewedSegment();
        return;
    }}

    if (isTyping) {{
        return;
    }}

    if (key.toLowerCase() === "p") {{
        event.preventDefault();
        logAppEvent("keyboard", "shortcut_used", "P", {{
            meaning: "play_active_segment",
            active_segment_index: activeSegmentIndex
        }});
        playActiveSegment();
        return;
    }}

    if (key.toLowerCase() === "e") {{
        event.preventDefault();
        logAppEvent("keyboard", "shortcut_used", "E", {{
            meaning: "edit_active_segment",
            active_segment_index: activeSegmentIndex
        }});
        focusActiveSegmentEditor();
        return;
    }}
}});

rows.forEach((row) => {{
    row.addEventListener("click", () => {{
        const index = row.dataset.index;
        setActiveSegment(index);
    }});

    row.addEventListener("focus", () => {{
        const index = row.dataset.index;
        setActiveSegment(index);
    }});

    row.addEventListener("mouseenter", () => {{
        const index = row.dataset.index;
        setActiveSegment(index);
    }});
}});

if (rows.length > 0) {{
    setActiveSegment(rows[0].dataset.index);
}}

autoResizeAllTextareas();

function jumpToFirstSpeakerSegment(originalSpeaker) {{
    const firstSpeakerElement = document.querySelector(
        `.segment-speaker[data-original-speaker="${{originalSpeaker}}"]`
    );

    if (!firstSpeakerElement) {{
        alert("No se ha encontrado ningún segmento para este hablante.");
        return;
    }}

    const row = firstSpeakerElement.closest(".segment-row");

    if (!row) return;

    const index = row.dataset.index;

    setActiveSegment(index);

    row.scrollIntoView({{
        behavior: "smooth",
        block: "center"
    }});
}}

const speakerNameInputs = Array.from(document.querySelectorAll(".speaker-name-input"));
const speakerJumpButtons = Array.from(document.querySelectorAll(".speaker-jump-btn"));

function updateSpeakerName(originalSpeaker, newName) {{
    const cleanName = newName.trim();
    const visibleName = cleanName || originalSpeaker;

    document
        .querySelectorAll(`.segment-speaker[data-original-speaker="${{originalSpeaker}}"]`)
        .forEach((speakerElement) => {{
            speakerElement.textContent = visibleName;
        }});
}}

function jumpToFirstSpeakerSegment(originalSpeaker) {{
    const firstSpeakerElement = document.querySelector(
        `.segment-speaker[data-original-speaker="${{originalSpeaker}}"]`
    );

    if (!firstSpeakerElement) {{
        alert("No se ha encontrado ningún segmento para este hablante.");
        return;
    }}

    const row = firstSpeakerElement.closest(".segment-row");

    if (!row) return;

    const index = row.dataset.index;

    setActiveSegment(index);

    row.scrollIntoView({{
        behavior: "smooth",
        block: "center"
    }});
}}

async function saveSpeakerName(originalSpeaker, newName) {{
     logAppEvent("speakers", "speaker_name_change_requested", "", {{
        original_speaker: originalSpeaker,
        new_name: newName.trim()
    }});
    const response = await fetch(`/update_speaker_name/${{jobId}}`, {{
        method: "POST",
        headers: {{
            "Content-Type": "application/json"
        }},
        body: JSON.stringify({{
            speaker: originalSpeaker,
            name: newName.trim()
        }})
    }});

    const data = await response.json();

    if (!response.ok || !data.ok) {{
        throw new Error(data.error || "No se ha podido guardar el nombre del hablante");
    }}

    return data;
}}

speakerJumpButtons.forEach((button) => {{
    button.addEventListener("click", () => {{
        const originalSpeaker = button.dataset.speaker;
        jumpToFirstSpeakerSegment(originalSpeaker);
    }});
}});

speakerNameInputs.forEach((input) => {{
    input.addEventListener("input", () => {{
        const originalSpeaker = input.dataset.speaker;
        updateSpeakerName(originalSpeaker, input.value);
    }});

    input.addEventListener("change", async () => {{
        const originalSpeaker = input.dataset.speaker;

        try {{
            await saveSpeakerName(originalSpeaker, input.value);
        }} catch (error) {{
            alert(error.message);
        }}
    }});
}});
</script>

</body>
</html>
"""

    html_content = html_content.replace("__JOB_ID__", html.escape(job_id or ""))

    with open(output, "w", encoding="utf-8") as f:
        f.write(html_content)
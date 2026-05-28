import json
import html
import re
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

    speakers = sorted({
    s.get("speaker", "SPEAKER_UNKNOWN")
    for s in segments
    if s.get("speaker", "SPEAKER_UNKNOWN")
})

    speaker_rows = ""

    for speaker in speakers:
        speaker_rows += f"""
            <tr>
                <td>
                    <span class="speaker-pill">{html.escape(speaker)}</span>
                </td>
                <td>
                    <input
                        class="speaker-name-input"
                        data-speaker="{html.escape(speaker)}"
                        placeholder="Nombre"
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
            badge_html = '<span class="badge badge-human-reviewed">Humano comprobado</span>'
        elif review_needed:
            row_class = "row-ai-inconsistent"
            badge_html = '<span class="badge badge-ai-inconsistent">IA inconsistente</span>'
        else:
            row_class = "row-ai-consistent"
            badge_html = '<span class="badge badge-ai-consistent">IA consistente</span>'

        slow_text = s.get("slow_text", "")
        fast_text = s.get("fast_text", "")
        final_text = s.get("text", "")

        if human_reviewed:
            details_html = f"""
                <div class="review-box single-transcription">
                    <div class="version-label">Texto revisado</div>
                    <div class="text-final reviewed-text">{html.escape(final_text)}</div>

                    <div class="meta">
                        <span class="sim-pill {similarity_class}">{similarity_label}</span>
                    </div>
                </div>
            """

        if similarity_percent == 100:
            details_html = f"""
                <div class="review-box single-transcription">
                    <div class="version-label">Texto final editable</div>
                    <textarea class="final-editor" data-index="{idx}">{html.escape(final_text)}</textarea>

                    <div class="meta">
                        <span class="sim-pill {similarity_class}">{similarity_label}</span>
                    </div>
                </div>
                """
        else:
            slow_highlighted, fast_highlighted = highlight_differences(slow_text, fast_text)

            details_html = f"""
                <div class="review-box">
                    <div class="version-label">Texto final editable</div>
                    <textarea class="final-editor" data-index="{idx}">{html.escape(final_text)}</textarea>

                    <div class="version-label">Comparación con transcripción lenta</div>
                    <div class="text-slow">{slow_highlighted}</div>

                    <div class="version-label">Comparación con transcripción rápida</div>
                    <div class="text-fast">{fast_highlighted}</div>

                    <div class="meta">
                        <span class="sim-pill {similarity_class}">{similarity_label}</span>
                        <span class="meta-reason">{html.escape(s.get("review_reason", ""))}</span>
                    </div>
                </div>
                """
        rows += f"""
        <tr class="{row_class} segment-row" id="row-{idx}" data-index="{idx}" data-start="{s['start']}" data-end="{s['end']}">
            <td>{format_time(s['start'])}</td>
            <td>{format_time(s['end'])}</td>
            <td>
                <span 
                    class="speaker-pill segment-speaker"
                    data-original-speaker="{html.escape(speaker)}"
                >
                    {html.escape(speaker)}</span>
            </td>
            <td>
                {badge_html}
                {details_html}
            </td>
            <td>
                <button class="action-btn" onclick="playSegment({idx})">▶</button>
                {'' if human_reviewed else f'<button class="action-btn reviewed-btn" onclick="markAsReviewed({idx})">Revisado</button>'}
            </td>
        </tr>
        """

        if total_duration > 0:
            left = (s["start"] / total_duration) * 100
            marker_class = "marker review-marker" if review_needed else "marker ai-marker"
            markers.append(
                f'<div class="{marker_class}" id="marker-{idx}" style="left:{left:.3f}%;" onclick="playSegment({idx})"></div>'
            )

    markers_html = "".join(markers)

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

.top-player {{
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 1000;
    background: #5e7394;
    color: white;
    padding: 16px 22px 18px 22px;
    box-shadow: 0 4px 14px rgba(0,0,0,0.15);
}}

.top-player-inner {{
    max-width: 1280px;
    margin: 0 auto;
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
    outline: 2px solid #4b79cf;
    outline-offset: -2px;
    background: #edf4ff;
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
    background: #eef4ff;
    color: #2f63c6;
    font-size: 12px;
    font-weight: 700;
    white-space: nowrap;
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
    margin: 0 0 16px 0;
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
    resize: vertical;
    border: 1px solid #d7e0ea;
    border-radius: 10px;
    padding: 10px 12px;
    font-family: Arial, sans-serif;
    font-size: 14px;
    line-height: 1.5;
    color: #2e3b52;
    background: #fbfcfe;
    margin-bottom: 10px;
}}

.final-editor:focus {{
    outline: 2px solid #8fb4f2;
    background: #ffffff;
}}

</style>
</head>

<body>

<div class="top-player">
    <div class="top-player-inner">
        <audio id="media" controls src="{audio_path}"></audio>
        <div class="timeline-wrapper" id="timeline">
            {markers_html}
        </div>
    </div>
</div>

<div class="editor-card">
    <div class="editor-header">
        <h1>Editor de transcripción</h1>
    </div>

    <div class="speaker-map-box">
        <h2>Identificación de hablantes</h2>
        <p>
            Cambia el nombre de cada hablante detectado automáticamente.
            Los cambios se aplican a todos los segmentos de la tabla.
        </p>

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
                <th>Inicio</th>
                <th>Fin</th>
                <th>Hablante</th>
                <th>Revisión</th>
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

function setActiveSegment(index) {{
    rows.forEach(row => row.classList.remove("active-row"));
    document.querySelectorAll(".marker").forEach(m => m.classList.remove("active"));

    const row = document.getElementById(`row-${{index}}`);
    const marker = document.getElementById(`marker-${{index}}`);

    if (row) row.classList.add("active-row");
    if (marker) marker.classList.add("active");
}}

function playSegment(index) {{
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
            badge.textContent = "Humano comprobado";
        }}

        if (marker) {{
            marker.classList.remove("ai-marker");
            marker.classList.remove("review-marker");
            marker.classList.add("human-marker");
        }}

        const reviewBox = row.querySelector(".review-box");
        if (reviewBox) {{
            reviewBox.innerHTML = `
                <div class="version-label">Texto revisado</div>
                <div class="text-final reviewed-text"></div>
            `;

            reviewBox.querySelector(".reviewed-text").textContent = reviewedText;
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

rows.forEach((row) => {{
    row.addEventListener("click", () => {{
        const index = row.dataset.index;
        setActiveSegment(index);
    }});

    row.addEventListener("mouseenter", () => {{
        const index = row.dataset.index;
        setActiveSegment(index);
    }});
}});

const speakerNameInputs = Array.from(document.querySelectorAll(".speaker-name-input"));

function updateSpeakerName(originalSpeaker, newName) {{
    const cleanName = newName.trim();
    const visibleName = cleanName || originalSpeaker;

    document
        .querySelectorAll(`.segment-speaker[data-original-speaker="${{originalSpeaker}}"]`)
        .forEach((speakerElement) => {{
            speakerElement.textContent = visibleName;
        }});
}}

speakerNameInputs.forEach((input) => {{
    input.addEventListener("input", () => {{
        const originalSpeaker = input.dataset.speaker;
        updateSpeakerName(originalSpeaker, input.value);
    }});
}});
</script>

</body>
</html>
"""

    html_content = html_content.replace("__JOB_ID__", html.escape(job_id or ""))

    with open(output, "w", encoding="utf-8") as f:
        f.write(html_content)
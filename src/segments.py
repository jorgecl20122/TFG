import json
import html

from numpy import size


def format_time(seconds):
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    milliseconds = int((seconds - int(seconds)) * 1000)

    return f"{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def save_segments_json(segments, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(segments, f, indent=2, ensure_ascii=False)


def generate_html(segments, audio_path, output):
    rows = ""
    markers = []

    total_duration = 0.0
    if segments:
        total_duration = max(s["end"] for s in segments)

    for idx, s in enumerate(segments):
        similarity_percent = s.get("similarity_percent", "")
        uncertain = s.get("uncertain", False)

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

        row_class = "row-review" if uncertain else "row-ok"

        badge_html = ""
        if uncertain:
            badge_html = '<span class="badge badge-review">Revisar</span>'
        else:
            badge_html = '<span class="badge badge-ok">Correcto</span>'

        details_html = f"""
            <div class="review-box">
                <div class="text-slow">{html.escape(s.get("slow_text", ""))}</div>
                <div class="text-fast">{html.escape(s.get("fast_text", ""))}</div>

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
                {badge_html}
                {details_html}
            </td>
            <td>
                <button class="action-btn" onclick="playSegment({idx})">▶</button>
                <button class="action-btn" onclick="deleteRow(this)">🗑</button>
            </td>
        </tr>
        """

        if total_duration > 0:
            left = (s["start"] / total_duration) * 100
            marker_class = "marker review-marker" if uncertain else "marker ok-marker"
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

.ok-marker {{
    background: #dbe7ff;
}}

.review-marker {{
    background: #ffd166;
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

.row-ok {{
    background: #ffffff;
}}

.row-review {{
    background: #fff8df;
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

.badge-review {{
    background: #e9b949;
    color: white;
}}

.badge-ok {{
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

.meta {{
    display: flex;
    gap: 8px;
    align-items: center;
    font-size: 12px;
}}

.meta-reason {{
    color: #8a98ad;
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

<div class="page">
    <div class="editor-card">
        <div class="editor-header">
            <h1>Editor de transcripción</h1>
        </div>

        <table>
            <tr>
                <th>Inicio</th>
                <th>Fin</th>
                <th>Revisión</th>
                <th>Acciones</th>
            </tr>
            {rows}
        </table>

        <div class="note">
            Verde = segmento estable. Amarillo o rojo = conviene revisar. La barra superior muestra marcas verticales para orientarte en toda la reunión.
        </div>
    </div>
</div>

<script>
const media = document.getElementById("media");
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

function deleteRow(btn) {{
    const row = btn.closest("tr");
    const index = row.dataset.index;
    const marker = document.getElementById(`marker-${{index}}`);

    if (marker) marker.remove();
    row.remove();
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
</script>

</body>
</html>
"""

    with open(output, "w", encoding="utf-8") as f:
        f.write(html_content)
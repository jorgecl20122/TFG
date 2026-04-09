import json
import html


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

    for s in segments:
        row_class = "uncertain-row" if s.get("uncertain") else ""

        badge_html = ""
        details_html = ""

        if s.get("uncertain"):
            badge_html = '<span class="badge">Revisar</span>'
            details_html = f"""
            <div class="review-box">
                <div><strong>Rápida:</strong> {html.escape(s.get("fast_text", ""))}</div>
                <div><strong>Lenta:</strong> {html.escape(s.get("slow_text", ""))}</div>
                <div><strong>Similitud:</strong> {s.get("similarity", "")}</div>
                <div><strong>Motivo:</strong> {html.escape(s.get("review_reason", ""))}</div>
                <div><strong>Segmentos rápida:</strong> {s.get("fast_count", "")}</div>
                <div><strong>Segmentos lenta:</strong> {s.get("slow_count", "")}</div>
            </div>
            """

        rows += f"""
        <tr class="{row_class}">
            <td>{format_time(s['start'])}</td>
            <td>{format_time(s['end'])}</td>
            <td contenteditable="true">{html.escape(s['text'])}</td>
            <td>
                {badge_html}
                {details_html}
            </td>
            <td>
                <button onclick="playSegment({s['start']}, {s['end']})">▶</button>
                <button onclick="deleteRow(this)">🗑</button>
            </td>
        </tr>
        """

    html_content = f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<title>Editor de transcripción</title>

<style>
body {{
    font-family: Arial, sans-serif;
    margin: 40px;
    background: #f7f8fa;
    color: #222;
}}

h1 {{
    margin-bottom: 20px;
}}

audio {{
    width: 100%;
    margin-bottom: 24px;
}}

table {{
    border-collapse: collapse;
    width: 100%;
    background: white;
}}

td, th {{
    border: 1px solid #ddd;
    padding: 10px;
    vertical-align: top;
}}

th {{
    background: #f0f3f7;
    text-align: left;
}}

td[contenteditable] {{
    background: #fafafa;
    min-width: 320px;
}}

button {{
    cursor: pointer;
    margin-right: 6px;
}}

.uncertain-row {{
    background: #fff6d8;
}}

.badge {{
    display: inline-block;
    background: #d97706;
    color: white;
    padding: 4px 8px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: bold;
    margin-bottom: 8px;
}}

.review-box {{
    margin-top: 6px;
    font-size: 12px;
    line-height: 1.5;
    color: #555;
    max-width: 420px;
}}

.note {{
    margin-top: 18px;
    color: #666;
    font-size: 14px;
}}
</style>
</head>

<body>

<h1>Editor de transcripción</h1>

<audio id="media" controls src="{audio_path}"></audio>

<table>
    <tr>
        <th>Inicio</th>
        <th>Fin</th>
        <th>Texto final</th>
        <th>Revisión</th>
        <th>Acciones</th>
    </tr>

    {rows}
</table>

<p class="note">
    Los fragmentos marcados como "Revisar" son segmentos donde la pasada rápida y la lenta no coinciden lo suficiente.
</p>

<script>
const media = document.getElementById("media");
let stopTimer = null;

function playSegment(start, end) {{
    media.currentTime = start;
    media.play();

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
    btn.parentElement.parentElement.remove();
}}
</script>

</body>
</html>
"""

    with open(output, "w", encoding="utf-8") as f:
        f.write(html_content)
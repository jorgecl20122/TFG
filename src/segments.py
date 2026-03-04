import json

def format_time(seconds):
    
    minutes = int(seconds // 60)
    secs = int(seconds % 60)
    centiseconds = int((seconds - int(seconds)) * 100)

    return f"{minutes:02d}:{secs:02d}:{centiseconds:02d}"

def save_segments_json(segments, path):

    with open(path, "w", encoding="utf-8") as f:
        json.dump(segments, f, indent=2, ensure_ascii=False)


def generate_html(segments, audio_path, output):

    rows = ""

    for s in segments:

        rows += f"""
        <tr>
        <td>{format_time(s['start'])}</td>
        <td>{format_time(s['end'])}</td>
        <td contenteditable="true">{s['text']}</td>
        <td>
            <button onclick="playSegment({s['start']}, {s['end']})">▶</button>
            <button onclick="deleteRow(this)">🗑</button>
        </td>
        </tr>
        """

    html = f"""
<!DOCTYPE html>
<html>
<head>

<meta charset="utf-8">
<title>Editor de transcripción</title>

<style>

body {{font-family: Arial; margin:40px;}}

table {{border-collapse: collapse; width:100%;}}

td,th {{
border:1px solid #ddd;
padding:8px;
}}

td[contenteditable] {{
background:#fafafa;
}}

button {{
cursor:pointer;
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
<th>Texto</th>
<th>Acciones</th>
</tr>

{rows}

</table>

<script>

const media = document.getElementById("media");

let stopTimer=null;

function playSegment(start,end){{
    
    media.currentTime=start;
    media.play();

    if(stopTimer) clearInterval(stopTimer)

    stopTimer=setInterval(()=>{{
        if(media.currentTime>=end){{
            media.pause()
            clearInterval(stopTimer)
        }}
    }},100)
}}

function deleteRow(btn){{
    btn.parentElement.parentElement.remove()
}}

</script>

</body>
</html>
"""

    with open(output, "w", encoding="utf-8") as f:
        f.write(html)
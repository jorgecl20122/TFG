from transcriber import transcribe_audio
from segments import save_segments_json, generate_html
import os

audio = "data/audio/reunion.mp3"

segments = transcribe_audio(audio)

os.makedirs("data/out", exist_ok=True)

save_segments_json(segments, "data/out/segments.json")

generate_html(
    segments,
    "../audio/reunion.mp3",
    "data/out/editor.html"
)

print("Transcripción generada.")
print("Abre data/out/editor.html en tu navegador.")
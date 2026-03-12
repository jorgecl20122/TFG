from transcriber import transcribe_audio
from segments import save_segments_json, generate_html
import os

def process_audio(audio_path, output_dir, web_audio_path):
    segments = transcribe_audio(audio_path)

    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, "segments.json")
    html_path = os.path.join(output_dir, "editor.html")

    save_segments_json(segments, json_path)

    generate_html(
        segments,
        web_audio_path,
        html_path
    )

    return{
        "segments": segments,
        "json_path": json_path,
        "html_path": html_path
    }

if __name__ == "__main__":
    audio = "data/audio/reunion.mp3"
    output_dir = "data/out"
    web_audio_path = "../audio/reunion.mp3"

    result = process_audio(audio, output_dir, web_audio_path)

    print("Transcripción generada.")
    print(f"HTML: {result['html_path']}")
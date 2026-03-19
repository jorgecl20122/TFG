from transcriber import (
    transcribe_fast,
    transcribe_slow,
    merge_and_flag_segments
)
from segments import save_segments_json, generate_html
import os


def process_audio(audio_path, output_dir, web_audio_path):
    fast_segments = transcribe_fast(audio_path)
    slow_segments = transcribe_slow(audio_path)
    final_segments = merge_and_flag_segments(fast_segments, slow_segments)

    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, "segments.json")
    html_path = os.path.join(output_dir, "editor.html")

    save_segments_json(final_segments, json_path)
    generate_html(final_segments, web_audio_path, html_path)

    return {
        "segments": final_segments,
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
from transcriber import (
    transcribe_fast,
    transcribe_slow,
    merge_and_flag_segments
)
from segments import save_segments_json, generate_html
from mutagen import File as MutagenFile
from diarization import detect_speakers, assign_speakers_to_segments

import os
import json
import time
import argparse


CONFIG_FOLDER = "data/config"
CALIBRATION_FILE = os.path.join(CONFIG_FOLDER, "calibration.json")


def get_audio_duration(path):
    audio = MutagenFile(path)

    if audio is None or not hasattr(audio, "info") or not hasattr(audio.info, "length"):
        raise ValueError("No se ha podido leer la duración del audio")

    return float(audio.info.length)


def load_calibration_factor():
    if not os.path.exists(CALIBRATION_FILE):
        return 0.27

    with open(CALIBRATION_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    return float(data.get("seconds_per_second", 0.27))


def format_duration(seconds):
    seconds = max(0, int(round(seconds)))
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes:02d}:{secs:02d}"


def process_audio(audio_path, output_dir, web_audio_path, job_id=None, require_diarization=False):
    fast_segments = transcribe_fast(audio_path)
    slow_segments = transcribe_slow(audio_path)
    final_segments = merge_and_flag_segments(fast_segments, slow_segments)

    try:
        speaker_segments = detect_speakers(audio_path)
        final_segments = assign_speakers_to_segments(
            final_segments,
            speaker_segments
        )
    except Exception as e:
        print("No se ha podido completar la diarización:", e)

        if require_diarization:
            raise RuntimeError(
                "La calibración no puede completarse porque ha fallado la diarización"
            ) from e

        for segment in final_segments:
            segment["speaker"] = "SPEAKER_UNKNOWN"

    os.makedirs(output_dir, exist_ok=True)

    json_path = os.path.join(output_dir, "segments.json")
    html_path = os.path.join(output_dir, "editor.html")

    save_segments_json(final_segments, json_path)
    generate_html(final_segments, web_audio_path, html_path, job_id=job_id)

    return {
        "segments": final_segments,
        "json_path": json_path,
        "html_path": html_path
    }


def main():
    parser = argparse.ArgumentParser(
        description="Procesa un audio y genera la transcripción en JSON y HTML."
    )

    parser.add_argument(
        "audio",
        help="Ruta del archivo de audio que se quiere transcribir"
    )

    parser.add_argument(
        "--output",
        default="data/out/cli",
        help="Carpeta donde se guardarán los resultados"
    )

    parser.add_argument(
        "--web-audio-path",
        default=None,
        help="Ruta del audio que usará el HTML generado. Si no se indica, se usa la ruta del audio original."
    )

    args = parser.parse_args()

    audio_path = args.audio
    output_dir = args.output
    web_audio_path = args.web_audio_path or audio_path

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"No existe el archivo de audio: {audio_path}")

    factor = load_calibration_factor()
    duration = get_audio_duration(audio_path)
    estimated_seconds = duration * factor

    print("Archivo:", audio_path)
    print("Duración del audio:", format_duration(duration))
    print("Velocidad estimada:", round(factor * 60, 1), "s/min")
    print("Tiempo estimado:", format_duration(estimated_seconds))
    print("Procesando...")

    start = time.perf_counter()

    result = process_audio(
        audio_path=audio_path,
        output_dir=output_dir,
        web_audio_path=web_audio_path
    )

    elapsed = time.perf_counter() - start

    print()
    print("Transcripción generada correctamente.")
    print("Tiempo real:", format_duration(elapsed))
    print("JSON:", result["json_path"])
    print("HTML:", result["html_path"])


if __name__ == "__main__":
    main()
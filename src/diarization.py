import os
from dotenv import load_dotenv
import warnings

warnings.filterwarnings(
    "ignore",
    message=".*torchcodec is not installed correctly.*"
)

warnings.filterwarnings(
    "ignore",
    message=".*degrees of freedom is <= 0.*"
)

_pipeline = None


def get_diarization_pipeline():
    global _pipeline

    if _pipeline is None:
        from pyannote.audio import Pipeline

        load_dotenv()
        hf_token = os.getenv("HF_TOKEN")

        if not hf_token:
            raise RuntimeError(
                "No se ha encontrado HF_TOKEN. Crea un archivo .env con HF_TOKEN=tu_token"
            )

        _pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            token=hf_token
        )

    return _pipeline

def load_audio_for_pyannote(audio_path):
    """
    Convierte el audio a WAV mono 16kHz y lo carga en memoria.
    Así evitamos torchcodec/torchaudio en Windows.
    """
    import os
    import tempfile
    import subprocess
    import numpy as np
    import torch
    import soundfile as sf

    temp_dir = tempfile.gettempdir()
    wav_path = os.path.join(temp_dir, "pyannote_input.wav")

    command = [
        "ffmpeg",
        "-y",
        "-i", audio_path,
        "-ac", "1",
        "-ar", "16000",
        wav_path
    ]

    subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=True
    )

    audio, sample_rate = sf.read(wav_path, dtype="float32")

    if audio.ndim == 1:
        waveform = torch.from_numpy(audio).unsqueeze(0)
    else:
        waveform = torch.from_numpy(audio.T)

    return {
        "waveform": waveform,
        "sample_rate": sample_rate
    }


def detect_speakers(audio_path, num_speakers=None, min_speakers=None, max_speakers=None):
    """
    Ejecuta diarización sobre un audio.

    Devuelve una lista simple:
    [
        {"start": 0.0, "end": 3.5, "speaker": "SPEAKER_00"},
        {"start": 3.5, "end": 7.2, "speaker": "SPEAKER_01"}
    ]
    """
    pipeline = get_diarization_pipeline()
    audio_input = load_audio_for_pyannote(audio_path)

    if num_speakers is not None:
        diarization = pipeline(audio_input, num_speakers=num_speakers)
    elif min_speakers is not None or max_speakers is not None:
        kwargs = {}

        if min_speakers is not None:
            kwargs["min_speakers"] = min_speakers

        if max_speakers is not None:
            kwargs["max_speakers"] = max_speakers

        diarization = pipeline(audio_input, **kwargs)
    else:
        diarization = pipeline(audio_input)

    speaker_segments = []

    speaker_segments = extract_speaker_segments(diarization)

    return speaker_segments

def extract_speaker_segments(diarization):
    """
    Extrae segmentos de hablantes de distintas versiones/formas de salida de pyannote.
    Algunas versiones devuelven directamente Annotation.
    Otras devuelven un objeto DiarizeOutput.
    """
    speaker_segments = []

    # Caso 1: salida clásica de pyannote.core.Annotation
    if hasattr(diarization, "itertracks"):
        for turn, _, speaker in diarization.itertracks(yield_label=True):
            speaker_segments.append({
                "start": float(turn.start),
                "end": float(turn.end),
                "speaker": str(speaker)
            })

        return speaker_segments

    # Caso 2: objeto con atributo speaker_diarization
    if hasattr(diarization, "speaker_diarization"):
        annotation = diarization.speaker_diarization

        for turn, _, speaker in annotation.itertracks(yield_label=True):
            speaker_segments.append({
                "start": float(turn.start),
                "end": float(turn.end),
                "speaker": str(speaker)
            })

        return speaker_segments

    # Caso 3: objeto con atributo diarization
    if hasattr(diarization, "diarization"):
        annotation = diarization.diarization

        for turn, _, speaker in annotation.itertracks(yield_label=True):
            speaker_segments.append({
                "start": float(turn.start),
                "end": float(turn.end),
                "speaker": str(speaker)
            })

        return speaker_segments

    # Caso 4: salida tipo diccionario
    if isinstance(diarization, dict):
        for key in ["speaker_diarization", "diarization", "annotation"]:
            if key in diarization:
                annotation = diarization[key]

                for turn, _, speaker in annotation.itertracks(yield_label=True):
                    speaker_segments.append({
                        "start": float(turn.start),
                        "end": float(turn.end),
                        "speaker": str(speaker)
                    })

                return speaker_segments

    raise TypeError(
        f"No se ha podido interpretar la salida de pyannote. Tipo recibido: {type(diarization)}"
    )


def overlap(a_start, a_end, b_start, b_end):
    """
    Calcula cuántos segundos se solapan dos intervalos.
    """
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def assign_speakers_to_segments(transcription_segments, speaker_segments):
    """
    Asigna a cada segmento de transcripción el hablante que más tiempo se solapa con él.
    """
    for segment in transcription_segments:
        best_speaker = "SPEAKER_UNKNOWN"
        best_overlap = 0.0

        for speaker_segment in speaker_segments:
            current_overlap = overlap(
                segment["start"],
                segment["end"],
                speaker_segment["start"],
                speaker_segment["end"]
            )

            if current_overlap > best_overlap:
                best_overlap = current_overlap
                best_speaker = speaker_segment["speaker"]

        segment["speaker"] = best_speaker

    return transcription_segments
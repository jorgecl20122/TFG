from faster_whisper import WhisperModel
from difflib import SequenceMatcher

from numpy import block
from aligner import align_segments
import re

MODEL_NAME = "small"

model = None


def get_model():
    global model

    if model is None:
        model = WhisperModel(
            MODEL_NAME,
            device="cpu",
            compute_type="int8"
        )

    return model

fast_model = None
slow_model = None


def normalize_text(text):
    text = text.lower().strip()
    text = re.sub(r"[^\w\sáéíóúüñ]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text


def similarity(text_a, text_b):
    a = normalize_text(text_a)
    b = normalize_text(text_b)

    if not a and not b:
        return 1.0

    return SequenceMatcher(None, a, b).ratio()


def transcribe_with_model(
    model,
    audio_path,
    beam_size=1,
    vad_filter=False,
    language="es"
):
    segments_generator, info = model.transcribe(
        audio_path,
        beam_size=beam_size,
        vad_filter=vad_filter,
        language=language
    )

    segments = []

    for seg in segments_generator:
        segments.append({
            "start": float(seg.start),
            "end": float(seg.end),
            "text": seg.text.strip()
        })

    return segments


def transcribe_fast(audio_path):
    return transcribe_with_model(
        get_model(),
        audio_path,
        beam_size=2,
        vad_filter=True,
        language="es"
    )


def transcribe_slow(audio_path):
    return transcribe_with_model(
        get_model(),
        audio_path,
        beam_size=5,
        vad_filter=True,
        language="es"
    )



def format_text_for_display(text):
    if not text:
        return text

    if text.isupper():
        text = text.lower()
        text = text.capitalize()

    return text


def merge_and_flag_segments(fast_segments, slow_segments, threshold=0.90):
    aligned_blocks = align_segments(fast_segments, slow_segments)
    merged = []

    for block in aligned_blocks:
        fast_text = format_text_for_display(block["a_text"])
        slow_text = format_text_for_display(block["b_text"])

        if not fast_text and not slow_text:
            sim = 1.0
        elif not fast_text or not slow_text:
            sim = 0.0
        else:
            sim = similarity(fast_text, slow_text)

        similarity_percent = int(round(sim * 100))

        uncertain = False
        reason = ""

        if not fast_text:
            uncertain = True
            reason = "missing_fast_block"
        elif not slow_text:
            uncertain = True
            reason = "missing_slow_block"
        elif sim < threshold:
            uncertain = True
            reason = "fast_slow_difference"

        merged.append({
            "start": block["start"],
            "end": block["end"],
            "text": slow_text if slow_text else fast_text,
            "fast_text": fast_text,
            "slow_text": slow_text,
            "uncertain": uncertain,
            "review_reason": reason,
            "similarity_score": round(sim, 3),
            "similarity_percent": similarity_percent,
            "fast_count": len(block["a_segments"]),
            "slow_count": len(block["b_segments"])
        })

    return merged


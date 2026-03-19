from faster_whisper import WhisperModel
from difflib import SequenceMatcher
import re

FAST_MODEL_NAME = "base"
SLOW_MODEL_NAME = "small"

fast_model = WhisperModel(FAST_MODEL_NAME, device="cpu", compute_type="int8")
slow_model = WhisperModel(SLOW_MODEL_NAME, device="cpu", compute_type="int8")


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


def transcribe_with_model(model, audio_path, beam_size=1):
    segments_generator, info = model.transcribe(
        audio_path,
        beam_size=beam_size,
        vad_filter=False
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
    return transcribe_with_model(fast_model, audio_path, beam_size=1)


def transcribe_slow(audio_path):
    return transcribe_with_model(slow_model, audio_path, beam_size=5)


def transcribe_for_calibration(audio_path):
    return transcribe_fast(audio_path)


def overlap(a_start, a_end, b_start, b_end):
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def find_best_match(reference_segment, candidate_segments):
    best_segment = None
    best_overlap = 0.0

    for candidate in candidate_segments:
        current_overlap = overlap(
            reference_segment["start"],
            reference_segment["end"],
            candidate["start"],
            candidate["end"]
        )

        if current_overlap > best_overlap:
            best_overlap = current_overlap
            best_segment = candidate

    return best_segment, best_overlap


def merge_and_flag_segments(fast_segments, slow_segments, threshold=0.85):
    merged = []

    for slow_seg in slow_segments:
        fast_match, _ = find_best_match(slow_seg, fast_segments)

        fast_text = fast_match["text"] if fast_match else ""
        slow_text = slow_seg["text"]

        sim = similarity(fast_text, slow_text) if fast_match else 0.0

        uncertain = False
        reason = ""

        if fast_match is None:
            uncertain = True
            reason = "no_fast_match"
        elif sim < threshold:
            uncertain = True
            reason = "fast_slow_difference"

        merged.append({
            "start": slow_seg["start"],
            "end": slow_seg["end"],
            "text": slow_text,
            "fast_text": fast_text,
            "slow_text": slow_text,
            "uncertain": uncertain,
            "review_reason": reason,
            "similarity": round(sim, 3)
        })

    return merged
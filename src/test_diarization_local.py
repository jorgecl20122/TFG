from diarization import detect_speakers

audio_path = "data/test/RNE.mp3"

speaker_segments = detect_speakers(audio_path, num_speakers=2)

for segment in speaker_segments:
    print(
        segment["speaker"],
        round(segment["start"], 3),
        "->",
        round(segment["end"], 3)
    )
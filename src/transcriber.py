import whisper

def transcribe_audio(audio_path, model_name="base"):

    model = whisper.load_model(model_name)

    result = model.transcribe(audio_path)

    segments = []

    for seg in result["segments"]:
        segments.append({
            "start": seg["start"],
            "end": seg["end"],
            "text": seg["text"].strip()
        })

    return segments
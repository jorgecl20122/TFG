def overlap(a_start, a_end, b_start, b_end):
    return max(0.0, min(a_end, b_end) - max(a_start, b_start))


def join_text(segments):
    return " ".join(seg["text"].strip() for seg in segments if seg["text"].strip())


def align_segments(segments_a, segments_b, tolerance=0.35):
    """
    Alinea dos listas de segmentos por tiempo, agrupando varios segmentos
    de cada lado si hace falta para formar bloques comparables.
    """

    i = 0
    j = 0
    aligned = []

    while i < len(segments_a) and j < len(segments_b):
        group_a = [segments_a[i]]
        group_b = [segments_b[j]]
        i += 1
        j += 1

        while True:
            end_a = group_a[-1]["end"]
            end_b = group_b[-1]["end"]

            if abs(end_a - end_b) <= tolerance:
                break

            if end_a < end_b:
                if i < len(segments_a):
                    group_a.append(segments_a[i])
                    i += 1
                else:
                    break
            else:
                if j < len(segments_b):
                    group_b.append(segments_b[j])
                    j += 1
                else:
                    break

        start = min(group_a[0]["start"], group_b[0]["start"])
        end = max(group_a[-1]["end"], group_b[-1]["end"])

        aligned.append({
            "start": start,
            "end": end,
            "a_segments": group_a,
            "b_segments": group_b,
            "a_text": join_text(group_a),
            "b_text": join_text(group_b),
        })

    while i < len(segments_a):
        seg = segments_a[i]
        aligned.append({
            "start": seg["start"],
            "end": seg["end"],
            "a_segments": [seg],
            "b_segments": [],
            "a_text": seg["text"].strip(),
            "b_text": "",
        })
        i += 1

    while j < len(segments_b):
        seg = segments_b[j]
        aligned.append({
            "start": seg["start"],
            "end": seg["end"],
            "a_segments": [],
            "b_segments": [seg],
            "a_text": "",
            "b_text": seg["text"].strip(),
        })
        j += 1

    return aligned
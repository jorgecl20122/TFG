from transcriber import merge_and_flag_segments

def run_case(name, fast_segments, slow_segments):
    print("\n" + "=" * 70)
    print("CASO:", name)
    print("=" * 70)

    result = merge_and_flag_segments(fast_segments, slow_segments)

    for i, r in enumerate(result, start=1):
        print("-" * 50)
        print(f"Resultado {i}")
        print("Tiempo:", r["start"], "->", r["end"])
        print("Fast:", r.get("fast_text"))
        print("Slow:", r.get("slow_text"))
        print("Similitud:", r.get("similarity_percent"), "%")
        print("Incierto:", r.get("uncertain"))
        print("Motivo:", r.get("review_reason"))

# Caso 1
run_case(
    "Mismo contenido, distinta segmentación",
    [
        {"start": 0.0, "end": 4.0, "text": "hola buenos días empezamos la reunión"}
    ],
    [
        {"start": 0.0, "end": 1.0, "text": "hola"},
        {"start": 1.0, "end": 2.0, "text": "buenos días"},
        {"start": 2.0, "end": 4.0, "text": "empezamos la reunión"}
    ]
)

# Caso 2
run_case(
    "Texto distinto",
    [
        {"start": 0.0, "end": 3.0, "text": "se aprueba el presupuesto"}
    ],
    [
        {"start": 0.0, "end": 3.0, "text": "se aplaza el presupuesto"}
    ]
)

# Caso 3
run_case(
    "Cambio pequeño",
    [
        {"start": 0.0, "end": 2.0, "text": "vale pues seguimos"}
    ],
    [
        {"start": 0.0, "end": 2.0, "text": "vale seguimos"}
    ]
)
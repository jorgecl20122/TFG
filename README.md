# TranscribeMatic

## Descripción:
Aplicación web que permite subir un archivo de audio de una reunión y generar su transcripción en texto separada por segmentos.
El sistema utiliza Whisper de OpenAI para transcribir el audio y genera un editor HTML que permite reproducir el audio de cada segmento y modificar el texto de la transcripción.

## Tecnologías utilizadas:
Python
Flask
Whisper
Torch
Werkzeug

## Estructura del proyecto:
```
TFG
├─ docs
├─ LICENSE
├─ models
├─ README.md
├─ src
│  ├─ app.py
│  ├─ data
│  │  ├─ out
│  │  │  └─ ca3cc30c-ce47-484f-9988-5be8dfa54437
│  │  │     ├─ editor.html
│  │  │     └─ segments.json
│  │  └─ uploads
│  │     └─ ca3cc30c-ce47-484f-9988-5be8dfa54437_GlobalNewsPodcast-20260303-IsraelHitsTehranAndBeirutWithSimultaneousStrikes.mp3
│  ├─ diarization.py
│  ├─ email_sender.py
│  ├─ main.py
│  ├─ requirements.txt
│  ├─ segments.py
│  ├─ templates
│  │  ├─ index.html
│  │  └─ result.html
│  └─ transcriber.py
└─ tests

```

## Instalación:
### 1. Clonar repositorio
```
git clone <repositorio>
cd <repositorio>
```

### 2. Crear entorno virtual
```
python -m venv .venv
.venv\Scripts\activate
```

### 3. Instalar dependencias
```
pip install -r requirements.txt
```

## Ejecutar Aplicación y Uso:
Inciar el servidor:
```
python app.py
```
Abrir el navegador en:
```
http://127.0.0.1:5000
```
Subir un archivo de audio y el sistema procesará el audio y generará transcripción y editor HTML interactivo.
# YouTube → Anki Deck Generator

Aplicación de escritorio que convierte un video de YouTube en un mazo de
Anki (`.apkg`) con tarjetas de video + subtítulos, generadas automáticamente
mediante IA. **Todo el procesamiento (descarga, transcripción, corte de
video, empaquetado) ocurre localmente**; solo la transcripción de texto se
envía a un proveedor de LLM para segmentarla semánticamente — el video
nunca sale de la máquina del usuario.

## Arquitectura

```
┌─────────────────────────┐        HTTP (localhost:8000)       ┌───────────────────────────┐
│   Tauri + React (UI)     │ ──────────────────────────────────▶│  FastAPI backend (sidecar) │
│   frontend/               │◀────────────────────────────────── │  backend/                   │
└─────────────────────────┘        JSON (progreso, resultado)   └───────────────────────────┘
                                                                          │
                                                    ┌─────────────────────┼─────────────────────┐
                                                    ▼                     ▼                     ▼
                                              yt-dlp (descarga)   faster-whisper (STT)     LLM provider
                                                    │                     │              (DeepSeek/Claude/OpenAI)
                                                    ▼                     ▼                     │
                                               FFmpeg (corte) ◀───────────┴─────────────────────┘
                                                    │
                                                    ▼
                                              genanki (.apkg)
```

El frontend (Tauri) nunca habla directamente con FFmpeg, Whisper ni el LLM:
todo pasa por la API local de FastAPI, que se ejecuta como proceso
"sidecar" administrado por Tauri. Esto mantiene una separación estricta
entre UI y lógica de negocio, y permite testear/ejecutar el backend de
forma completamente independiente (incluso por línea de comandos).

### Estructura de carpetas

```
backend/
  app/
    api/          # Rutas FastAPI + esquemas Pydantic (capa HTTP)
    core/         # Orquestador del pipeline, job manager, excepciones
    services/     # Un módulo por responsabilidad (descarga, subtítulos,
                   # transcripción, segmentación, corte, enriquecimiento, anki)
    llm/          # Abstracción de proveedor de IA (Strategy pattern)
    utils/        # Helpers puros (tiempo, filesystem)
  tests/          # Tests unitarios (pytest)
frontend/
  src/
    components/   # UrlForm, ProgressBar, StageIndicator, ErrorBanner
    hooks/         # useJobPolling
    api/           # Cliente HTTP tipado hacia el backend
  src-tauri/       # Shell nativo de Tauri (Rust) que lanza el backend
```

## Decisiones técnicas clave

| Decisión | Alternativas consideradas | Por qué |
|---|---|---|
| **yt-dlp** vía API de Python | youtube-dl, pytube | Mantenido activamente, soporta subtítulos nativos y automáticos en un solo paso, y expone metadata estructurada sin parsear stdout. |
| **faster-whisper** (CTranslate2) | whisper original de OpenAI | 4-8x más rápido en CPU, menor uso de memoria, soporta cuantización int8 — crítico para correr en la máquina del usuario sin GPU. |
| **FFmpeg vía subprocess** | ffmpeg-python, moviepy | El CLI de FFmpeg es la interfaz estable y documentada; moviepy añade dependencias pesadas (numpy/imageio) innecesarias. Se usa re-encode (no `-c copy`) para cortes exactos al frame, no al keyframe más cercano. |
| **pysubs2 + srt** | Parsers propios | pysubs2 normaliza cualquier formato (VTT/SRT/ASS) a SRT limpio; `srt` es una librería pequeña y muy testeada para el parseo fino usado en el re-timing por segmento. |
| **genanki** | Generar .apkg a mano (SQLite + zip) | Es el estándar de facto en Python para crear paquetes Anki válidos sin necesitar Anki instalado; maneja el empaquetado de medios automáticamente. |
| **Patrón Strategy para LLM** (`llm/base.py` + 3 implementaciones) | if/else por proveedor esparcido en el código | Cambiar de proveedor es una sola línea en `.env`; agregar un cuarto proveedor no toca lógica de negocio. |
| **pydantic-settings** | `os.environ` manual | Config tipada, validación al arrancar (fail-fast), y `.env` sin código extra. |
| **Polling HTTP simple** (no WebSockets/SSE) | WebSockets | Para una app de escritorio de un solo usuario, con actualizaciones de progreso coarse-grained, un `setTimeout` + `fetch` cada 1.5s es más simple y suficientemente responsivo. |
| **Job manager en memoria** (no Redis/Celery) | Cola de tareas distribuida | Un solo usuario, un solo proceso local: una cola distribuida sería sobre-ingeniería. El único "seam" de extensión (`JobManager`) queda aislado por si se necesita persistencia en el futuro. |

## Flujo del pipeline (`app/core/pipeline.py`)

1. **Descarga** (`yt-dlp`): video + subtítulos si existen.
2. **Subtítulos**: si yt-dlp encontró subtítulos, se normalizan con
   `pysubs2`. Si no, se transcribe el video con `faster-whisper`.
3. **Transcripción → LLM**: se envía *solo el texto* (nunca el video) a un
   prompt que exige **JSON estricto** con segmentos `{title, start, end}`.
   La respuesta se valida con un modelo Pydantic; si falla, se reintenta
   una vez con un prompt de corrección.
4. **Corte**: FFmpeg corta cada segmento con precisión de frame.
5. **Re-timing de subtítulos**: se genera un `.srt` por segmento,
   reajustado para comenzar en `00:00:00`.
6. **Enriquecimiento opcional**: traducción y tip de pronunciación nativa
   por segmento (no bloqueante — si falla, la tarjeta se genera igual).
7. **Construcción del mazo**: `genanki` arma el `.apkg` embebiendo cada
   clip de video como archivo de medios (sin enlaces externos).
8. **Limpieza**: se vacían `temp/downloads`, `temp/subtitles`,
   `temp/segments`, `temp/anki` (configurable con `CLEANUP_AFTER_JOB`).

## Requisitos previos

- Python 3.12+
- Node.js 18+ y npm
- Rust (para compilar el shell de Tauri) — ver https://tauri.app/start/prerequisites/
- [FFmpeg](https://ffmpeg.org/download.html) instalado y en el `PATH`
- Una API key de al menos uno de: DeepSeek, Anthropic (Claude), OpenAI

## Backend: instalación y ejecución

- Configura YT_DLP_COOKIES_FROM_BROWSER= O YT_DLP_COOKIES_FILE= del archivo .env para evitar posibles conflictos al descargar ciertos videos, recomendado descargar la extension de tu navegador "Get cookies.txt locally" y extraer las cookies de tu sesion en youtube para mayor compatibilidad

- Configura tu apikey de tu proveedor de IA (deepseek, claude o openAi) en el .env

- Si ocurrio algun error, asegurarse de que las carpetas dentro de temp esten vacias para evitar cualquier conflicto


```bash
cd backend
uv sync                       # o: pip install -e ".[dev]"
cp .env.example .env
# Edita .env: agrega tu API key del proveedor LLM que quieras usar

uv run uvicorn app.main:app --reload --port 8000
# o: python -m uvicorn app.main:app --reload --port 8000
```

Ejecutar tests:

```bash
cd backend
uv run pytest
```

## Frontend: desarrollo

```bash
cd frontend
npm install
npm run tauri dev
```

Esto abre la ventana de escritorio de Tauri apuntando al backend en
`http://127.0.0.1:8000`. En desarrollo puedes correr el backend por
separado (como arriba) en vez de empaquetarlo como sidecar.

## Empaquetado para distribución (producción)

Para distribuir la app como un único ejecutable, el backend de Python debe
compilarse a un binario standalone (sidecar) con **PyInstaller**, y
colocarse donde Tauri lo espera:

```bash
cd backend
uv run pyinstaller --onefile --name backend app/main.py \
  --add-data "app:app" \
  --collect-all faster_whisper

# Renombra el binario según el target triple de Rust, p.ej.:
#   backend-x86_64-pc-windows-msvc.exe
#   backend-x86_64-apple-darwin
#   backend-x86_64-unknown-linux-gnu
mv dist/backend ../frontend/src-tauri/binaries/backend-<target-triple>
```

Luego:

```bash
cd frontend
npm run tauri build
```

Esto genera el instalador nativo (`.msi`/`.dmg`/`.AppImage` según el SO) en
`frontend/src-tauri/target/release/bundle/`.

## Configuración (`backend/.env`)

Ver `backend/.env.example` para la lista completa de variables. Las más
relevantes:

- `LLM_PROVIDER`: `deepseek` | `claude` | `openai`
- `WHISPER_MODEL_SIZE`: `tiny` | `base` | `small` | `medium` | `large-v3`
  (trade-off velocidad/precisión; `small` es un buen punto de partida en CPU)
- `SEGMENT_MIN_SECONDS` / `SEGMENT_MAX_SECONDS`: duración objetivo de cada
  tarjeta
- `CLEANUP_AFTER_JOB`: si se borran los archivos temporales al finalizar

## Calidad de código

- Tipado estricto en ambos lados (Python: `mypy --strict`; TS: `strict: true`)
- Separación estricta UI / lógica / IA / FFmpeg / Whisper / Anki, cada
  módulo con una única responsabilidad
- Manejo de errores mediante jerarquía de excepciones propia
  (`app/core/exceptions.py`), nunca excepciones genéricas silenciosas
- Logging estructurado en todos los servicios
- Tests unitarios para la lógica más sensible (parseo de tiempos, parseo/
  validación del JSON del LLM, re-timing de subtítulos)

  ### song

  - if is a song, you can add this in segmenter.py {duration_rule}:
  - If the transcript is a song, identify repeated choruses, refrains, hooks,
  or repeated verses.
- Only create a segment for the FIRST occurrence of repeated lyrical content.
- If the same chorus or verse appears again later with substantially the same
  lyrics, DO NOT create another segment for it.
- Continue segmenting normally after the repeated section.
- This deduplication rule applies only to songs or musical performances, not
  to speeches, podcasts, interviews, or lessons.  
- Ignore non-content metadata such as:
  - song title
  - artist name
  - album name
  - record label
  - publisher
  - "Written by"
  - copyright notices
  - licensing information
  - production credits
  - "Edit by", "Remastered by", etc.
- Do not create segments consisting only of metadata or credits.
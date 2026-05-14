# CLAIRE // VERITAS LEGAL

Persistent litigation intelligence workspace for the local CLAIRE build.

## What changed

- Added a new FastAPI web workspace under `web/`.
- Kept the legacy Tkinter build intact.
- Kept the existing memory files and ingestion patterns intact.
- Added grounded chat, evidence search, timeline reconstruction, OCR, Gyro visor output, and upload ingest.

## Runtime model

- `CLAIRE_API_URL` points to the local llama.cpp server.
- `CLAIRE_MODEL_ID` selects the model id passed into chat completions.
- The app runs offline except for the local llama.cpp endpoint.
- No cloud API is required.

## Layout

- `web/app.py` is the FastAPI entrypoint.
- `web/index.html` is the premium legal workspace UI.
- `web/static/styles.css` contains the visual system.
- `web/static/app.js` handles chat, search, ingest, OCR, and panel refresh.
- `web/services/workspace.py` owns storage, search, grounding, Gyro visor output, and timeline logic.
- `web/services/llm.py` wraps the local model server.
- `palantir_parser.py` preserves the breadcrumb-style ingest flow for folders, zips, PDFs, DOCX, and images.

## Endpoints

- `GET /`
- `GET /health`
- `POST /chat`
- `POST /ingest`
- `POST /search`
- `POST /timeline`
- `POST /ocr`
- `POST /load_corpus`
- `GET /cache`
- `GET /prompt_prefix`
- `POST /suggest`
- `GET /gyro_debug`
- `POST /gyro`
- `POST /prompt-prefix`
- `GET /trace/{trace_id}`
- `GET /report/{trace_id}`
- `POST /demo`
- `WebSocket /ws/ingest`

## Launch

```powershell
.\start_veritas_legal.ps1
```

It will start the web workspace on `127.0.0.1:8000` and try to reuse or bootstrap the local llama.cpp server on `127.0.0.1:8080`.

## Notes

- Uploads are handled without cloud services.
- OCR is local and optional; if `pytesseract` or `PIL` is missing, the endpoint returns an explicit unavailable response.
- The legacy Tkinter launcher remains available for the existing desktop build.


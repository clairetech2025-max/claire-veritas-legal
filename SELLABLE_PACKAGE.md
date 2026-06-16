# Veritas Legal Sellable Package

## Product Position

Veritas Legal is a local-first legal evidence and matter-memory workspace.

It is designed for document-heavy legal work where teams need to ingest evidence, preserve source lineage, reconstruct timelines, search grounded records, and produce traceable analysis without sending matter data to a cloud chatbot.

## Buyer-Safe Summary

Veritas Legal helps legal teams turn messy matter folders into searchable, traceable working memory.

Core flow:

```text
Matter files
  -> ingest
  -> evidence records
  -> grounded search
  -> timeline
  -> trace / report
  -> local model-assisted drafting
```

## What Is Implemented

- FastAPI web workspace
- local-first storage under `memory/` and `vault/`
- matter profile support
- file, folder, ZIP, pasted-text, OCR-capable ingest paths
- grounded search over matter records
- timeline and trace endpoints
- CourtListener connector scaffolding
- local model integration through llama.cpp-compatible chat completions
- evaluation license manager
- synthetic demo seed data

## What To Demo

1. Seed the synthetic matter:

```bash
python3 demo_seed.py
```

2. Start the app:

```bash
uvicorn web.app:app --host 127.0.0.1 --port 8000
```

3. Open:

```text
http://127.0.0.1:8000
```

4. Search for:

```text
elevator outage accessible alternate routing
```

5. Show:

- the matter profile
- evidence hits
- timeline
- trace output
- grounded citations

## What To Keep Private

Do not publish or demo with:

- real client data
- matter memory
- `.env.local`
- API keys
- creator unlock phrases
- paid license secrets
- private legal strategy

## Required Disclaimer

Veritas Legal is a legal evidence and workflow support tool. It is not legal advice and does not replace attorney review.

## Commercial Angle

Sell:

- private setup
- matter-workspace licensing
- local model integration
- evidence ingestion workflows
- connector packs
- support and onboarding

The strongest positioning is:

> Local-first legal continuity with provenance, grounded recall, timeline reconstruction, and traceable drafting support.

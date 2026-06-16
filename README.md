CLAIRE // VERITAS LEGAL
========================

Local-first litigation intelligence workspace for evidence reconstruction, chronology analysis, grounded citation tracing, and private matter memory.

VERITAS LEGAL is a locally operated workspace for attorneys, investigators, analysts, and document-heavy case teams that need to organize complex evidence sets, reconstruct timelines, correlate entities, trace provenance, and preserve matter continuity across legal corpora.

Unlike a generic chat surface, VERITAS LEGAL emphasizes grounded outputs, replayable citation chains, offline-first operation, chronology reconstruction, and evidence-linked reasoning for litigation and investigative workflows.

## Core Capabilities

- Evidence ingest and OCR
- Timeline reconstruction
- Persistent matter memory
- Grounded citation tracing
- Entity and relationship analysis
- Contradiction detection
- Local/private operation
- Legal corpus search and recall
- Read-only evaluation licensing
- Modular FastAPI + llama.cpp architecture

## Intended Users

- litigation teams
- civil rights investigations
- discovery-heavy matters
- regulatory analysis
- administrative law
- investigative research
- document-intensive legal workflows

Ex Tenebris Iustitia

## Quick Start

Install dependencies in a local virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-web.txt
```

Seed the synthetic demo matter:

```bash
python3 demo_seed.py
```

Start the web workspace:

```bash
uvicorn web.app:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000
```

## Demo Path

Use the synthetic demo matter to show the product without exposing real legal data:

```bash
python3 demo_seed.py
uvicorn web.app:app --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000
```

Demo query:

```text
elevator outage accessible alternate routing
```

Expected demo surface:

- matter profile
- grounded evidence hits
- timeline entries
- replayable trace
- local-first workspace status

See `SELLABLE_PACKAGE.md` for the buyer-facing package outline.

## Smoke Test

Run the local package check:

```bash
python3 smoke_test.py
```

The smoke test verifies required public files, ignored private/runtime paths, and a synthetic ingest/search roundtrip in a temporary workspace.

The same smoke path runs in GitHub Actions on push and pull request.

## Safety

This public repository is intended for code, synthetic demo data, and documentation only. Keep real matter data, memory files, vault files, `.env.local`, API keys, license secrets, and creator unlock phrases out of GitHub.

Veritas Legal is a legal evidence and workflow support tool. It is not legal advice and does not replace attorney review.

## License

This repository is published under an all-rights-reserved evaluation license. See `LICENSE`.

## Local-Only Data

The following paths are ignored and should remain local:

- `memory/`
- `vault/`
- `.claire_veritas/`
- `.env.local`
- `models/`
- media exports and archives

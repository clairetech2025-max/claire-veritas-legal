# VERITAS Session Resume

Current state:
- `VERITAS LEGAL` is online at `http://127.0.0.1:8000/`
- local model service is online at `http://127.0.0.1:8080/`
- `Creator Mode` is implemented
- `CourtListener` bridge is implemented
- portable connector payload templates are checked in

Latest commits:
- `0a2da1b` Add portable connector payload templates
- `7acf89a` Add CourtListener bridge and creator mode unlock
- `3c3e297` Stabilize VERITAS workspace and add creator mode
- `ca16782` Add docket import scaffolding
- `2483a60` Add PDF packet export

Creator unlock:
- send `I_am_BATTLEBORN` once in the chat shell
- that unlocks Creator Mode for the session

Portable files:
- `CONNECTORS.md`
- `examples/courtlistener-search.json`
- `examples/courtlistener-ingest.json`
- `examples/chat-creator-unlock.json`
- `examples/chat-creator-question.json`
- `.env.example`

Next priorities:
1. add a minimal CourtListener UI control surface
2. add a second external-source connector if needed
3. keep provenance and matter continuity as the rule

Resume rule:
- use this file as the quick re-entry point
- use a commit hash if you need an exact checkpoint
- there is no separate chat resume number

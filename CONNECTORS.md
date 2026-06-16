# VERITAS Connectors

Local setup:
- Put real API keys in `.env.local`
- Keep `.env.local` out of GitHub
- Use the examples below as templates on any machine

Live endpoints:
- `POST /courtlistener/search`
- `POST /courtlistener/ingest`
- `POST /chat`

Creator unlock:
- Set `VERITAS_CREATOR_PASSPHRASE` in `.env.local`
- Send that configured phrase once in the chat shell
- That unlocks Creator Mode for the session

Notes:
- CourtListener is the first external source bridge
- Results import into the active matter with provenance metadata
- Payloads are intentionally small so they can be copied into PowerShell, curl, or a tiny local wrapper

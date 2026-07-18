from __future__ import annotations

import os

import uvicorn

os.environ.setdefault("VERITAS_MEMORY_DIR", "/tmp/veritas_memory")
os.environ.setdefault("VERITAS_KNOWLEDGE_DIR", "/tmp/veritas_knowledge")
os.environ.setdefault("VERITAS_VAULT_DIR", "/tmp/veritas_vault")
os.environ.setdefault("VERITAS_UPLOAD_DIR", "/tmp/veritas_uploads")
os.environ.setdefault("VERITAS_RUNTIME_DIR", "/tmp/veritas_runtime")

from web.app import app  # noqa: F401


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "7860")))

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import traceback
import zipfile
from pathlib import Path
from typing import Any, Dict, List

try:
    import docx  # type: ignore
except ImportError:
    docx = None

try:
    import PyPDF2  # type: ignore
except ImportError:
    PyPDF2 = None

try:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
except ImportError:
    pytesseract = None
    Image = None


ROOT_DIR = Path(__file__).resolve().parent
OUT_DIR = ROOT_DIR / "palantir_data"
OUT_DIR.mkdir(parents=True, exist_ok=True)
MEM_FILE = OUT_DIR / "veritas_mem.jsonl"
LOG_FILE = OUT_DIR / "parser_log.txt"
CHUNK_SIZE_CHARS = 1200
OVERLAP_CHARS = 200


def log(*args: Any) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] " + " ".join(str(a) for a in args)
    print(line)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def short_id(h: str, n: int = 12) -> str:
    return h[:n]


def make_hg_breadcrumb(source_path: Path, chunk_index: int, total_chunks: int, text: str, diode_tag: str = "ingest_only", parser_version: str = "0.1") -> Dict[str, Any]:
    text_trim = text.strip()
    payload_hash = sha256_hex(text_trim)
    hg_id = f"HnG-{short_id(payload_hash)}"
    return {
        "ts": int(time.time()),
        "hg_id": hg_id,
        "source_path": str(source_path),
        "chunk_index": chunk_index,
        "total_chunks": total_chunks,
        "parser_version": parser_version,
        "diode_mode": diode_tag,
        "integrity": {"payload_sha256": payload_hash, "source_sha256": sha256_hex(str(source_path))},
        "text": text_trim,
    }


def extract_text_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_text_json(path: Path) -> str:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    try:
        data = json.loads(raw)
    except Exception:
        return raw
    out_lines: List[str] = []

    def walk(obj, prefix: str = ""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                new_prefix = f"{prefix}.{k}" if prefix else str(k)
                walk(v, new_prefix)
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                new_prefix = f"{prefix}[{i}]"
                walk(v, new_prefix)
        else:
            try:
                out_lines.append(f"{prefix}: {obj}")
            except Exception:
                pass

    walk(data)
    return "\n".join(out_lines)


def extract_text_docx(path: Path) -> str:
    if docx is None:
        log("DOCX support not installed; skipping:", path)
        return ""
    try:
        document = docx.Document(str(path))
        return "\n".join(paragraph.text for paragraph in document.paragraphs)
    except Exception as e:
        log("DOCX parse error:", path, e)
        return ""


def extract_text_pdf(path: Path) -> str:
    if PyPDF2 is None:
        log("PDF support not installed; skipping:", path)
        return ""
    try:
        txt_parts: List[str] = []
        with path.open("rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                try:
                    txt_parts.append(page.extract_text() or "")
                except Exception:
                    continue
        return "\n".join(txt_parts)
    except Exception as e:
        log("PDF parse error:", path, e)
        return ""


def extract_text_image(path: Path) -> str:
    if pytesseract is None or Image is None:
        log("OCR not installed; skipping image:", path)
        return ""
    try:
        img = Image.open(str(path))
        return pytesseract.image_to_string(img)
    except Exception as e:
        log("Image OCR error:", path, e)
        return ""


def extract_text_generic(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def extract_text(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in {".txt", ".md", ".log"}:
        return extract_text_txt(path)
    if ext in {".json", ".jsonl"}:
        return extract_text_json(path)
    if ext == ".docx":
        return extract_text_docx(path)
    if ext == ".pdf":
        return extract_text_pdf(path)
    if ext in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        return extract_text_image(path)
    return extract_text_generic(path)


def chunk_text(text: str, size: int = CHUNK_SIZE_CHARS, overlap: int = OVERLAP_CHARS) -> List[str]:
    text = text.strip()
    if not text:
        return []
    chunks: List[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + size, n)
        chunk = text[start:end]
        chunks.append(chunk)
        if end == n:
            break
        start = max(0, end - overlap)
    return chunks


def iter_files_in_zip(zip_path: Path) -> List[Path]:
    tmp_root = OUT_DIR / "tmp_zip" / zip_path.stem
    tmp_root.mkdir(parents=True, exist_ok=True)
    out_paths: List[Path] = []
    try:
        with zipfile.ZipFile(str(zip_path), "r") as zf:
            for name in zf.namelist():
                if name.endswith("/"):
                    continue
                target_path = tmp_root / name
                target_path.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as src, target_path.open("wb") as dst:
                    dst.write(src.read())
                out_paths.append(target_path)
    except Exception as e:
        log("ZIP extract error:", zip_path, e)
    return out_paths


def iter_all_files(root: Path) -> List[Path]:
    files: List[Path] = []
    for dirpath, _, filenames in os.walk(root):
        d = Path(dirpath)
        for fn in filenames:
            files.append(d / fn)
    return files


def ingest_path(root: Path) -> None:
    root = root.resolve()
    log("Starting ingest for:", root)
    all_files: List[Path] = []
    if root.is_file():
        if root.suffix.lower() == ".zip":
            all_files.extend(iter_files_in_zip(root))
        else:
            all_files.append(root)
    else:
        for p in iter_all_files(root):
            if p.suffix.lower() == ".zip":
                all_files.extend(iter_files_in_zip(p))
            else:
                all_files.append(p)

    log("Total files discovered (incl. zip contents):", len(all_files))
    n_ingested = 0
    with MEM_FILE.open("a", encoding="utf-8") as out_f:
        for path in all_files:
            try:
                text = extract_text(path)
                if not text.strip():
                    continue
                chunks = chunk_text(text)
                total_chunks = len(chunks)
                if total_chunks == 0:
                    continue
                for idx, chunk in enumerate(chunks):
                    hg = make_hg_breadcrumb(source_path=path, chunk_index=idx, total_chunks=total_chunks, text=chunk)
                    out_f.write(json.dumps(hg, ensure_ascii=False) + "\n")
                    n_ingested += 1
            except Exception as e:
                log("Ingest error:", path, e)
                traceback.print_exc()
    log("Ingest complete. Chunks written:", n_ingested)
    log("Memory file:", MEM_FILE)


def search_mem(keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
    keyword = keyword.strip().lower()
    results: List[Dict[str, Any]] = []
    if not MEM_FILE.exists():
        log("No memory file yet.")
        return results
    with MEM_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                j = json.loads(line)
            except Exception:
                continue
            blob = json.dumps(j, ensure_ascii=False).lower()
            if keyword in blob:
                results.append(j)
            if len(results) >= limit:
                break
    return results


def cmd_ingest(args: List[str]) -> None:
    if not args:
        print("Usage: palantir_parser.py ingest /path/to/folder_or_zip")
        sys.exit(1)
    target = Path(args[0])
    if not target.exists():
        print("Path does not exist:", target)
        sys.exit(1)
    ingest_path(target)


def cmd_search(args: List[str]) -> None:
    if not args:
        print("Usage: palantir_parser.py search keyword [limit]")
        sys.exit(1)
    kw = args[0]
    limit = int(args[1]) if len(args) > 1 else 20
    hits = search_mem(kw, limit=limit)
    print(f"Found {len(hits)} matches:")
    for h in hits:
        print("=" * 80)
        print("hg_id:", h.get("hg_id"))
        print("source:", h.get("source_path"))
        print("chunk:", f"{h.get('chunk_index') + 1}/{h.get('total_chunks')}")
        print("-" * 80)
        print(h.get("text", "")[:2000])
        print()


def cmd_info() -> None:
    print("Palantir Parser v0.1 - Desktop Build")
    print("Memory file:", MEM_FILE)
    if MEM_FILE.exists():
        with MEM_FILE.open("r", encoding="utf-8") as f:
            n = sum(1 for _ in f)
        print("Total H&G chunks:", n)
    else:
        print("No memory file found yet.")


def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print(" palantir_parser.py ingest /path/to/folder_or_zip")
        print(" palantir_parser.py search keyword [limit]")
        print(" palantir_parser.py info")
        sys.exit(1)
    cmd = sys.argv[1].lower()
    args = sys.argv[2:]
    if cmd == "ingest":
        cmd_ingest(args)
    elif cmd == "search":
        cmd_search(args)
    elif cmd == "info":
        cmd_info()
    else:
        print("Unknown command:", cmd)
        sys.exit(1)


if __name__ == "__main__":
    main()


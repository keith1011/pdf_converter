"""Wave 2 B-side research agent: Qdrant reader + jobs filesystem allowlist (read-only).

Never writes to Qdrant. Never writes under /data/pdf-scaner.
Requires: qdrant-client, httpx (or urllib), Ollama running locally.

Usage on B:
  export QDRANT_URL=http://192.168.1.107:6333
  export QDRANT_READER_KEY=...   # from ~/homelab/.env READ_ONLY key
  export OLLAMA_MODEL=llama3.2:1b
  python3 query_agent.py "二次方程判別式"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ALLOWLIST_ROOTS = [
    Path("/data/pdf-scaner/jobs"),
]
# Deny these even if under jobs
DENY_NAME_PARTS = (".incoming",)

COLLECTION = os.environ.get("QDRANT_COLLECTION", "exam_segments_v1")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://192.168.1.107:6333").rstrip("/")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:1b")
# Default embed model on B for vector search (must be 768-d to match exam_segments_v1)
OLLAMA_EMBED_MODEL = os.environ.get("OLLAMA_EMBED_MODEL", "nomic-embed-text")
TOP_K = int(os.environ.get("AGENT_TOP_K", "5"))


def reader_key() -> str:
    key = os.environ.get("QDRANT_READER_KEY") or os.environ.get("QDRANT__SERVICE__READ_ONLY_API_KEY")
    if not key:
        # Optional: load from ~/homelab/.env without importing writer into process if possible
        env_path = Path.home() / "homelab" / ".env"
        if env_path.is_file():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("QDRANT__SERVICE__READ_ONLY_API_KEY="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    if not key:
        raise SystemExit("Set QDRANT_READER_KEY or READ_ONLY key in ~/homelab/.env")
    return key


def _http_json(method: str, url: str, *, headers: dict | None = None, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code} {url}: {detail[:500]}") from e


def assert_reader_cannot_write(api_key: str) -> None:
    """Fail loud if this key can upsert (misconfigured writer as reader)."""
    try:
        _http_json(
            "PUT",
            f"{QDRANT_URL}/collections/{COLLECTION}/points?wait=true",
            headers={"api-key": api_key},
            body={
                "points": [
                    {
                        "id": "00000000-0000-4000-8000-000000000099",
                        "vector": [0.0] * 768,
                        "payload": {"doc_id": "__wave2_should_fail__"},
                    }
                ]
            },
        )
    except SystemExit as e:
        msg = str(e).lower()
        if "403" in msg or "401" in msg or "forbidden" in msg or "unauthorized" in msg:
            print("PASS: reader key cannot upsert")
            return
        raise
    raise SystemExit("FAIL: reader key was able to upsert — aborting agent")


def search(api_key: str, query: str, limit: int) -> list[dict]:
    """Prefer qdrant-client if installed; else REST with dummy vector fallback is weak.

    For Wave 2 we use text payload scroll+filter when embedding on B is unavailable,
    OR call A-style: if fastembed missing, use Qdrant recommend/search with zero vector
    is useless. Better: use scroll with MatchText if available, else keyword filter on payload.
    """
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models as qm
    except ImportError:
        QdrantClient = None  # type: ignore

    if QdrantClient is not None:
        client = QdrantClient(
            url=QDRANT_URL,
            api_key=api_key,
            prefer_grpc=False,
            check_compatibility=False,
        )
        # Try embedding via ollama nomic if present; else MatchText scroll
        vector = _embed_ollama(query)
        if vector is not None:
            # qdrant-client ≥1.14: query_points; older: search(query_vector=...)
            if hasattr(client, "query_points"):
                resp = client.query_points(
                    collection_name=COLLECTION,
                    query=vector,
                    limit=limit,
                    with_payload=True,
                )
                hits = list(getattr(resp, "points", None) or [])
            else:
                hits = client.search(
                    collection_name=COLLECTION,
                    query_vector=vector,
                    limit=limit,
                    with_payload=True,
                )
            return [
                {
                    "score": float(h.score) if getattr(h, "score", None) is not None else None,
                    "doc_id": (h.payload or {}).get("doc_id"),
                    "page": (h.payload or {}).get("page"),
                    "segment_id": (h.payload or {}).get("segment_id"),
                    "text": (h.payload or {}).get("text"),
                    "job_id": (h.payload or {}).get("job_id"),
                }
                for h in hits
            ]
        # Fallback: payload text contains
        points, _ = client.scroll(
            collection_name=COLLECTION,
            scroll_filter=qm.Filter(
                must=[qm.FieldCondition(key="text", match=qm.MatchText(text=query))]
            ),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return [
            {
                "score": None,
                "doc_id": (p.payload or {}).get("doc_id"),
                "page": (p.payload or {}).get("page"),
                "segment_id": (p.payload or {}).get("segment_id"),
                "text": (p.payload or {}).get("text"),
                "job_id": (p.payload or {}).get("job_id"),
            }
            for p in points
        ]

    # Pure REST scroll with MatchText
    body = {
        "limit": limit,
        "with_payload": True,
        "with_vector": False,
        "filter": {"must": [{"key": "text", "match": {"text": query}}]},
    }
    data = _http_json(
        "POST",
        f"{QDRANT_URL}/collections/{COLLECTION}/points/scroll",
        headers={"api-key": api_key},
        body=body,
    )
    out = []
    for p in data.get("result", {}).get("points", []):
        payload = p.get("payload") or {}
        out.append(
            {
                "score": None,
                "doc_id": payload.get("doc_id"),
                "page": payload.get("page"),
                "segment_id": payload.get("segment_id"),
                "text": payload.get("text"),
                "job_id": payload.get("job_id"),
            }
        )
    return out


def _embed_ollama(text: str) -> list[float] | None:
    """Embed via Ollama (nomic-embed-text → 768-d). Returns None if unavailable."""
    model = (os.environ.get("OLLAMA_EMBED_MODEL") or OLLAMA_EMBED_MODEL or "").strip()
    if not model:
        return None
    try:
        data = _http_json(
            "POST",
            f"{OLLAMA_URL}/api/embeddings",
            body={"model": model, "prompt": f"search_query: {text}"},
        )
        vec = data.get("embedding")
        if isinstance(vec, list) and len(vec) >= 64:
            return [float(x) for x in vec]
    except SystemExit:
        return None
    return None


def path_allowed(path: Path) -> bool:
    resolved = path.resolve()
    for part in DENY_NAME_PARTS:
        if part in resolved.parts:
            return False
    for root in ALLOWLIST_ROOTS:
        try:
            resolved.relative_to(root.resolve())
            return resolved.is_file() or resolved.is_dir()
        except ValueError:
            continue
    return False


def read_job_snippet(job_id: str, max_chars: int = 1500) -> str | None:
    if not job_id or any(x in job_id for x in ("..", "/", "\\")):
        return None
    job_dir = Path("/data/pdf-scaner/jobs") / job_id
    if not path_allowed(job_dir):
        return None
    done = job_dir / "DONE.json"
    if not done.is_file():
        return None
    txt_candidates = list(job_dir.glob("*.txt"))
    parts = [f"DONE: {done.read_text(encoding='utf-8')[:500]}"]
    if txt_candidates:
        parts.append(txt_candidates[0].read_text(encoding="utf-8")[:max_chars])
    return "\n".join(parts)


def ollama_chat(prompt: str) -> str:
    data = _http_json(
        "POST",
        f"{OLLAMA_URL}/api/generate",
        body={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
    )
    return (data.get("response") or "").strip()


def build_prompt(query: str, hits: list[dict]) -> str:
    blocks = []
    for i, h in enumerate(hits, 1):
        blocks.append(
            f"[{i}] doc={h.get('doc_id')} page={h.get('page')} seg={h.get('segment_id')} job={h.get('job_id')}\n"
            f"{(h.get('text') or '')[:800]}"
        )
    ctx = "\n\n".join(blocks) if blocks else "(no hits)"
    return (
        "You are a read-only research assistant for an exam question bank.\n"
        "Answer ONLY from the context. If insufficient, say so.\n"
        "Reply in Traditional Chinese unless the user used English.\n\n"
        f"Question: {query}\n\nContext:\n{ctx}\n\nAnswer:"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Wave 2 read-only B query agent")
    ap.add_argument("query", nargs="?", help="Natural language query")
    ap.add_argument("--skip-write-check", action="store_true", help="Skip reader upsert probe")
    ap.add_argument("--json", action="store_true", help="Print hits JSON only (no LLM)")
    ap.add_argument("--limit", type=int, default=TOP_K)
    args = ap.parse_args()
    if not args.query:
        raise SystemExit("usage: query_agent.py 'your question'")

    key = reader_key()
    if not args.skip_write_check:
        assert_reader_cannot_write(key)

    hits = search(key, args.query, args.limit)
    if args.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
        return

    # Optional filesystem enrichment for first job_id
    extra = None
    for h in hits:
        jid = h.get("job_id")
        if jid:
            extra = read_job_snippet(str(jid))
            if extra:
                break

    prompt = build_prompt(args.query, hits)
    if extra:
        prompt += f"\n\nJob file snippet (allowlisted read-only):\n{extra[:1200]}"

    print("=== hits ===")
    for h in hits:
        print(f"- {h.get('doc_id')} p{h.get('page')} {h.get('segment_id')} :: {(h.get('text') or '')[:80]!r}")
    print("=== answer ===")
    print(ollama_chat(prompt))


if __name__ == "__main__":
    main()

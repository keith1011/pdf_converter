"""Ingest a published job into Qdrant exam_segments_v1 (A-side writer)."""

from __future__ import annotations

import argparse
import json
import os
import uuid
from pathlib import Path

from done import content_hash, load_and_validate_done, normalize_text
from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

COLLECTION = "exam_segments_v1"
EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1.5"
EMBEDDING_DIM = 768
CHUNK_VERSION = "pageir_v1"
UUID_NS = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # URL namespace


def point_id(doc_id: str, page: int, segment_id: str) -> str:
    key = f"{doc_id}|{page}|{segment_id}|{EMBEDDING_MODEL}|{CHUNK_VERSION}"
    return str(uuid.uuid5(UUID_NS, key))


def load_segments(job_dir: Path, doc_id: str) -> list[dict]:
    pageir = job_dir / f"{doc_id}.pageir.json"
    tex = None
    tex_path = job_dir / f"{doc_id}.tex"
    if tex_path.is_file():
        tex = tex_path.read_text(encoding="utf-8")

    out: list[dict] = []
    if pageir.is_file():
        data = json.loads(pageir.read_text(encoding="utf-8"))
        for page in data.get("pages", []):
            page_index = int(page.get("page_index", 0))
            for i, seg in enumerate(page.get("segments", [])):
                text = (seg.get("text") or "").strip()
                if not text:
                    continue
                seg_id = f"p{page_index}_s{i}"
                out.append(
                    {
                        "doc_id": doc_id,
                        "page": page_index,
                        "segment_id": seg_id,
                        "kind": seg.get("kind", "prose"),
                        "text": text,
                        "tex": tex,
                        "source_path": str(pageir.name),
                    }
                )
        return out

    # Fallback: whole txt as page 0
    txt = (job_dir / f"{doc_id}.txt").read_text(encoding="utf-8")
    out.append(
        {
            "doc_id": doc_id,
            "page": 0,
            "segment_id": "p0_all",
            "kind": "prose",
            "text": txt,
            "tex": tex,
            "source_path": f"{doc_id}.txt",
        }
    )
    return out


def get_embedder():
    """Prefer fastembed nomic 768-d; fail clearly if missing."""
    try:
        from fastembed import TextEmbedding
    except ImportError as e:
        raise SystemExit(
            "Install ingest deps: pip install -r homelab/ingest/requirements.txt"
        ) from e

    # 768-dim nomic (fastembed full id)
    model = TextEmbedding(model_name=EMBEDDING_MODEL)
    return model


def embed_texts(model, texts: list[str]) -> list[list[float]]:
    # nomic often wants a task prefix; use search_document for corpus
    prefixed = [f"search_document: {t}" for t in texts]
    vectors = list(model.embed(prefixed))
    return [list(map(float, v)) for v in vectors]


def ensure_collection(client: QdrantClient) -> None:
    names = {c.name for c in client.get_collections().collections}
    if COLLECTION in names:
        return
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=qm.VectorParams(size=EMBEDDING_DIM, distance=qm.Distance.COSINE),
    )


def ingest_job(
    job_dir: Path,
    *,
    qdrant_url: str,
    api_key: str,
    reindex: bool = False,
) -> tuple[int, int]:
    done = load_and_validate_done(job_dir)
    doc_id = done["doc_id"]
    segments = load_segments(job_dir, doc_id)
    if not segments:
        raise SystemExit("no segments to ingest")

    client = QdrantClient(
        url=qdrant_url,
        api_key=api_key,
        prefer_grpc=False,
        check_compatibility=False,
    )
    ensure_collection(client)

    if reindex:
        client.delete(
            collection_name=COLLECTION,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(
                    must=[qm.FieldCondition(key="doc_id", match=qm.MatchValue(value=doc_id))]
                )
            ),
        )

    model = get_embedder()
    texts = [normalize_text(s["text"]) for s in segments]
    vectors = embed_texts(model, texts)
    if len(vectors) != len(segments):
        raise RuntimeError("embed count mismatch")
    if vectors and len(vectors[0]) != EMBEDDING_DIM:
        raise RuntimeError(f"expected dim {EMBEDDING_DIM}, got {len(vectors[0])}")

    points: list[qm.PointStruct] = []
    for seg, vec in zip(segments, vectors, strict=True):
        pid = point_id(seg["doc_id"], seg["page"], seg["segment_id"])
        payload = {
            "doc_id": seg["doc_id"],
            "page": seg["page"],
            "segment_id": seg["segment_id"],
            "kind": seg["kind"],
            "text": seg["text"],
            "source_path": seg["source_path"],
            "content_hash": content_hash(seg["text"], None),
            "embedding_model": EMBEDDING_MODEL,
            "chunk_version": CHUNK_VERSION,
            "job_id": done["job_id"],
        }
        points.append(qm.PointStruct(id=pid, vector=vec, payload=payload))

    # Upsert in batches
    written = 0
    batch = 64
    for i in range(0, len(points), batch):
        chunk = points[i : i + batch]
        client.upsert(collection_name=COLLECTION, points=chunk, wait=True)
        written += len(chunk)
    return written, len(segments)


def main() -> None:
    ap = argparse.ArgumentParser(description="Ingest DONE job into exam_segments_v1")
    ap.add_argument("--job-dir", type=Path, required=True)
    ap.add_argument("--qdrant-url", default=os.environ.get("QDRANT_URL", "http://192.168.1.107:6333"))
    ap.add_argument(
        "--api-key",
        default=os.environ.get("QDRANT_WRITER_KEY") or os.environ.get("QDRANT_API_KEY"),
        help="Writer API key (not reader)",
    )
    ap.add_argument("--reindex", action="store_true")
    args = ap.parse_args()
    if not args.api_key:
        raise SystemExit("Set --api-key or QDRANT_WRITER_KEY to the writer key")

    n, total = ingest_job(args.job_dir, qdrant_url=args.qdrant_url, api_key=args.api_key, reindex=args.reindex)
    print(f"UPSERTED {n}/{total} points into {COLLECTION}")


if __name__ == "__main__":
    main()

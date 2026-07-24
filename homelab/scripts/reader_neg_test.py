#!/usr/bin/env python3
"""Reader key negative test: upsert/delete must fail; writer must succeed (then delete test point).

Usage (A):
  set QDRANT_URL=http://192.168.1.107:6333
  set QDRANT_READER_KEY=...
  set QDRANT_WRITER_KEY=...
  python homelab/scripts/reader_neg_test.py
"""
from __future__ import annotations

import os
import sys
import uuid

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm
from qdrant_client.http.exceptions import UnexpectedResponse

COLLECTION = "exam_segments_v1"
TEST_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "wave1-reader-neg-test"))


def _client(key: str) -> QdrantClient:
    url = os.environ.get("QDRANT_URL", "http://192.168.1.107:6333")
    return QdrantClient(url=url, api_key=key, prefer_grpc=False, check_compatibility=False)


def _expect_forbidden(label: str, fn) -> None:
    try:
        fn()
    except UnexpectedResponse as e:
        code = getattr(e, "status_code", None) or getattr(e, "status", None)
        msg = str(e).lower()
        if code in (401, 403) or "forbidden" in msg or "unauthorized" in msg or "403" in msg or "401" in msg:
            print(f"PASS reader {label}: denied ({code or 'auth'})")
            return
        print(f"FAIL reader {label}: unexpected UnexpectedResponse: {e}", file=sys.stderr)
        raise SystemExit(2) from e
    except Exception as e:
        msg = str(e).lower()
        if any(x in msg for x in ("403", "401", "forbidden", "unauthorized", "access")):
            print(f"PASS reader {label}: denied ({type(e).__name__})")
            return
        print(f"FAIL reader {label}: unexpected {type(e).__name__}: {e}", file=sys.stderr)
        raise SystemExit(2) from e
    print(f"FAIL reader {label}: operation succeeded (expected deny)", file=sys.stderr)
    raise SystemExit(2)


def main() -> None:
    reader = os.environ.get("QDRANT_READER_KEY") or os.environ.get("QDRANT__SERVICE__READ_ONLY_API_KEY")
    writer = os.environ.get("QDRANT_WRITER_KEY") or os.environ.get("QDRANT__SERVICE__API_KEY")
    if not reader or not writer:
        raise SystemExit("Set QDRANT_READER_KEY and QDRANT_WRITER_KEY")
    if reader == writer:
        raise SystemExit("reader and writer keys must differ")

    point = qm.PointStruct(
        id=TEST_ID,
        vector=[0.0] * 768,
        payload={"doc_id": "__wave1_neg__", "segment_id": "neg", "text": "neg-test"},
    )

    rc = _client(reader)
    _expect_forbidden("upsert", lambda: rc.upsert(collection_name=COLLECTION, points=[point], wait=True))
    _expect_forbidden(
        "delete",
        lambda: rc.delete(
            collection_name=COLLECTION,
            points_selector=qm.PointIdsList(points=[TEST_ID]),
        ),
    )

    wc = _client(writer)
    wc.upsert(collection_name=COLLECTION, points=[point], wait=True)
    print("PASS writer upsert")
    wc.delete(collection_name=COLLECTION, points_selector=qm.PointIdsList(points=[TEST_ID]))
    print("PASS writer delete (cleanup)")
    print("OK: reader negative test passed")


if __name__ == "__main__":
    main()

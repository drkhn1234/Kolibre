"""Rebuildable per-library passage indexes. No identity or ACL cache.

Exact cosine scoring intentionally avoids a vector daemon/ANN prefilter contract.
SQLite is the storage boundary; replacing the backend does not change the API.
"""

import hashlib
import json
import math
import os
import posixpath
import re
import sqlite3
import time
import threading
import zipfile
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

from .. import config, database, models
from ..calibre.library import CalibreLibrary

INDEX = "knowledge.sqlite3"
VERSION = "epub-spine-words-v1"


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        if tag in ("p", "div", "br", "h1", "h2", "h3"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        self.parts.append(" ")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def passages(path):
    """EPUB spine order; offsets are normalized section word offsets, not CFIs."""
    with zipfile.ZipFile(path) as z:
        if sum(i.file_size for i in z.infolist()) > 100_000_000:
            raise ValueError("EPUB uncompressed size exceeds 100 MB")
        container = ET.fromstring(z.read("META-INF/container.xml"))
        opf = next(
            e.attrib["full-path"]
            for e in container.iter()
            if e.tag.endswith("rootfile")
        )
        root = ET.fromstring(z.read(opf))
        manifest = {
            e.attrib["id"]: e.attrib.get("href", "")
            for e in root.iter()
            if e.tag.endswith("}item")
        }
        for ref in root.iter():
            if not ref.tag.endswith("itemref"):
                continue
            section = posixpath.normpath(
                posixpath.join(posixpath.dirname(opf), manifest[ref.attrib["idref"]])
            )
            parser = Text()
            parser.feed(z.read(section).decode("utf-8", errors="replace"))
            words = " ".join(parser.parts).split()
            for start in range(0, len(words), 160):
                text = " ".join(words[start : start + 200])
                if text:
                    yield {"section": section, "word_start": start, "text": text}


def fingerprint(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized(vector):
    vector = [float(x) for x in vector]
    norm = math.sqrt(sum(x * x for x in vector))
    if not vector or not math.isfinite(norm) or norm == 0:
        raise ValueError("Invalid embedding")
    return [x / norm for x in vector]


class Embeddings:
    def __init__(self):
        self.lock = threading.Lock()
        self.provider = os.environ.get("KOLIBRE_EMBED_PROVIDER", "fastembed")
        self.model = os.environ.get("KOLIBRE_EMBED_MODEL", "BAAI/bge-small-en-v1.5")
        self.identity = json.dumps(
            [
                VERSION,
                self.provider,
                self.model,
                os.environ.get("KOLIBRE_EMBED_URL", ""),
                os.environ.get("KOLIBRE_EMBED_REVISION", "1"),
            ]
        )
        if self.provider == "fastembed":
            from fastembed import TextEmbedding

            self.engine = TextEmbedding(
                model_name=self.model,
                threads=1,
                cache_dir=os.path.join(config.DATA_DIR, "embedding-models"),
            )
        elif self.provider != "openai":
            raise ValueError("Unsupported embedding provider")

    def encode(self, texts, query=False):
        if not texts:
            return []
        if self.provider == "fastembed":
            with self.lock:
                method = self.engine.query_embed if query else self.engine.passage_embed
                vectors = list(method(texts))
        else:
            import httpx

            url = os.environ["KOLIBRE_EMBED_URL"]
            if not url.startswith("https://"):
                raise ValueError("Hosted embeddings require HTTPS")
            with httpx.Client(timeout=60, trust_env=False) as client:
                r = client.post(
                    url,
                    headers={
                        "Authorization": "Bearer " + os.environ["KOLIBRE_EMBED_KEY"]
                    },
                    json={"model": self.model, "input": texts},
                )
                r.raise_for_status()
                vectors = [
                    x["embedding"]
                    for x in sorted(r.json()["data"], key=lambda x: x["index"])
                ]
        if len(vectors) != len(texts):
            raise ValueError("Embedding count mismatch")
        result = [normalized(v) for v in vectors]
        if len({len(v) for v in result}) != 1:
            raise ValueError("Embedding dimension mismatch")
        return result


@lru_cache(maxsize=1)
def _embedder():
    return Embeddings()


_model_lock = threading.Lock()


def embedder():
    with _model_lock:
        return _embedder()


def connect(path):
    db = sqlite3.connect(os.path.join(path, INDEX), timeout=30)
    db.row_factory = sqlite3.Row
    db.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS sources(book INTEGER PRIMARY KEY, digest TEXT, model TEXT);
    CREATE TABLE IF NOT EXISTS passages(id INTEGER PRIMARY KEY, book INTEGER, section TEXT, word_start INTEGER, text TEXT, vector TEXT);
    CREATE VIRTUAL TABLE IF NOT EXISTS lexical USING fts5(text);
    """)
    return db


def sync_library(path, engine):
    """Worker-only, atomic per-book replacement. Failure retains old rows,
    which retrieval suppresses by fingerprint/model; originals are never edited.
    """
    if not os.path.isfile(os.path.join(path, "metadata.db")):
        return
    lib = CalibreLibrary(path)
    books = lib.list_books()
    with connect(path) as db:
        existing = {r["book"]: r for r in db.execute("SELECT * FROM sources")}
        live = set()
        for book in books:
            bid = book["id"]
            source = lib.get_format_file_path(bid, "EPUB")
            if not source:
                continue
            live.add(bid)
            digest = fingerprint(source)
            old = existing.get(bid)
            if old and old["digest"] == digest and old["model"] == engine.identity:
                continue
            chunks = list(passages(source))
            vectors = []
            for i in range(0, len(chunks), 32):
                vectors.extend(engine.encode([c["text"] for c in chunks[i : i + 32]]))
            if fingerprint(source) != digest:
                continue
            with db:
                ids = [
                    r[0]
                    for r in db.execute("SELECT id FROM passages WHERE book=?", (bid,))
                ]
                db.executemany("DELETE FROM lexical WHERE rowid=?", [(i,) for i in ids])
                db.execute("DELETE FROM passages WHERE book=?", (bid,))
                for chunk, vector in zip(chunks, vectors):
                    row = db.execute(
                        "INSERT INTO passages(book,section,word_start,text,vector) VALUES(?,?,?,?,?)",
                        (
                            bid,
                            chunk["section"],
                            chunk["word_start"],
                            chunk["text"],
                            json.dumps(vector),
                        ),
                    )
                    db.execute(
                        "INSERT INTO lexical(rowid,text) VALUES(?,?)",
                        (row.lastrowid, chunk["text"]),
                    )
                db.execute(
                    "INSERT OR REPLACE INTO sources VALUES(?,?,?)",
                    (bid, digest, engine.identity),
                )
        with db:
            for bid in set(existing) - live:
                db.execute(
                    "DELETE FROM lexical WHERE rowid IN (SELECT id FROM passages WHERE book=?)",
                    (bid,),
                )
                db.execute("DELETE FROM passages WHERE book=?", (bid,))
                db.execute("DELETE FROM sources WHERE book=?", (bid,))


def candidates(path, engine, query, vector):
    """Called ONLY after library authorization. Filter stale books before ranking."""
    if not os.path.exists(os.path.join(path, INDEX)):
        return [], 0
    lib = CalibreLibrary(path)
    books = {b["id"]: b for b in lib.list_books()}
    with connect(path) as db:
        valid = {}
        for source in db.execute(
            "SELECT * FROM sources WHERE model=?", (engine.identity,)
        ):
            file = lib.get_format_file_path(source["book"], "EPUB")
            if (
                source["book"] in books
                and file
                and fingerprint(file) == source["digest"]
            ):
                valid[source["book"]] = source["digest"]
        tokens = re.findall(r"\w+", query)[:40]
        match = " OR ".join('"' + x + '"' for x in tokens)
        lexical = (
            {
                r[0]: rank
                for rank, r in enumerate(
                    db.execute(
                        "SELECT rowid FROM lexical WHERE lexical MATCH ? ORDER BY bm25(lexical)",
                        (match,),
                    ),
                    1,
                )
            }
            if match
            else {}
        )
        result = []
        for row in db.execute("SELECT * FROM passages"):
            if row["book"] not in valid:
                continue
            stored = json.loads(row["vector"])
            if len(stored) != len(vector):
                continue
            result.append(
                {
                    "book_id": row["book"],
                    "title": books[row["book"]]["title"],
                    "author": books[row["book"]]["author"],
                    "section": row["section"],
                    "word_start": row["word_start"],
                    "text": row["text"],
                    "source_sha256": valid[row["book"]],
                    "kind": "passage",
                    "_cosine": sum(a * b for a, b in zip(stored, vector)),
                    "_lexical": lexical.get(row["id"]),
                }
            )
        return result, len(books) - len(valid)


def rank(items, query, mode, limit):
    semantic = sorted(
        range(len(items)), key=lambda i: items[i]["_cosine"], reverse=True
    )
    lexical = sorted(
        [i for i in range(len(items)) if items[i].get("_lexical")],
        key=lambda i: items[i]["_lexical"],
    )
    scores = {}
    for order in (
        [semantic]
        if mode == "semantic"
        else [lexical]
        if mode == "lexical"
        else [semantic, lexical]
    ):
        for n, i in enumerate(order, 1):
            scores[i] = scores.get(i, 0) + 1 / (60 + n)
    output = []
    for i in sorted(scores, key=scores.get, reverse=True)[:limit]:
        item = {k: v for k, v in items[i].items() if not k.startswith("_")}
        item["score"] = scores[i]
        output.append(item)
    return output


def worker(once=False):
    import logging
    import fcntl

    os.makedirs(config.DATA_DIR, exist_ok=True)
    lock = open(os.path.join(config.DATA_DIR, "knowledge-worker.lock"), "w")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    while True:
        with database.SessionLocal() as db:
            folders = [r.folder_name for r in db.query(models.Library).all()]
        for folder in folders:
            try:
                sync_library(config.library_path(folder), embedder())
            except Exception:
                logging.exception("Knowledge indexing failed for a registered library")
        if once:
            return
        time.sleep(30)


if __name__ == "__main__":
    import sys

    worker(once="--once" in sys.argv)

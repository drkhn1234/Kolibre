"""Authenticated retrieval over current authorized sources, never global top-k."""

import os
import re
from typing import Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .. import auth, config, database, models
from ..calibre.library import CalibreLibrary
from ..services import knowledge, permessi
from .libraries import require_library_access

router = APIRouter(prefix="/api/kolibre/knowledge", tags=["knowledge"])


@router.get("/search")
def search(
    q: str = Query(min_length=1, max_length=500),
    library: str | None = None,
    mode: Literal["hybrid", "semantic", "lexical"] = "hybrid",
    limit: int = Query(default=10, ge=1, le=30),
    include_annotations: bool = True,
    user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    if os.environ.get("KOLIBRE_KNOWLEDGE_ENABLED") != "1":
        raise HTTPException(503, "Knowledge retrieval is not enabled")
    if library is not None:
        library = require_library_access(db, user, library)
    folders = [
        r.folder_name
        for r in permessi.biblioteche_visibili(db, user)
        if library is None or r.folder_name == library
    ]
    try:
        engine = knowledge.embedder()
        vector = engine.encode([q], query=True)[0]
        items = []
        pending = 0
        for folder in folders:
            rows, missing = knowledge.candidates(
                config.library_path(folder), engine, q, vector
            )
            pending += missing
            for row in rows:
                row["library"] = folder
            items.extend(rows)
        if include_annotations and folders:
            notes = (
                db.query(models.Highlight)
                .filter(
                    models.Highlight.user_id == user.id,
                    models.Highlight.library.in_(folders),
                )
                .all()
            )
            entries = []
            for note in notes:
                book = CalibreLibrary(config.library_path(note.library)).get_book(
                    note.calibre_book_id
                )
                if not book:
                    continue
                entries.append(
                    {
                        "kind": "annotation",
                        "annotation_id": note.id,
                        "library": note.library,
                        "book_id": note.calibre_book_id,
                        "title": book["title"],
                        "author": CalibreLibrary(
                            config.library_path(note.library)
                        ).get_book_author(note.calibre_book_id),
                        "section": note.chapter,
                        "page": note.page,
                        "cfi_start": note.cfi_start,
                        "text": note.text
                        + ("\n" + note.comment if note.comment else ""),
                    }
                )
            for start in range(0, len(entries), 32):
                batch = entries[start : start + 32]
                vectors = engine.encode([e["text"] for e in batch])
                for entry, v in zip(batch, vectors):
                    entry["_cosine"] = sum(a * b for a, b in zip(vector, v))
                    entry["_lexical"] = (
                        1
                        if set(re.findall(r"\w+", q.lower()))
                        & set(re.findall(r"\w+", entry["text"].lower()))
                        else None
                    )
                    items.append(entry)
        results = knowledge.rank(items, q, mode, limit)
        # Fresh permission query and source check before releasing text. No result cache.
        db.expire_all()
        allowed = {r.folder_name for r in permessi.biblioteche_visibili(db, user)}
        final = []
        for result in results:
            folder = result["library"]
            if folder not in allowed:
                continue
            lib = CalibreLibrary(config.library_path(folder))
            if not lib.get_book(result["book_id"]):
                continue
            if result["kind"] == "passage":
                file = lib.get_format_file_path(result["book_id"], "EPUB")
                if not file or knowledge.fingerprint(file) != result["source_sha256"]:
                    continue
            else:
                note = (
                    db.query(models.Highlight)
                    .filter_by(
                        id=result["annotation_id"],
                        user_id=user.id,
                        library=folder,
                        calibre_book_id=result["book_id"],
                    )
                    .first()
                )
                if note is None or result["text"] != note.text + (
                    "\n" + note.comment if note.comment else ""
                ):
                    continue
            result["source_url"] = (
                f"/api/kolibre/books/{result['book_id']}/download?"
                + urlencode({"library": folder, "format": "EPUB"})
            )
            result["location_type"] = (
                "annotation"
                if result["kind"] == "annotation"
                else "epub-section-normalized-word-offset"
            )
            final.append(result)
        return {
            "results": final,
            "pending_books": pending,
            "embedding_model": engine.identity,
            "ranking": mode,
        }
    except HTTPException:
        raise
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Knowledge retrieval failed")
        # Provider URLs/bodies and file paths must not escape in API errors.
        raise HTTPException(
            503, "Knowledge index or embedding provider unavailable"
        ) from None

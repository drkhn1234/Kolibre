"""Durable, owner-only reconciliation for interrupted shared-to-private moves.

Source deletion is the commit point: before it, roll back the private copy;
after it, finish moving only the owner's personal metadata. Never delete
another user's data or a source book during recovery.
"""
import json
import hashlib
import os
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import config, models
from ..calibre.library import CalibreLibrary
from .private_book_move import migrate_owner_records

_ACTIVE_STATES = ("copying", "ready", "source_deleted", "needs_review")


def _format_files(library, book_id):
    """Catalog rows alone cannot prove that a book's bytes survived a crash."""
    files = {}
    for row in library.get_formats(book_id):
        path = library.get_format_file_path(book_id, row["format"])
        if not path or not os.path.isfile(path) or os.path.getsize(path) <= 0:
            raise ValueError("Book format missing or incomplete")
        files[row["format"]] = path
    return files


def source_safe_for_rollback(source, source_id, target, target_id):
    """Prove source files exist and agree with every registered target copy.

    Comparing full SHA-256 digests detects truncation and same-size corruption.
    Calibre's recorded sizes may be stale after EPUB metadata rewrites, so
    they are not evidence of file integrity. Any uncertainty preserves both
    copies, even if the corrupt file might actually be the target.
    """
    try:
        source_files = _format_files(source, source_id)
        if not source_files:
            return False
        target_formats = target.get_formats(target_id)
        if not target_formats:
            return False
        for row in target_formats:
            fmt = row["format"]
            target_path = target.get_format_file_path(target_id, fmt)
            if fmt not in source_files or not target_path:
                return False
            with open(source_files[fmt], "rb") as src, open(target_path, "rb") as dst:
                if hashlib.file_digest(src, "sha256").digest() != hashlib.file_digest(dst, "sha256").digest():
                    return False
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


def begin(db: Session, user_id: int, source: str, book_id: int, target: str):
    if not user_id or source == target:
        raise ValueError("Move must have an owner and separate libraries")
    # JSON avoids ambiguous delimiters in arbitrary library names.
    key = json.dumps([source, book_id], ensure_ascii=False)
    row = models.PrivateBookMove(
        owner_id=user_id, source_library=source, source_book_id=book_id,
        target_library=target, token=uuid4().hex,
        active_key=key, state="copying",
    )
    try:
        db.add(row)
        db.commit()  # Durable BEFORE any Calibre modification.
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Private move already pending")
    return row


def checkpoint(db: Session, move, state: str, target_id: int | None = None):
    if state not in ("copying", "ready", "source_deleted", "completed", "rolled_back", "needs_review"):
        raise ValueError("Unknown private move checkpoint")
    if target_id is not None:
        move.target_book_id = target_id
    move.state = state
    if state in ("completed", "rolled_back"):
        move.active_key = None
        move.failure_code = None
    move.updated_at = datetime.utcnow()
    db.commit()


def private_move_for_user(db: Session, move_id: int, user_id: int):
    row = db.query(models.PrivateBookMove).filter(
        models.PrivateBookMove.id == move_id,
        models.PrivateBookMove.owner_id == user_id,
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Private move not found")
    return row


def serialize_move(row):
    """Never serialize filesystem paths, tokens, other users, or book titles."""
    return {
        "id": row.id,
        "source_library": row.source_library,
        "source_book_id": row.source_book_id,
        "target_library": row.target_library,
        "target_book_id": row.target_book_id,
        "state": row.state,
        "failure_code": row.failure_code,
    }


async def reconcile(db: Session, move, write_queue):
    """Reconcile one interrupted move (callable only by the record owner).

    A finished private copy is never removed if the source book is already
    gone. Never guess the target by title: the recovery token is atomic with
    Calibre insertion and must identify the exact target before touching it.
    """
    if move.state in ("completed", "rolled_back"):
        return serialize_move(move)

    source = CalibreLibrary(config.library_path(move.source_library))
    target = CalibreLibrary(config.library_path(move.target_library))
    source_present = source.get_book(move.source_book_id) is not None

    target_id = target.find_book_by_private_move_token(move.token)
    if target_id is not None:
        if move.target_book_id is not None and move.target_book_id != target_id:
            move.state = "needs_review"
            move.failure_code = "target_id_mismatch"
            db.commit()
            return serialize_move(move)
        if move.target_book_id is None:
            checkpoint(db, move, move.state, target_id=target_id)
    else:
        # No unambiguous target to clean up or finish.
        if source_present and move.target_book_id is None:
            checkpoint(db, move, "rolled_back")
        else:
            move.state = "needs_review"
            move.failure_code = "target_not_identified"
            db.commit()
        return serialize_move(move)

    if source_present:
        # A surviving row does not prove its files survived. Never discard
        # the only valid copy merely because the source catalog still lists it.
        if not source_safe_for_rollback(source, move.source_book_id, target, target_id):
            move.state = "needs_review"
            move.failure_code = "source_integrity_unverified"
            db.commit()
            return serialize_move(move)
        # Source files are intact; it is safe to undo the private copy. Queue must
        # NOT replay this deletion at a later time if it fails now.
        try:
            await write_queue.submit(
                "delete_book", {"book_id": target_id},
                config.library_path(move.target_library),
                _skip_persist_on_failure=True,
            )
        except Exception:
            db.rollback()
            move.state = "needs_review"
            move.failure_code = "target_cleanup_failed"
            db.commit()
            return serialize_move(move)
        # Target's app.db BookHash was inserted before the move completed.
        db.query(models.BookHash).filter(
            models.BookHash.library == move.target_library,
            models.BookHash.calibre_book_id == target_id,
        ).delete(synchronize_session=False)
        checkpoint(db, move, "rolled_back")
        return serialize_move(move)

    # A source disappearing while the copy was still in progress does NOT
    # prove the new private copy was complete. Keep its journal locked and
    # request manual review rather than silently accepting an incomplete book.
    if move.state not in ("ready", "source_deleted"):
        # Review is not a durable ready checkpoint. Retrying a previously
        # incomplete copy must never promote it to a completed move.
        if move.state == "needs_review":
            return serialize_move(move)
        move.state = "needs_review"
        move.failure_code = "source_missing_before_copy_ready"
        db.commit()
        return serialize_move(move)

    # Source was deleted, so the target is the only Calibre copy left.
    # This update is idempotent: only rows still keyed by the old shared
    # book identity can be moved, preventing duplicate records on retry.
    migrate_owner_records(
        db, move.source_library, move.source_book_id,
        move.target_library, target_id, move.owner_id,
    )
    checkpoint(db, move, "completed")
    return serialize_move(move)

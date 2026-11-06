"""Durable, owner-only reconciliation for interrupted shared-to-private moves.

Source deletion is the commit point: before it, roll back the private copy;
after it, finish moving only the owner's personal metadata. Never delete
another user's data or a source book during recovery.
"""
import json
from datetime import datetime
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import config, models
from ..calibre.library import CalibreLibrary
from .private_book_move import migrate_owner_records

_ACTIVE_STATES = ("copying", "ready", "source_deleted", "needs_review")


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
        # Source is intact; it is safe to undo the private copy. Queue must
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
    if move.state == "copying":
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

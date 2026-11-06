"""Move only one account's reading state when a shared book becomes private.

A private move is NOT a normal cross-library move: the shared copy is removed,
but another reader's highlights, positions, and already-downloaded device
records must never be transferred into the mover's private library.
"""
from sqlalchemy.orm import Session

from .. import models


_PERSONAL_BOOK_MODELS = (
    models.ReadingPosition,
    models.ReadingSession,
    models.Highlight,
    models.BookReadingCoverage,
)


def migrate_owner_records(
    db: Session, source_library: str, source_book_id: int,
    target_library: str, target_book_id: int, owner_id: int,
) -> dict:
    """Repoint only owner-scoped records. Caller owns transaction/commit.

    Shared, ownerless data (BookHashHistory/StatsHashPairing) is intentionally
    NOT remapped to the new private library. No foreign user's data is changed.
    Existing file copies on other devices are left untouched.
    """
    if not owner_id or source_library == target_library:
        raise ValueError("Private migration requires an owner and separate libraries")

    moved = {}
    for model in _PERSONAL_BOOK_MODELS:
        q = db.query(model).filter(
            model.user_id == owner_id,
            model.library == source_library,
            model.calibre_book_id == source_book_id,
        )
        moved[model.__tablename__] = q.update(
            {"library": target_library, "calibre_book_id": target_book_id},
            synchronize_session=False,
        )

    # The owner's KOReader devices keep their files. Only the server-side
    # book identity changes; no forced device-side removal/re-download.
    owned_device_ids = db.query(models.Device.id).filter(
        models.Device.user_id == owner_id
    )
    moved["device_books"] = db.query(models.DeviceBook).filter(
        models.DeviceBook.device_id.in_(owned_device_ids),
        models.DeviceBook.library == source_library,
        models.DeviceBook.calibre_book_id == source_book_id,
    ).update(
        {"library": target_library, "calibre_book_id": target_book_id},
        synchronize_session=False,
    )

    # Legacy device sync queue entries have the same owner requirement.
    moved["sync_queue"] = db.query(models.SyncQueue).filter(
        models.SyncQueue.device_id.in_(owned_device_ids),
        models.SyncQueue.library == source_library,
        models.SyncQueue.calibre_book_id == source_book_id,
    ).update(
        {"library": target_library, "calibre_book_id": target_book_id},
        synchronize_session=False,
    )

    candidates = db.query(models.DeviceFlaggedBook).filter(
        models.DeviceFlaggedBook.device_id.in_(owned_device_ids),
        models.DeviceFlaggedBook.candidate_library == source_library,
        models.DeviceFlaggedBook.candidate_calibre_book_id == source_book_id,
    )
    moved["device_flagged_candidates"] = candidates.update(
        {"candidate_library": target_library,
         "candidate_calibre_book_id": target_book_id},
        synchronize_session=False,
    )
    pending = db.query(models.DeviceFlaggedBook).filter(
        models.DeviceFlaggedBook.device_id.in_(owned_device_ids),
        models.DeviceFlaggedBook.pending_action_library == source_library,
        models.DeviceFlaggedBook.pending_action_calibre_book_id == source_book_id,
    )
    moved["device_flagged_pending"] = pending.update(
        {"pending_action_library": target_library,
         "pending_action_calibre_book_id": target_book_id},
        synchronize_session=False,
    )

    # Cached per-library stats are stale for this person only. Other users'
    # reading stats, bookmarks, and book associations remain in the source.
    moved["stats_cache_invalidated"] = db.query(models.StatsCache).filter(
        models.StatsCache.user_id == owner_id,
        models.StatsCache.library.in_((source_library, target_library)),
    ).delete(synchronize_session=False)

    # The shared source file is about to be removed; don't advertise its old
    # live checksum as a public book. The new private copy has its own BookHash.
    moved["shared_live_hashes_removed"] = db.query(models.BookHash).filter(
        models.BookHash.library == source_library,
        models.BookHash.calibre_book_id == source_book_id,
    ).delete(synchronize_session=False)

    return moved

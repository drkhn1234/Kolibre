"""Authorization for staged book imports.

A NULL uploader_id denotes a filesystem-watched or legacy item, reviewed only
by the founder. Uploaded items belong exclusively to their authenticated user.
"""
from fastapi import HTTPException
from sqlalchemy import or_
from uuid import uuid4
from .. import config
from ..calibre.library import CalibreLibrary
from .. import models
from . import permessi


def visible_ingest_query(db, user):
    query = db.query(models.IngestedBook)
    if user.is_founder:
        return query.filter(or_(models.IngestedBook.uploader_id == user.id,
                                models.IngestedBook.uploader_id.is_(None)))
    return query.filter(models.IngestedBook.uploader_id == user.id)


def get_accessible_ingest(db, user, ingest_id):
    item = visible_ingest_query(db, user).filter(
        models.IngestedBook.id == ingest_id
    ).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Staged book not found")
    return item


def require_upload_library(db, user, library_name):
    """Use the existing registered library only if uploading is authorized."""
    from ..api.libraries import resolve_default_library_folder, resolve_folder_name

    candidate = library_name or resolve_default_library_folder(db)
    if not candidate:
        raise HTTPException(status_code=404, detail="No library configured")
    folder = resolve_folder_name(db, candidate)
    library = db.query(models.Library).filter(
        models.Library.folder_name == folder
    ).first()
    if library is None or not permessi.puo_caricare(db, user, library):
        raise HTTPException(status_code=403, detail="No upload permission for this library")
    return library.folder_name


def ensure_private_library(db, user):
    """Create the user's first personal Calibre library on demand.

    Private libraries cannot be shared, even by the founder. Generated slugs
    prevent collisions with a user's existing public library names.
    """
    private = db.query(models.Library).filter(
        models.Library.owner_id == user.id,
        models.Library.is_private.is_(True),
    ).order_by(models.Library.id).first()
    if private:
        return private

    from ..api.libraries import _next_sort_order
    folder = f"private_{user.id}_{uuid4().hex[:12]}"
    name = f"Private ({user.username}) - {folder[-6:]}"
    path = config.library_path(folder)
    CalibreLibrary(path, crea=True)
    private = models.Library(
        name=name, folder_name=folder, path=path,
        owner_id=user.id, is_private=True, sort_order=_next_sort_order(db),
    )
    db.add(private)
    db.commit()
    return private


def require_ingest_destination(db, user, staged, requested_library):
    """Resolve the destination; a private upload cannot fall back to shared."""
    if staged.is_private:
        return ensure_private_library(db, user).folder_name
    return require_upload_library(db, user, requested_library)

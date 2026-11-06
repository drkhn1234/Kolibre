"""Authorization for staged book imports.

A NULL uploader_id denotes a filesystem-watched or legacy item, reviewed only
by the founder. Uploaded items belong exclusively to their authenticated user.
"""
from fastapi import HTTPException
from sqlalchemy import or_
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

"""One-time ownership migration for catalogs predating library ACLs."""
from .. import models


def migrate_legacy_library_permissions(db, founder):
    # A missing grant on an owned library means no access, including after
    # revocation. Never reconstruct such grants on startup. Only unowned,
    # non-private catalogs demonstrably predate the ownership model.
    legacy = db.query(models.Library).filter(
        models.Library.owner_id.is_(None),
        models.Library.is_private.is_(False),
    ).all()
    others = db.query(models.User).filter(models.User.id != founder.id).all()
    existing = {
        (row.user_id, row.library_id)
        for row in db.query(models.LibraryPermission).all()
    }
    for library in legacy:
        library.owner_id = founder.id
        for user in others:
            if (user.id, library.id) not in existing:
                db.add(models.LibraryPermission(
                    user_id=user.id, library_id=library.id,
                    can_edit=True, can_share=False, can_manage=False,
                ))
    # Caller commits ownership and grants together: restart cannot replay
    # the migration after a later revocation. Ownerless private catalogs
    # remain inaccessible, rather than being assigned to the founder.

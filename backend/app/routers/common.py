import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Base


def get_or_404[M: Base](db: Session, model: type[M], object_id: uuid.UUID) -> M:
    obj = db.get(model, object_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{model.__name__} not found")
    return obj

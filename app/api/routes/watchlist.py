"""Watchlist CRUD routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models import User, Watchlist
from app.schemas.trading import WatchlistCreate, WatchlistOut

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("", response_model=list[WatchlistOut])
def list_watchlist(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return (
        db.query(Watchlist)
        .filter(Watchlist.user_id == current_user.id)
        .order_by(Watchlist.created_at.desc())
        .all()
    )


@router.post("", response_model=WatchlistOut, status_code=status.HTTP_201_CREATED)
def add_watchlist(
    payload: WatchlistCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = Watchlist(user_id=current_user.id, **payload.model_dump())
    item.symbol = item.symbol.upper()
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watchlist(item_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.get(Watchlist, item_id)
    if not item or item.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    db.delete(item)
    db.commit()

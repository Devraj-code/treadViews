"""Seed demo data: a demo user with a watchlist and a sample schedule.

Run with:  python -m app.db.seed
"""
from __future__ import annotations

import logging

from app.core.security import hash_password
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models import Schedule, ScheduleInterval, User, UserRole, Watchlist

logger = logging.getLogger(__name__)

DEMO_EMAIL = "demo@tvai.app"
DEMO_PASSWORD = "Demo@12345"
DEMO_SYMBOLS = [
    ("NSE:NIFTY", "NSE", "1D"),
    ("NSE:BANKNIFTY", "NSE", "1h"),
    ("NSE:RELIANCE", "NSE", "1D"),
    ("BINANCE:BTCUSDT", "BINANCE", "4h"),
]


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == DEMO_EMAIL).first()
        if not user:
            user = User(
                email=DEMO_EMAIL,
                password_hash=hash_password(DEMO_PASSWORD),
                full_name="Demo Trader",
                role=UserRole.user,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info("Created demo user %s / %s", DEMO_EMAIL, DEMO_PASSWORD)

        if not db.query(Watchlist).filter(Watchlist.user_id == user.id).first():
            for symbol, exch, tf in DEMO_SYMBOLS:
                db.add(Watchlist(user_id=user.id, symbol=symbol, exchange=exch, timeframe=tf))
            db.add(
                Schedule(
                    user_id=user.id,
                    symbol="NSE:NIFTY",
                    timeframe="1D",
                    indicators=["RSI", "MACD", "EMA"],
                    interval=ScheduleInterval.hourly,
                )
            )
            db.commit()
            logger.info("Seeded demo watchlist + schedule")
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed()
    print("Seed complete. Demo login:", DEMO_EMAIL, "/", DEMO_PASSWORD)

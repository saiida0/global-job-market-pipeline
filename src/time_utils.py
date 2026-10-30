import logging
from datetime import datetime, timezone


logger = logging.getLogger(__name__)


def get_utc_now() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        logger.warning("Naive datetime received; assuming UTC: %r", dt)
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_for_db(dt: datetime) -> str:
    return to_utc(dt).isoformat()
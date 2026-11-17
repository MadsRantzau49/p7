from datetime import UTC, datetime


def to_utc_iso(date_time: datetime) -> str:
    """Write an aware datetime into UTC."""
    if date_time.tzinfo is None:
        raise ValueError(f"{date_time} has no timezone")
    return date_time.astimezone(UTC).isoformat()

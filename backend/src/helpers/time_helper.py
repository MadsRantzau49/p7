import re

TIMESTAMP_FORMAT = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?")


def check_timestamp_format(value):
    if isinstance(value, str):
        value = value.strip()
        if not TIMESTAMP_FORMAT.fullmatch(value):
            raise ValueError(
                "timestamp must be YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD HH:MM:SS, e.g. 2024-01-31 14:05:00"
            )
    return value

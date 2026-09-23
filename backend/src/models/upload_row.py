import re
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, NaiveDatetime

MAX_VEHICLE_ID = 2147483647
TIMESTAMP_FORMAT = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?")

class VehicleType(StrEnum):
    CAR = "CAR"
    TAXI = "TAXI"
    UNKNOWN = "UNKNOWN"

def check_timestamp_format(value):
    if isinstance(value, str):
        value = value.strip()
        if not TIMESTAMP_FORMAT.fullmatch(value):
            raise ValueError("timestamp must be YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD HH:MM:SS, e.g. 2024-01-31 14:05:00")
    return value

class UploadRow(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    trajectory_id: str = Field(min_length=1, max_length=255)
    vehicle_id: int = Field(ge=0, le=MAX_VEHICLE_ID)
    vehicle_type: VehicleType
    timestamp: Annotated[NaiveDatetime, BeforeValidator(check_timestamp_format)]
    longitude: float= Field(ge=-180, le=180, allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
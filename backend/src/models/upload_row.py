from enum import StrEnum
from typing import Annotated

from helpers.time_helper import check_timestamp_format
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, NaiveDatetime

MAX_VEHICLE_ID = 2147483647


def empty_csv_value_as_none(value):
    """Represent an empty nullable CSV cell as None."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


class VehicleType(StrEnum):
    CAR = "CAR"
    TAXI = "TAXI"
    UNKNOWN = "UNKNOWN"


class UploadRow(BaseModel):
    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    trajectory_id: str = Field(min_length=1, max_length=255)
    vehicle_id: int = Field(ge=0, le=MAX_VEHICLE_ID)
    vehicle_type: VehicleType
    timestamp: Annotated[NaiveDatetime, BeforeValidator(check_timestamp_format)]
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    city: Annotated[str | None, BeforeValidator(empty_csv_value_as_none)] = Field(
        default=None, max_length=255
    )
    source_id: Annotated[str | None, BeforeValidator(empty_csv_value_as_none)] = Field(
        default=None, max_length=255
    )
    database_trajectory_id: Annotated[int | None, BeforeValidator(empty_csv_value_as_none)] = Field(
        default=None, ge=0
    )

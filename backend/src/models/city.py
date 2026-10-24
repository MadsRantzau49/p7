from dataclasses import dataclass


@dataclass
class City:
    city_id: int
    name: str
    time_zone: str

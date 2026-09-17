from dataclasses import dataclass

@dataclass
class porto_trajectory:
    trip_id: int 
    call_type: str | None
    origin_call: str | None
    origin_stand: str | None
    taxi_id: int
    timestamp: int 
    day_type: str | None
    missing_data: bool
    polyline: list[list[float]]

    source_id: int | None = None # source_id is used for bridge tabel, to determine where the data origins from
        

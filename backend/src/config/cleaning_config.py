from dataclasses import dataclass


@dataclass(frozen=True)
class CleaningConfig:
    bbox: tuple[float, float, float, float]  # lat min, max + lon min, max
    max_speed: float  # m/2
    max_accel: float  # (m/s)^2
    max_identical_coords: int  # Coords allowed to be identical before drop
    gap_time: float  # sec
    gap_distance: float  # meter
    min_points: int  # minimum allowed points for trajectory


PORTO = CleaningConfig(
    bbox=(40.9, 41.4, -8.8, -8.4),
    max_speed=50.0,
    max_accel=10.0,
    max_identical_coords=4,
    gap_time=60.0,
    gap_distance=500.0,
    min_points=2,
)

BEIJING = CleaningConfig(
    bbox=(39.4, 41.1, 115.4, 117.5),
    max_speed=50.0,
    max_accel=10.0,
    max_identical_coords=4,
    gap_time=900.0,
    gap_distance=10000.0,
    min_points=2,
)

_CONFIGS = {
    "Porto": PORTO,
    "Beijing": BEIJING,
}


def get_config(city: str) -> CleaningConfig:
    """Returns configuration for input city"""
    try:
        return _CONFIGS[city]
    except KeyError:
        raise KeyError(f"Clean config missing {city}") from None

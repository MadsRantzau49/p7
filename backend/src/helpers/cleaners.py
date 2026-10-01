import math

from models.UniformedTrajectories import UniformedTrajectoryPoint

EARTH_RADIUS_M = 6_371_000

# Helper method to find sphere difference in meters betweeen points. https://en.wikipedia.org/wiki/Haversine_formula
def _haversine(first_point: UniformedTrajectoryPoint, second_point: UniformedTrajectoryPoint) -> float:
    lat1 = math.radians(first_point.latitude)
    lat2 = math.radians(second_point.latitude)
    difference_in_lat = lat2 - lat1
    difference_in_lon = math.radians(second_point.longitude - first_point.longitude)
    h = math.sin(difference_in_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(difference_in_lon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


# Drop all points not within city limits
def drop_out_of_bounds(points: list[UniformedTrajectoryPoint], bbox: tuple[float, float, float, float]) -> tuple[list[UniformedTrajectoryPoint], int]: 
    lat_min, lat_max, lon_min, lon_max = bbox

    kept = [
        point
        for point in points 
            if lat_min < point.latitude < lat_max and lon_min < point.longitude < lon_max
    ]

    return kept, len(points) - len(kept)

# Drop all points with older timestamps than last point (2 should have newer timestamp than 1) 
def drop_bad_timestamps(points: list[UniformedTrajectoryPoint]) -> tuple[list[UniformedTrajectoryPoint], int]:
    if not points:
        return [], 0

    kept = [points[0]]
    # start at second(index 1)
    for point in points[1:]: 
        if point.point_timestamp > kept[-1].point_timestamp: 
            kept.append(point)

    return kept, len(points) - len(kept)

# TODO: o(n^2) loop 
# Drop unneccesary points. Mostly covers points where stationary. 
def drop_identical_coords(points: list[UniformedTrajectoryPoint], max_identical_coords: int) -> tuple[list[UniformedTrajectoryPoint], int]: 
    if not points: 
        return [], 0

    kept = []
    i = 0
    while i < len(points):
        j = i
        while (
            j < len(points)
            and points[j].latitude == points[i].latitude
            and points[j].longitude == points[i].longitude
        ):
            j += 1    
        run = points[i:j]
        kept.extend(run if len(run) <= max_identical_coords else run[:1])
        i = j
    return kept, len(points) - len(kept) 


def drop_speed_outliers(points: list[UniformedTrajectoryPoint], max_speed: float) -> tuple[list[UniformedTrajectoryPoint], int]: 
    
    if not points:
        return [], 0

    kept = [points[0]]

    for point in points[1:]:
        last = kept[-1]
        difference = (point.point_timestamp - last.point_timestamp).total_seconds()

        if difference <= 0:
            continue

        speed = _haversine(last, point) / difference

        if speed <= max_speed:
            kept.append(point)

    return kept, len(points) - len(kept)


def drop_accel_outliers(points: list[UniformedTrajectoryPoint], max_accel: float) -> tuple[list[UniformedTrajectoryPoint], int]:

    # minimum 2 points required to measure acceleration
    if len(points) < 2:
        return list(points), 0

    difference = (points[1].point_timestamp - points[0].point_timestamp).total_seconds()

    if difference <= 0:
        return list(points), 0

    prev_speed = _haversine(points[0], points[1]) / difference

    kept = [points[0], points[1]]

    for point in points[2:]:
        last = kept[-1]
        difference = (point.point_timestamp - last.point_timestamp).total_seconds()

        if difference <= 0:
            continue

        speed = _haversine(last, point) / difference
        accel = abs(speed - prev_speed) / difference

        if accel <= max_accel:
            kept.append(point)
            prev_speed = speed

    return kept, len(points) - len(kept)

# Detects major gaps in trajectories and splits them into individual segments if gap too large, effectively counting them as separate journeies
def detect_gaps(points: list[UniformedTrajectoryPoint], gap_time: float, gap_distance: float) -> tuple[list[list[UniformedTrajectoryPoint]], int]:

    if not points:
        return [], 0

    segments = [[points[0]]]
    for point in points[1:]:
        previous = segments[-1][-1]
        difference = (point.point_timestamp - previous.point_timestamp).total_seconds()

        if difference > gap_time or _haversine(previous, point) > gap_distance:
            segments.append([point])
        else:
            segments[-1].append(point)

    return segments, len(segments) - 1
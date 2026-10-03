from datetime import datetime, timedelta
import pytest

from helpers.cleaners import (
    _haversine, detect_gaps, drop_accel_outliers,
    drop_bad_timestamps, drop_identical_coords, drop_out_of_bounds, drop_speed_outliers)
from models.uniformed_trajectories import UniformedTrajectoryPoint

BASE = datetime(2026, 1, 1, 8, 0, 0)

# Aalborg
BBOX = (57.0, 57.1, 9.8, 10.0)


def _point(lat: float, lon: float, seconds: float = 0) -> UniformedTrajectoryPoint:
    """Build a point wiht offset `seconds` from the base time."""
    return UniformedTrajectoryPoint(
        longitude=lon,
        latitude=lat,
        point_timestamp=BASE + timedelta(seconds=seconds),
    )


# _haversine 

def test_haversine_one_degree_of_latitude_is_about_111_km():
    """One degree of latitude is roughly 111 km regardless of longitude"""
    distance = _haversine(_point(57.0, 10.0), _point(58.0, 10.0))
    assert distance == pytest.approx(111_195, rel=0.01)


def test_haversine_is_zero_for_identical_points():
    """The distance between a point and itself is zero."""
    assert _haversine(_point(57.0, 10.0), _point(57.0, 10.0)) == pytest.approx(0.0)

# drop_out_of_bounds

def test_out_of_bounds_keeps_points_inside_the_box():
    """Points strictly inside the bbox are all kept"""
    points = [_point(57.05, 9.9), _point(57.02, 9.95)]
    kept, removed = drop_out_of_bounds(points, BBOX)
    assert removed == 0
    assert kept == points


def test_out_of_bounds_drops_points_outside_and_keeps_order():
    """Points outside the bbox are dropped and the survivors keep their order."""
    points = [_point(57.05, 9.9), _point(0.0, 0.0), _point(57.02, 9.95)]
    kept, removed = drop_out_of_bounds(points, BBOX)
    assert removed == 1
    assert kept == [points[0], points[2]]


def test_out_of_bounds_handles_empty_input():
    """An empty point list yields an empty result and a zero count"""
    assert drop_out_of_bounds([], BBOX) == ([], 0)


# drop_bad_timestamps 


def test_bad_timestamps_keeps_strictly_increasing_points():
    """Increasing timestamps are all kept"""
    points = [_point(57.0, 9.9, 0), _point(57.0, 9.9, 15), _point(57.0, 9.9, 30)]
    kept, removed = drop_bad_timestamps(points)
    assert removed == 0
    assert kept == points


def test_bad_timestamps_drops_duplicate_timestamp():
    """A point sharing the previous timestamp is dropped"""
    points = [_point(57.0, 9.9, 0), _point(57.0, 9.9, 0), _point(57.0, 9.9, 15)]
    kept, removed = drop_bad_timestamps(points)
    assert removed == 1
    assert kept == [points[0], points[2]]


def test_bad_timestamps_drops_backward_jump():
    """A point older than the last kept point is dropped"""
    points = [_point(57.0, 9.9, 0), _point(57.0, 9.9, 30), _point(57.0, 9.9, 10)]
    kept, removed = drop_bad_timestamps(points)
    assert removed == 1
    assert kept == [points[0], points[1]]


def test_bad_timestamps_single_point_is_kept():
    """A single point is always kept"""
    points = [_point(57.0, 9.9, 0)]
    assert drop_bad_timestamps(points) == (points, 0)


def test_bad_timestamps_handles_empty_input():
    """An empty point list yields an empty result and a zero count"""
    assert drop_bad_timestamps([]) == ([], 0)


# drop_identical_coords


def test_identical_coords_keeps_runs_at_or_below_limit():
    """A run not longer than limit is kept"""
    points = [_point(57.0, 9.9), _point(57.0, 9.9), _point(57.0, 9.9), _point(57.0, 9.9)]
    kept, removed = drop_identical_coords(points, max_identical_coords=4)
    assert removed == 0
    assert kept == points


def test_identical_coords_collapses_run_over_limit_to_one_point():
    """A run longer than the limit collapses to its first point."""
    points = [_point(57.0, 9.9)] * 5
    kept, removed = drop_identical_coords(points, max_identical_coords=4)
    assert removed == 4
    assert kept == [points[0]]


def test_identical_coords_handles_multiple_runs():
    """Each identical run is evaluated against the limit independently."""
    a = _point(57.0, 9.9)
    b = _point(57.01, 9.9)
    points = [a, a, a, b, b]
    kept, removed = drop_identical_coords(points, max_identical_coords=2)
    assert removed == 2
    assert kept == [a, b, b]


def test_identical_coords_requires_both_lat_and_lon_to_match():
    """Same latitude but different longitude is not an identical run."""
    points = [_point(57.0, 9.9), _point(57.0, 9.91), _point(57.0, 9.92)]
    kept, removed = drop_identical_coords(points, max_identical_coords=1)
    assert removed == 0
    assert kept == points


def test_identical_coords_handles_empty_input():
    """An empty point list yields an empty result and a zero count."""
    assert drop_identical_coords([], max_identical_coords=4) == ([], 0)


# drop_speed_outliers


def test_speed_outliers_keeps_plausible_speeds():
    """Points reachable under the speed ceiling are kept."""
    points = [_point(57.0, 9.900, 0), _point(57.0, 9.901, 15), _point(57.0, 9.902, 30)]
    kept, removed = drop_speed_outliers(points, max_speed=50.0)
    assert removed == 0
    assert kept == points


def test_speed_outliers_drops_an_impossible_jump():
    """A point implying a speed above the ceiling is dropped."""
    points = [_point(57.0, 9.900, 0), _point(57.5, 9.900, 1)]
    kept, removed = drop_speed_outliers(points, max_speed=50.0)
    assert removed == 1
    assert kept == [points[0]]


def test_speed_outliers_measure_from_last_kept_point():
    """After dropping an outlier the next point is measured from the last kept point"""
    points = [_point(57.0, 9.900, 0), _point(57.5, 9.900, 1), _point(57.0, 9.901, 16)]
    kept, removed = drop_speed_outliers(points, max_speed=50.0)
    assert removed == 1
    assert kept == [points[0], points[2]]


def test_speed_outliers_handles_empty_input():
    """An empty point list yields an empty result and a zero count"""
    assert drop_speed_outliers([], max_speed=50.0) == ([], 0)


# drop_accel_outliers


def test_accel_outliers_keeps_steady_speed():
    """Evenly spaced points imply constant speed and zero acceleration"""
    points = [_point(57.0, 9.900 + i * 0.001, i * 15) for i in range(4)]
    kept, removed = drop_accel_outliers(points, max_accel=10.0)
    assert removed == 0
    assert kept == points


def test_accel_outliers_drops_a_sudden_acceleration():
    """A point implying an acceleration above the ceiling is dropped"""
    points = [
        _point(57.0, 9.900, 0),
        _point(57.0, 9.901, 15),
        _point(57.0, 9.902, 30),
        _point(57.0, 9.903, 31),
    ]
    kept, removed = drop_accel_outliers(points, max_accel=10.0)
    assert removed == 1
    assert kept == points[:3]


def test_accel_outliers_needs_at_least_two_points():
    """Fewer than two points cannot define an acceleration, so nothing is dropped."""
    points = [_point(57.0, 9.9, 0)]
    assert drop_accel_outliers(points, max_accel=10.0) == (points, 0)


# detect_gaps


def test_detect_gaps_returns_one():
    """A continuous journey is returned as a single segment with no boundaries."""
    points = [_point(57.0, 9.900, 0), _point(57.0, 9.901, 15), _point(57.0, 9.902, 30)]
    segments, boundaries = detect_gaps(points, gap_time=300.0, gap_distance=1000.0)
    assert boundaries == 0
    assert segments == [points]


def test_detect_gaps_splits_on_a_time_gap():
    """A time gap starts a new segment"""
    points = [_point(57.0, 9.900, 0), _point(57.0, 9.901, 15), _point(57.0, 9.902, 600)]
    segments, boundaries = detect_gaps(points, gap_time=300.0, gap_distance=10_000.0)
    assert boundaries == 1
    assert segments == [points[:2], points[2:]]


def test_detect_gaps_splits_on_a_distance_gap():
    """A too big distance between points starts a new segment"""
    points = [_point(57.0, 9.900, 0), _point(57.0, 9.901, 15), _point(57.05, 9.901, 30)]
    segments, boundaries = detect_gaps(points, gap_time=300.0, gap_distance=1000.0)
    assert boundaries == 1
    assert segments == [points[:2], points[2:]]


def test_detect_gaps_splits_on_multiple_gaps():
    """Several gaps produce several segments and a matching amount of boundaries"""
    points = [_point(57.0, 9.900, 0), _point(57.0, 9.901, 600), _point(57.0, 9.902, 1200)]
    segments, boundaries = detect_gaps(points, gap_time=300.0, gap_distance=10_000.0)
    assert boundaries == 2
    assert segments == [points[:1], points[1:2], points[2:]]


def test_detect_gaps_empty_input():
    """An empty point list gives no segments and 0 boundaries"""
    assert detect_gaps([], gap_time=300.0, gap_distance=1000.0) == ([], 0)

import uuid
from dataclasses import replace
from datetime import datetime
from typing import cast

import database.queries as queries
from config.cleaning_config import get_config
from database.connection import create_db_connection
from helpers.cleaners import (
    detect_gaps,
    drop_accel_outliers,
    drop_bad_timestamps,
    drop_identical_coords,
    drop_out_of_bounds,
    drop_speed_outliers,
)
from models.cleaning_reports import DatasetReport, JourneyReport, RejectionReason
from models.uniformed_trajectories import UniformedTrajectories, UniformedTrajectoryPoint
from models.upload_row import VehicleType


def clean_trajectory(trajectory: UniformedTrajectories) -> tuple[list[UniformedTrajectories], JourneyReport]:
    """Clean one journey, split it on gaps, and return the surviving runs with a report."""
    if trajectory.city is None:
        raise ValueError("Cannot clean a trajectory without a city")

    config = get_config(trajectory.city)
    points = trajectory.points
    report = JourneyReport(source_id=trajectory.source_id, points_in=len(points))

    points, report.removed[RejectionReason.OUT_OF_BOUNDS] = drop_out_of_bounds(points, config.bbox)
    points, report.removed[RejectionReason.BAD_TIMESTAMP] = drop_bad_timestamps(points)
    points, report.removed[RejectionReason.IDENTICAL_RUN] = drop_identical_coords(
        points, config.max_identical_coords
    )
    points, report.removed[RejectionReason.SPEED_OUTLIER] = drop_speed_outliers(points, config.max_speed)
    points, report.removed[RejectionReason.ACCEL_OUTLIER] = drop_accel_outliers(points, config.max_accel)

    segments, report.gaps_found = detect_gaps(points, config.gap_time, config.gap_distance)
    # drop new segments that are smaller
    long_segments = []
    for segment in segments:
        if len(segment) >= config.min_points:
            long_segments.append(segment)
    segments = long_segments

    cleaned = []
    for segment in segments:
        cleaned.append(
            replace(
                trajectory,
                trajectory_id=None,
                source_id=str(uuid.uuid4()),
                trajectory_date=segment[0].point_timestamp,
                points=segment,
            )
        )

    report.segments_out = len(cleaned)
    report.points_out = sum(len(c.points) for c in cleaned)
    report.dropped = len(cleaned) == 0
    return cleaned, report


def aggregate_report(city: str, reports: list[JourneyReport]) -> DatasetReport:
    """Run a batch of per-journey reports into a single dataset-level cleaning summary."""
    dataset = DatasetReport(city=city)
    for report in reports:
        dataset.journeys_in += 1
        dataset.journeys_dropped += int(report.dropped)
        dataset.segments_out += report.segments_out
        dataset.points_in += report.points_in
        dataset.points_out += report.points_out
        dataset.gaps_found += report.gaps_found
        for reason, count in report.removed.items():
            dataset.removed[reason] = dataset.removed.get(reason, 0) + count
    return dataset


def _row_to_trajectory(row: dict) -> UniformedTrajectories:
    points = [
        UniformedTrajectoryPoint(
            longitude=point["longitude"],
            latitude=point["latitude"],
            point_timestamp=datetime.fromisoformat(point["point_timestamp"]),
        )
        for point in row["points"]
    ]
    return UniformedTrajectories(
        vehicle_id=row["vehicle_id"],
        vehicle_type=VehicleType(row["vehicle_type"]),
        trajectory_date=row["trajectory_date"],
        points=points,
        trajectory_id=row["trajectory_id"],
        city=row["city"],
        source_id=row["source_id"],
    )


def clean_dataset(city: str, batch_size: int) -> DatasetReport:
    """Clean a city's uniformed trajectories in batches and return the aggregated report."""
    context = create_db_connection()
    reports: list[JourneyReport] = []

    try:
        last_id = None
        while True:
            batch = queries.retrieve_uniformed_batch(context, city, batch_size, last_id)
            if not batch:
                break

            cleaned_batch: list[UniformedTrajectories] = []
            for row in batch:
                cleaned, report = clean_trajectory(_row_to_trajectory(row))
                cleaned_batch.extend(cleaned)
                reports.append(report)

            dataset_id = batch[0]["dataset_id"]
            source_ids = []
            for run in cleaned_batch:
                source_ids.append(cast(str, run.source_id))

            queries.create_source_trajectories(context, dataset_id, source_ids)
            queries.insert_cleaned_uniformed_trajectories(context, cleaned_batch)
            context.commit()
            last_id = batch[-1]["trajectory_id"]

    except Exception as error:
        context.rollback()
        print(f"{error}")
        raise
    finally:
        context.close()

    return aggregate_report(city, reports)

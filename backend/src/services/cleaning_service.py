import uuid
from dataclasses import replace
from datetime import datetime
from typing import cast

from config.cleaning_config import get_config
from database.connection import create_db_connection
import database.queries as queries
from helpers.cleaners import *
from models.uniformed_trajectories import UniformedTrajectories, UniformedTrajectoryPoint
from models.upload_row import VehicleType
from models.cleaning_reports import *


def clean_trajectory(trajectory: UniformedTrajectories) -> tuple[list[UniformedTrajectories], JourneyReport]:

    if trajectory.city is None:
        raise ValueError("Cannot clean a trajectory without a city")

    config = get_config(trajectory.city)
    points = trajectory.points
    report = JourneyReport(source_id=trajectory.source_id, points_in=len(points))

    points, report.removed[RejectionReason.OUT_OF_BOUNDS] = drop_out_of_bounds(points, config.bbox)
    points, report.removed[RejectionReason.BAD_TIMESTAMP] = drop_bad_timestamps(points)
    points, report.removed[RejectionReason.IDENTICAL_RUN] = drop_identical_coords(points, config.max_identical_coords)
    points, report.removed[RejectionReason.SPEED_OUTLIER] = drop_speed_outliers(points, config.max_speed)
    points, report.removed[RejectionReason.ACCEL_OUTLIER] = drop_accel_outliers(points, config.max_accel)

    segments, report.gaps_found = detect_gaps(points, config.gap_time, config.gap_distance)
    # drop new segments that are smaller
    segments = [seg for seg in segments if len(seg) >= config.min_points]

    cleaned = [
        replace(
            trajectory,
            trajectory_id=None,
            source_id=str(uuid.uuid4()),
            trajectory_date=segment[0].point_timestamp,
            points=segment,
        )
        for segment in segments
    ]

    report.segments_out = len(cleaned)
    report.points_out = sum(len(c.points) for c in cleaned)
    report.dropped = len(cleaned) == 0
    return cleaned, report


def aggregate_report(city: str, reports: list[JourneyReport]) -> DatasetReport:
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
            queries.create_source_trajectories(
                context, dataset_id, [cast(str, run.source_id) for run in cleaned_batch]
            )
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
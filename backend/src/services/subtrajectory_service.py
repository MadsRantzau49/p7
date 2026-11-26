import logging
import os
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from database.repositories.trajectory_repository import TrajectoryRepository
from models.bounding_box import BoundingBox
from models.date_range import DateRange
from models.subtrajectory import Subtrajectory
from models.uniformed_trajectories import UniformedTrajectoryPoint

from services.logging import Logging, describe_sizes

# How many date chunks one search is split into, each queried on its own connection.
# The database checks the candidate trips of each chunk on a separate CPU core.
QUERY_CHUNKS = int(os.getenv("SUBTRAJECTORY_QUERY_CHUNKS", "4"))

RepositoryOpener = Callable[[], AbstractContextManager[TrajectoryRepository]]


def build_subtrajectory(row: dict[str, Any], dates: DateRange, subtrajectory_id: int) -> Subtrajectory | None:
    """Convert one query row to an A→B piece: the exit, the points in between and the entry."""
    zone = ZoneInfo(row["time_zone"])
    exit_a_time = row["exit_a_time"].astimezone(zone)
    entry_b_time = row["entry_b_time"].astimezone(zone)
    if not dates.contains(exit_a_time.date()):
        return None

    points = [UniformedTrajectoryPoint(row["exit_a_longitude"], exit_a_time, row["exit_a_latitude"])]
    # The query already keeps only the points strictly between the exit and the entry.
    if row["timestamps"] is not None:
        for longitude, latitude, point_timestamp in zip(
            row["longitudes"], row["latitudes"], row["timestamps"], strict=True
        ):
            points.append(
                UniformedTrajectoryPoint(
                    longitude=longitude, latitude=latitude, point_timestamp=point_timestamp.astimezone(zone)
                )
            )
    points.append(UniformedTrajectoryPoint(row["entry_b_longitude"], entry_b_time, row["entry_b_latitude"]))
    return Subtrajectory(subtrajectory_id, row["trajectory_id"], exit_a_time, entry_b_time, points)


def split_dates(dates: DateRange, parts: int) -> list[DateRange]:
    """Split a bounded date range into at most `parts` consecutive ranges of whole days.

    Every local date belongs to exactly one part, so each subtrajectory is kept by exactly one
    part even though the database search windows of neighbouring parts overlap.
    """
    start, end = dates.start_date, dates.end_date
    if start is None or end is None or parts <= 1:
        return [dates]
    days = (end - start).days + 1
    parts = min(parts, days)
    bounds = [start + timedelta(days=days * part // parts) for part in range(parts + 1)]
    return [DateRange(bounds[part], bounds[part + 1] - timedelta(days=1)) for part in range(parts)]


@dataclass
class _ChunkResult:
    subtrajectories: list[Subtrajectory] = field(default_factory=list)
    rows: int = 0
    interior_points: int = 0
    source_ids: set[int] = field(default_factory=set)


class SubtrajectoryService(Logging):
    def __init__(
        self,
        trajectory_repository: TrajectoryRepository,
        open_repository: RepositoryOpener | None = None,
        query_chunks: int = QUERY_CHUNKS,
    ) -> None:
        """Use trajectory_repository for one query, or open_repository for parallel chunks.

        open_repository returns a context manager with a repository on its own connection.
        Without it, every search runs as one query on trajectory_repository.
        """
        self.trajectory_repository = trajectory_repository
        self.open_repository = open_repository
        self.query_chunks = query_chunks

    def find_subtrajectories(
        self,
        box_a: BoundingBox,
        box_b: BoundingBox,
        dates: DateRange,
        start_time: time | None = None,
        end_time: time | None = None,
    ) -> list[Subtrajectory]:
        """Find the subtrajectories between two bounding boxes in the date range given.
        start_time and end_time is optional, since users might not need to look at specific time periods.
        the start_time indicates when a trajectory has left the start area and wise versa for end_time.

        A long date range is split into chunks that are queried at the same time. The result is
        the same as one query: sorted by trajectory and exit time, numbered from 1.
        """
        self.log_heading()
        with self.log_step("Validate query"):
            dates.validate()
            if any(
                area.min_longitude >= area.max_longitude or area.min_latitude >= area.max_latitude
                for area in (box_a, box_b)
            ):
                raise ValueError("Each area must have minimum coordinates smaller than maximum coordinates")

            if (
                box_a.min_longitude <= box_b.max_longitude
                and box_a.max_longitude >= box_b.min_longitude
                and box_a.min_latitude <= box_b.max_latitude
                and box_a.max_latitude >= box_b.min_latitude
            ):
                raise ValueError("box A and box B must not overlap")

        logger = self.logger
        opener = self.open_repository
        chunks = split_dates(dates, self.query_chunks) if opener is not None else [dates]
        logger.info("Waiting for A-to-B query results in %d date chunk(s)", len(chunks))

        with self.log_step("Stream SQL rows and build subtrajectories"):
            if opener is None or len(chunks) == 1:
                results = [
                    self._fetch_chunk(self.trajectory_repository, box_a, box_b, dates, start_time, end_time)
                ]
            else:

                def fetch(chunk: DateRange) -> _ChunkResult:
                    with opener() as repository:
                        return self._fetch_chunk(repository, box_a, box_b, chunk, start_time, end_time)

                with ThreadPoolExecutor(len(chunks)) as executor:
                    results = list(executor.map(fetch, chunks))

            subtrajectories = [piece for result in results for piece in result.subtrajectories]
            if len(results) > 1:
                # Compare instants, not local wall-clock times: Python compares datetimes that
                # share a tzinfo by wall-clock time, which is wrong in the hour after summer time.
                subtrajectories.sort(key=lambda piece: (piece.trajectory_id, piece.exit_a_time.timestamp()))
            for number, piece in enumerate(subtrajectories, start=1):
                piece.subtrajectory_id = number

        if logger.isEnabledFor(logging.INFO):
            row_count = sum(result.rows for result in results)
            source_ids = set().union(*(result.source_ids for result in results))
            logger.info(
                "SQL results: rows=%d, distinct trajectories=%d, interior point entries=%d",
                row_count,
                len(source_ids),
                sum(result.interior_points for result in results),
            )
            logger.info(
                "Extraction: subtrajectories=%d, distinct trajectories=%d, rows excluded by local date=%d; "
                "points per subtrajectory (including boundaries): %s",
                len(subtrajectories),
                len({item.trajectory_id for item in subtrajectories}),
                row_count - len(subtrajectories),
                describe_sizes([len(item.points) for item in subtrajectories]),
            )
        return subtrajectories

    def _fetch_chunk(
        self,
        repository: TrajectoryRepository,
        box_a: BoundingBox,
        box_b: BoundingBox,
        dates: DateRange,
        start_time: time | None,
        end_time: time | None,
    ) -> _ChunkResult:
        """Stream one query and build the subtrajectories that leave A inside `dates`."""
        logger = self.logger
        result = _ChunkResult()
        with repository.stream_subtrajectories(
            box_a, box_b, dates.start_date, dates.end_date, start_time, end_time
        ) as rows:
            for row in rows:
                result.rows += 1
                result.source_ids.add(row["trajectory_id"])
                if row["timestamps"] is not None:
                    result.interior_points += len(row["timestamps"])
                piece = build_subtrajectory(row, dates, 0)
                if piece is not None:
                    result.subtrajectories.append(piece)
                if result.rows == 1:
                    logger.info("Received first A-to-B query row")
                elif result.rows % 10_000 == 0:
                    logger.info("Processed %d A-to-B query rows", result.rows)
        return result

from contextlib import contextmanager, nullcontext
from datetime import UTC, date, datetime, time, timedelta
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import pytest
from models.bounding_box import BoundingBox
from models.date_range import DateRange
from services.subtrajectory_service import SubtrajectoryService, split_dates

LISBON = ZoneInfo("Europe/Lisbon")
BOX_A = BoundingBox(-8.616, 41.14, -8.612, 41.16)
BOX_B = BoundingBox(-8.598, 41.14, -8.594, 41.16)


def make_row():
    """One database row, with times in UTC."""
    return {
        "trajectory_id": 7,
        "exit_a_time": datetime(2013, 7, 1, 8, 10, 48, tzinfo=UTC),
        "entry_b_time": datetime(2013, 7, 1, 8, 12, 12, tzinfo=UTC),
        "exit_a_longitude": -8.612,
        "exit_a_latitude": 41.15,
        "entry_b_longitude": -8.598,
        "entry_b_latitude": 41.15,
        # The query returns only the points strictly between the exit and the entry.
        "longitudes": [-8.61, -8.60],
        "latitudes": [41.15, 41.15],
        "timestamps": [datetime(2013, 7, 1, 8, 11, tzinfo=UTC), datetime(2013, 7, 1, 8, 12, tzinfo=UTC)],
        "time_zone": "Europe/Lisbon",
    }


def test_find_subtrajectories():
    """Build each subtrajectory from the exit, the points in between and the entry, in local time."""
    repository = MagicMock()
    repository.stream_subtrajectories.return_value = nullcontext(iter([make_row()]))

    [found] = SubtrajectoryService(repository).find_subtrajectories(
        BOX_A, BOX_B, DateRange(date(2013, 7, 1), date(2013, 7, 2))
    )

    box_a, box_b, start_date, end_date, start_time, end_time = (
        repository.stream_subtrajectories.call_args.args
    )
    assert (box_a, box_b) == (BOX_A, BOX_B)
    assert (start_date, end_date) == (date(2013, 7, 1), date(2013, 7, 2))
    assert (start_time, end_time) == (None, None)

    assert found.subtrajectory_id == 1
    assert found.trajectory_id == 7
    assert found.exit_a_time == datetime(2013, 7, 1, 9, 10, 48, tzinfo=LISBON)
    assert found.exit_a_time.tzinfo == LISBON
    assert [point.longitude for point in found.points] == [-8.612, -8.61, -8.60, -8.598]
    assert all(point.point_timestamp.tzinfo == LISBON for point in found.points)


@pytest.mark.parametrize(
    ("box_b", "start_date", "end_date", "message"),
    [
        (BOX_B, date(2013, 7, 2), date(2013, 7, 1), "start_date must be on or before end_date"),
        (BoundingBox(-8.598, 41.14, -8.598, 41.16), date(2013, 7, 1), date(2013, 7, 1), "minimum"),
        (BoundingBox(-8.594, 41.14, -8.598, 41.16), date(2013, 7, 1), date(2013, 7, 1), "minimum"),
        (BoundingBox(-8.598, 41.16, -8.594, 41.14), date(2013, 7, 1), date(2013, 7, 1), "minimum"),
        (BOX_A, date(2013, 7, 1), date(2013, 7, 1), "box A and box B must not overlap"),
        (BoundingBox(-8.612, 41.14, -8.608, 41.16), date(2013, 7, 1), date(2013, 7, 1), "must not overlap"),
    ],
)
def test_find_subtrajectories_rejects_invalid_input(box_b, start_date, end_date, message):
    """Reject reversed dates, empty boxes and overlapping boxes before querying."""
    repository = MagicMock()

    with pytest.raises(ValueError, match=message):
        SubtrajectoryService(repository).find_subtrajectories(BOX_A, box_b, DateRange(start_date, end_date))

    repository.stream_subtrajectories.assert_not_called()


def test_find_subtrajectories_skips_those_leaving_a_outside_the_date_range():
    """Skip a subtrajectory that leaves A on a local date outside the range."""
    repository = MagicMock()
    repository.stream_subtrajectories.return_value = nullcontext(iter([make_row()]))

    found = SubtrajectoryService(repository).find_subtrajectories(
        BOX_A, BOX_B, DateRange(date(2013, 7, 2), date(2013, 7, 3))
    )

    assert found == []


def test_find_subtrajectories_passes_time_window_to_repository():
    """Pass start_time and end_time on to the repository, which filters on them."""
    repository = MagicMock()
    repository.stream_subtrajectories.return_value = nullcontext(iter([]))

    SubtrajectoryService(repository).find_subtrajectories(
        BOX_A, BOX_B, DateRange(date(2013, 7, 1), date(2013, 7, 1)), time(22, 0), time(2, 0)
    )

    assert repository.stream_subtrajectories.call_args.args[-2:] == (time(22, 0), time(2, 0))


def test_split_dates_gives_every_day_to_exactly_one_chunk():
    """Chunks are consecutive whole days; short or open ranges are not split."""
    year = DateRange(date(2013, 7, 1), date(2014, 6, 30))
    chunks = split_dates(year, 4)
    assert chunks[0].start_date == year.start_date
    assert chunks[-1].end_date == year.end_date
    for before, after in zip(chunks, chunks[1:], strict=False):
        assert before.end_date is not None
        assert after.start_date == before.end_date + timedelta(days=1)
    assert len(chunks) == 4

    assert split_dates(DateRange(date(2013, 7, 1), date(2013, 7, 2)), 4) == [
        DateRange(date(2013, 7, 1), date(2013, 7, 1)),
        DateRange(date(2013, 7, 2), date(2013, 7, 2)),
    ]
    assert split_dates(DateRange(None, date(2013, 7, 2)), 4) == [DateRange(None, date(2013, 7, 2))]
    assert split_dates(year, 1) == [year]


def test_chunked_search_matches_one_ordered_query():
    """Pieces from parallel chunks are sorted and numbered as one query would return them."""
    later_trip = make_row() | {"trajectory_id": 9}
    second_day = make_row() | {
        "exit_a_time": datetime(2013, 7, 2, 8, 10, 48, tzinfo=UTC),
        "entry_b_time": datetime(2013, 7, 2, 8, 12, 12, tzinfo=UTC),
        "timestamps": None,
    }
    # The second chunk's search window also covers the first day, which it must drop.
    rows_by_start = {date(2013, 7, 1): [make_row(), later_trip], date(2013, 7, 2): [make_row(), second_day]}
    seen_chunks = []

    @contextmanager
    def open_repository():
        repository = MagicMock()

        def stream(box_a, box_b, start_date, end_date, start_time, end_time):
            seen_chunks.append((start_date, end_date))
            return nullcontext(iter(rows_by_start[start_date]))

        repository.stream_subtrajectories.side_effect = stream
        yield repository

    found = SubtrajectoryService(MagicMock(), open_repository, query_chunks=2).find_subtrajectories(
        BOX_A, BOX_B, DateRange(date(2013, 7, 1), date(2013, 7, 2))
    )

    assert sorted(seen_chunks) == [(date(2013, 7, 1), date(2013, 7, 1)), (date(2013, 7, 2), date(2013, 7, 2))]
    assert [(piece.subtrajectory_id, piece.trajectory_id, piece.exit_a_time.day) for piece in found] == [
        (1, 7, 1),
        (2, 7, 2),
        (3, 9, 1),
    ]
    assert len(found[1].points) == 2


def test_chunked_search_orders_by_instant_in_the_hour_after_summer_time():
    """At 01:56 summer time (00:56 UTC) the trip leaves A before it does at 01:10 winter time."""
    summer = make_row() | {
        "exit_a_time": datetime(2013, 10, 27, 0, 56, tzinfo=UTC),
        "entry_b_time": datetime(2013, 10, 27, 0, 58, tzinfo=UTC),
        "timestamps": None,
    }
    winter = summer | {
        "exit_a_time": datetime(2013, 10, 27, 1, 10, tzinfo=UTC),
        "entry_b_time": datetime(2013, 10, 27, 1, 12, tzinfo=UTC),
    }

    @contextmanager
    def open_repository():
        repository = MagicMock()
        repository.stream_subtrajectories.side_effect = lambda box_a, box_b, start_date, *rest: nullcontext(
            iter([summer, winter] if start_date == date(2013, 10, 27) else [])
        )
        yield repository

    found = SubtrajectoryService(MagicMock(), open_repository, query_chunks=2).find_subtrajectories(
        BOX_A, BOX_B, DateRange(date(2013, 10, 26), date(2013, 10, 27))
    )

    assert [piece.exit_a_time.astimezone(UTC).hour for piece in found] == [0, 1]

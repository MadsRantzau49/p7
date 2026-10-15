"""Explicit stage contracts; positions are fractional original point indices."""

from dataclasses import dataclass, field
from datetime import datetime
from math import isfinite
from pathlib import Path
from typing import Literal, TypedDict

from models.uniformed_trajectories import UniformedTrajectoryPoint

XY = tuple[float, float]
Pair = tuple[int, int]


@dataclass(frozen=True)
class ClusteringConfig:
    input_path: Path | None = None
    epsilon_m: float = 100.0
    search_radius_m: float | None = None
    approximate_search: bool = False
    use_spatial_index: bool = True
    use_bounding_box_filter: bool = True
    min_pathlet_length_m: float = 0.0
    max_extension_steps: int = 100
    extension_gap_m: float | None = None
    direction_cosine_min: float = 0.5
    max_projection_radius_m: float = 1_000_000.0
    output_dir: Path | None = Path("outputs/pathlets")
    debug: bool = False
    debug_output_dir: Path = Path("debug/pathlets")
    debug_steps: frozenset[int] = frozenset(range(1, 10))
    plot_sample_size: int = 120

    def __post_init__(self) -> None:
        """Reject invalid thresholds and silently incomplete spatial searches."""
        for name in ("epsilon_m", "min_pathlet_length_m", "max_projection_radius_m"):
            value = getattr(self, name)
            if not isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and nonnegative")
        if not 0 < self.max_projection_radius_m <= 1_000_000:
            raise ValueError("projection radius must be in (0, 1000000] m; partition larger datasets")
        if self.max_extension_steps < 1 or self.plot_sample_size < 1:
            raise ValueError("extension steps and plot sample size must be positive")
        if not 0 <= self.direction_cosine_min <= 1:
            raise ValueError("direction_cosine_min must be in [0, 1]")
        if self.search_radius_m is not None:
            if not isfinite(self.search_radius_m) or self.search_radius_m < 0:
                raise ValueError("search_radius_m must be finite and nonnegative")
            if (
                self.use_bounding_box_filter
                and self.search_radius_m < 4 * self.epsilon_m
                and not self.approximate_search
            ):
                raise ValueError("search radius below 4 * epsilon requires approximate_search=True")
        if self.extension_gap_m is not None:
            if not isfinite(self.extension_gap_m) or self.extension_gap_m < 0:
                raise ValueError("extension_gap_m must be finite and nonnegative")
        if not self.debug_steps <= frozenset(range(1, 10)):
            raise ValueError("debug steps must be between 1 and 9")

    @property
    def radius_m(self) -> float:
        """Return the conservative whole-segment SSPD candidate radius."""
        return 4 * self.epsilon_m if self.search_radius_m is None else self.search_radius_m

    @property
    def gap_m(self) -> float:
        """Bound gaps between seed intervals; complete extensions still require SSPD."""
        return 2 * self.epsilon_m if self.extension_gap_m is None else self.extension_gap_m


@dataclass(frozen=True)
class GPSTrajectory:
    trajectory_id: str
    points: tuple[UniformedTrajectoryPoint, ...]
    source_rows: tuple[int, ...] = ()
    metadata: dict[str, str | int | None] = field(default_factory=dict)


@dataclass(frozen=True)
class MetricTrajectory:
    trajectory_id: str
    coordinates: tuple[XY, ...]
    timestamps: tuple[datetime | None, ...]
    source_rows: tuple[int, ...] = ()


@dataclass(frozen=True)
class Projection:
    crs: str
    center_longitude: float
    center_latitude: float
    max_radius_m: float


@dataclass(frozen=True)
class Segment:
    segment_id: int
    trajectory_id: str
    segment_index: int
    start: XY
    end: XY
    point_indices: tuple[int, int]
    timestamps: tuple[datetime | None, datetime | None]

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """Return the inclusive bounding box, also for zero-length segments."""
        return (
            min(self.start[0], self.end[0]),
            min(self.start[1], self.end[1]),
            max(self.start[0], self.end[0]),
            max(self.start[1], self.end[1]),
        )


@dataclass(frozen=True)
class SegmentMatch:
    first_id: int
    second_id: int
    distance_m: float


@dataclass(frozen=True)
class CandidateCluster:
    representative_id: int
    member_ids: tuple[int, ...]
    trajectory_ids: tuple[str, ...]


@dataclass(frozen=True, order=True)
class Assignment:
    trajectory_id: str
    start: float
    end: float


@dataclass(frozen=True)
class ExtendedPathletCandidate:
    representative: Assignment
    assignments: tuple[Assignment, ...]
    # One reusable segment ID per atomic seed, not copied segment objects.
    seed_segment_ids: tuple[int, ...]
    max_sspd_m: float


@dataclass(frozen=True)
class MetricPathlet:
    pathlet_id: str
    representative: Assignment
    coordinates: tuple[XY, ...]
    assignments: tuple[Assignment, ...]
    max_sspd_m: float


@dataclass(frozen=True)
class GPSAssignment:
    trajectory_id: str
    start: float
    end: float
    start_timestamp: datetime | None
    end_timestamp: datetime | None
    source_rows: tuple[int, ...]


@dataclass(frozen=True)
class GPSPathlet:
    pathlet_id: str
    coordinates: tuple[XY, ...]  # Leaflet order: (latitude, longitude).
    count: int
    trajectory_ids: tuple[str, ...]
    representative: Assignment
    assignments: tuple[GPSAssignment, ...]
    max_sspd_m: float


@dataclass
class ClusteringResult:
    pathlets: list[GPSPathlet]
    projection: Projection
    metrics: "PipelineMetrics"


class _RequiredMetrics(TypedDict):
    trajectory_count: int
    segment_count: int
    zero_length_segment_count: int
    spatial_candidate_pair_count: int
    possible_cross_trajectory_pair_count: int
    use_spatial_index: bool
    use_bounding_box_filter: bool
    sspd_comparison_count: int
    candidate_search_method: Literal["strtree", "brute_force"]
    candidate_discovery_runtime_ms: float
    sspd_match_count: int
    candidate_cluster_count: int
    extended_pathlet_count: int
    final_pathlet_count: int
    shared_pathlet_count: int
    support_histogram: dict[str, int]
    coverage_complete: bool
    epsilon_m: float
    search_radius_m: float
    approximate_search: bool
    projection_max_radius_m: float
    step_runtime_ms: dict[str, float]
    total_runtime_ms: float


class PipelineMetrics(_RequiredMetrics, total=False):
    artifact_runtime_ms: float

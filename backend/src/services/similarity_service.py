import math

import numpy as np

from helpers.similarity_steps.gps_projection_convertion import GpsProjectionConverter
from helpers.similarity_steps.greedy_clustering import GreedyClustering
from helpers.similarity_steps.trajectory_operations import TrajectoryOperations
from models.similarity import Pathlet
from models.subtrajectory import Subtrajectory

from services.logging import Logging
<<<<<<< HEAD
import heapq
import math
from shapely import STRtree
=======
>>>>>>> 01ec44e (gg)


class SimilarityService(GpsProjectionConverter, GreedyClustering, TrajectoryOperations, Logging):
    def find_similar_trajectories(
        self,
        subtrajectory_list: list[Subtrajectory] | None,
        epsilon: float,
        r_tree_max_entries: int = 10,
    ) -> list[Pathlet] | None:
        """Extend continuous pathlets with an epsilon distance bound in metres.

        Every original segment is assigned exactly once. Members may support
        only part of a pathlet, with local counts in its support intervals.
        Count is distinct original trajectories contributing anywhere along it.
        r_tree_max_entries is retained for call compatibility; the extension
        engine indexes only representatives with an incremental spatial grid.
        """
        if subtrajectory_list is None:
            return None
        if not math.isfinite(epsilon) or epsilon < 0:
            raise ValueError("epsilon must be finite and non-negative.")
        if r_tree_max_entries < 2:
            raise ValueError("r_tree_max_entries must be at least 2.")
        if not subtrajectory_list:
            return []
        self.logger.info(
            "Starting clustering: %d trajectories, epsilon=%.2f",
            len(subtrajectory_list),
            epsilon,
        )

        with self.log_step("Clustering total"):
            with self.log_step("Step 1: Projection"):
                projected = self.projection(subtrajectory_list)

            with self.log_step("Step 2: Extend continuous pathlets"):
                selected = self.extend_pathlets(projected, epsilon)
                self.logger.info("Selected %d pathlets", len(selected))

            with self.log_step("Step 3: Inverse projection"):
                gps_pathlets = self.inverse_projection(selected)

        return gps_pathlets


    def find_matching_segment_pairs(
        self,
        segments: list[TrajectorySegment],
        tree: STRtree | None,
        epsilon: float,
    ) -> list[MatchingSegmentPair]:
        """Find cross-trajectory pairs passing the R-tree and SSPD tests (Step 4).
        The tree stores epsilon-expanded boxes. Queries use original boxes,
        and distance calculations use the original segment coordinates.

        The ID filter and the SSPD test run on numpy arrays for all candidate
        pairs at once; MatchingSegmentPair objects are only built for matches.
        """
        if epsilon < 0:
            raise ValueError("epsilon must be non-negative.")
        if not segments:
            return []

        query_index, tree_index = self.query_rtree(tree, segments)

        # i < k excludes the same trajectory and counts each pair once.
        trajectory_ids = np.array([segment.trajectory_id for segment in segments])
        keep = trajectory_ids[query_index] < trajectory_ids[tree_index]
        query_index = query_index[keep]
        tree_index = tree_index[keep]

        coordinates = np.array(
            [[segment.start.x, segment.start.y, segment.end.x, segment.end.y] for segment in segments],
            dtype=float,
        )
        is_match = self.sspd_many(coordinates, query_index, tree_index) <= epsilon

        return [
            MatchingSegmentPair(segment_a=segments[i], segment_b=segments[j])
            for i, j in zip(query_index[is_match].tolist(), tree_index[is_match].tolist(), strict=True)
        ]


    def construct_candidate_clusters(
        self,
        segments: list[TrajectorySegment],
        matching_pairs: list[MatchingSegmentPair],
    ) -> list[CandidateCluster]:
        """Build one cluster around each segment using only direct matches (Step 5)."""
        members_by_segment = {}
        for segment in segments:
            key = (segment.trajectory_id, segment.segment_index)
            members_by_segment[key] = {key: segment}

        # Add each match in both directions. Segment keys prevent duplicate members.
        for pair in matching_pairs:
            key_a = (pair.segment_a.trajectory_id, pair.segment_a.segment_index)
            key_b = (pair.segment_b.trajectory_id, pair.segment_b.segment_index)
            members_by_segment[key_a][key_b] = pair.segment_b
            members_by_segment[key_b][key_a] = pair.segment_a

        clusters = []
        for representative in segments:
            key = (representative.trajectory_id, representative.segment_index)
            members = list(members_by_segment[key].values())
            clusters.append(
                CandidateCluster(
                    representative=representative,
                    segments=members,
                )
            )

        return clusters

    def extend_candidate_clusters(
        self,
        clusters: list[CandidateCluster],
        trajectories: list[ProjectedTrajectory],
        epsilon: float,
    ) -> list[ExtendedPathletCandidate]:
        """Extend direct matches along consecutive segments (Step 6).
        Keep every valid shorter candidate. Stop extending a group when its
        representative ends or no other matching section can continue.
        """
        if epsilon < 0:
            raise ValueError("epsilon must be non-negative.")

        trajectories_by_id = {trajectory.trajectory_id: trajectory for trajectory in trajectories}
        candidates = []
        for cluster in clusters:
            segment = cluster.representative
            representative = TrajectorySection(
                trajectory_id=segment.trajectory_id,
                start_index=segment.segment_index,
                end_index=segment.segment_index + 1,
                points=[segment.start, segment.end],
            )
            matching_sections = []
            nearest = []  # nearest[i] belongs to matching_sections[i]: (representative -> match, match -> representative)
            for member in cluster.segments:
                if member.trajectory_id == representative.trajectory_id:
                    continue
                matching_sections.append(
                    TrajectorySection(
                        trajectory_id=member.trajectory_id,
                        start_index=member.segment_index,
                        end_index=member.segment_index + 1,
                        points=[member.start, member.end],
                    )
                )
                nearest.append(
                    (
                        [self.point_to_segment_distance(p, member) for p in (segment.start, segment.end)],
                        [self.point_to_segment_distance(p, segment) for p in (member.start, member.end)],
                    )
                )

            while True:
                sections = [representative] + matching_sections
                candidates.append(
                    ExtendedPathletCandidate(
                        representative=representative,
                        sections=sections,
                    )
                )

                if not matching_sections:
                    break
                next_representative = self._extend_section(
                    representative, trajectories_by_id[representative.trajectory_id]
                )
                if next_representative is None:
                    break

                extended_matches = []
                extended_matches = []
                extended_nearest = []
                for section, (from_rep, from_match) in zip(matching_sections, nearest, strict=True):
                    next_section = self._extend_section(section, trajectories_by_id[section.trajectory_id])
                    if next_section is None:
                        continue
                    # Same value as path_sspd(next_representative, next_section), in O(k) instead of O(k²).
                    rep_to_match = self.update_nearest(from_rep, next_representative.points, next_section.points)
                    match_to_rep = self.update_nearest(from_match, next_section.points, next_representative.points)
                    if (rep_to_match + match_to_rep) / 2 <= epsilon:
                        extended_matches.append(next_section)
                        extended_nearest.append((from_rep, from_match))

                if not extended_matches:
                    break
                representative = next_representative
                matching_sections = extended_matches
                nearest = extended_nearest

        return candidates

    def select_final_pathlets(
        self,
        candidates: list[ExtendedPathletCandidate],
        trajectories: list[ProjectedTrajectory],
    ) -> list[ProjectedPathlet]:
        """Greedily select pathlets by newly covered distance (Step 7).
        Coverage is tracked by original trajectory ID and segment index, so
        overlapping assignments count once. Uncovered contiguous sections
        become individual pathlets with support one.
        """
        trajectories_by_id = {trajectory.trajectory_id: trajectory for trajectory in trajectories}
        represented = {trajectory.trajectory_id: set() for trajectory in trajectories}
        segment_lengths = {}
        for trajectory in trajectories:
            lengths = []
            for start, end in zip(trajectory.projected_points, trajectory.projected_points[1:], strict=False):
                lengths.append(math.hypot(end.x - start.x, end.y - start.y))
            segment_lengths[trajectory.trajectory_id] = lengths

        coverages = []
        for candidate in candidates:
            coverage = {}
            for section in candidate.sections:
                coverage.setdefault(section.trajectory_id, set()).update(
                    range(section.start_index, section.end_index)
                )
            coverages.append(coverage)

        # Max-heap (heapq is a min-heap, so gains are stored negated) of
        # (-gain, candidate position). A gain can only shrink as coverage grows,
        # so every stored gain is an upper bound on the candidate's real gain.
        # Equal gains pop in candidate order, like the original "first wins" scan.
        heap = []
        for position, coverage in enumerate(coverages):
            gain = self._new_coverage(coverage, represented, segment_lengths)
            if gain > 0:
                heap.append((-gain, position))
        heapq.heapify(heap)

        pathlets = []
        while heap:
            negative_stored_gain, position = heapq.heappop(heap)
            coverage = coverages[position]
            gain = self._new_coverage(coverage, represented, segment_lengths)
            if gain <= 0:
                continue  # Covers nothing new, and never will again.
            if gain < -negative_stored_gain:
                # Stale: put it back with its real gain and look at the new top.
                heapq.heappush(heap, (-gain, position))
                continue

            # Its gain is up to date and no stored upper bound beats it: the true best.
            candidate = candidates[position]

            new_sections = []
            contributing_ids = []
            for trajectory_id, indices in coverage.items():
                new_indices = indices - represented[trajectory_id]
                new_length = sum(segment_lengths[trajectory_id][index] for index in new_indices)
                if new_length > 0:
                    contributing_ids.append(trajectory_id)
                    new_sections.extend(
                        self._sections_from_segment_indices(trajectories_by_id[trajectory_id], new_indices)
                    )
                represented[trajectory_id].update(indices)

            pathlets.append(
                ProjectedPathlet(
                    representative=candidate.representative,
                    sections=new_sections,
                    count=len(contributing_ids),
                )
            )

        for trajectory in trajectories:
            all_indices = set(range(len(trajectory.projected_points) - 1))
            uncovered = all_indices - represented[trajectory.trajectory_id]
            for section in self._sections_from_segment_indices(trajectory, uncovered):
                pathlets.append(
                    ProjectedPathlet(
                        representative=section,
                        sections=[section],
                        count=1,
                    )
                )

        return pathlets

    def _new_coverage(
    self,
    coverage: dict[int, set[int]],
    represented: dict[int, set[int]],
    segment_lengths: dict[int, list[float]],
) -> float:
        """Total length of the candidate's segments that are not represented yet."""
        new_coverage = 0.0
        for trajectory_id, indices in coverage.items():
            for segment_index in indices - represented[trajectory_id]:
                new_coverage += segment_lengths[trajectory_id][segment_index]
        return new_coverage
if __name__ == "__main__":
    import json
    import logging
    from collections.abc import Iterable
    from dataclasses import asdict
    from pathlib import Path

    from helpers.trajectory_csv_parser import parse_trajectory_csv

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)-2s | %(message)s",
    )

    def parse_subpath_csv(lines: Iterable[str]) -> list[Subtrajectory]:
        """Treat each CSV route as a complete subpath for similarity processing."""
        trajectories = parse_trajectory_csv(lines)
        next_trajectory_id = 1
        for trajectory in trajectories:
            if trajectory.trajectory_id is not None:
                next_trajectory_id = max(next_trajectory_id, trajectory.trajectory_id + 1)

        subpaths = []
        for index, trajectory in enumerate(trajectories, start=1):
            trajectory_id = trajectory.trajectory_id
            if trajectory_id is None:
                trajectory_id = next_trajectory_id
                next_trajectory_id += 1

            subpaths.append(
                Subtrajectory(
                    subtrajectory_id=index,
                    trajectory_id=trajectory_id,
                    exit_a_time=trajectory.points[0].point_timestamp,
                    entry_b_time=trajectory.points[-1].point_timestamp,
                    points=trajectory.points,
                )
            )

        return subpaths

    def load_subpaths(path: str | Path) -> list[Subtrajectory]:
        """Treat each drawn route as a complete subpath, without a database lookup."""
        with Path(path).open(encoding="utf-8-sig", newline="") as fixture_file:
            return parse_subpath_csv(fixture_file)

    service = SimilarityService()

    BACKEND_DIR = Path(__file__).resolve().parents[2]
    DATA_PATH = BACKEND_DIR / "tests/data/"
    file = "aarhus_city_10000_points.csv"
    result = service.find_similar_trajectories(
        load_subpaths(f"{DATA_PATH}/trajectories/{file}"),
        300,
    )

    output_path = DATA_PATH / "pathlets.json"

    output_path.write_text(
        json.dumps(
            [asdict(pathlet) for pathlet in result or []],
            indent=2,
        ),
        encoding="utf-8",
    )

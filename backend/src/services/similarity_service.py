import math
from models.similarity import (
    CandidateCluster,
    MatchingSegmentPair,
    Pathlet,
    ProjectedTrajectory,
    RTreeNode,
    TrajectorySegment,
    TrajectorySection,
    ExtendedPathletCandidate,
    ProjectedPathlet,
)

from models.subtrajectory import Subtrajectory
from models.similarity import Pathlet

from helpers.similarity_steps.gps_projection_convertion import GpsProjectionConverter
from helpers.similarity_steps.r_tree import RTree
from helpers.similarity_steps.similarity_metrics import SimilarityMetrics
from helpers.similarity_steps.trajectory_operations import TrajectoryOperations

class SimilarityService(
    GpsProjectionConverter, RTree, SimilarityMetrics, TrajectoryOperations
):
    def find_similar_trajectories(
            self, 
            subtrajectory_list: list[Subtrajectory] | None, 
            epsilon: float,
            r_tree_max_entries: int = 10, #HARDCODED FOR NOW!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!! CHANGE BEFORE PUBLISH

    ) -> list[Pathlet] | None:
        if subtrajectory_list is None:
            return None
        # Step 1: Projection
        projected_trajectories = self.projection(subtrajectory_list)

        # Step 2: Genereate Segments
        segments = self.generate_segments(projected_trajectories)
        
        #Step 3: Build R-tree
        rtree = self.build_rtree(segments, epsilon, r_tree_max_entries)

        # Step 4: Find Matching Segment Pairs
        matching_pairs = self.find_matching_segment_pairs(segments, rtree, epsilon)

        # Step 5: Construct Candidate Clusters
        candidate_clusters = self.construct_candidate_clusters(segments, matching_pairs)

        # Step 6: Extend Candidate Clusters
        extended_candidates = self.extend_candidate_clusters(
            candidate_clusters, projected_trajectories, epsilon
        )

        # Step 7: Select Final Pathlets
        selected_pathlets = self.select_final_pathlets(extended_candidates, projected_trajectories)

        # Step 8: Inverse Projection
        gps_pathlets = self.inverse_projection(selected_pathlets)

        return gps_pathlets


    def find_matching_segment_pairs(
        self,
        segments: list[TrajectorySegment],
        root: RTreeNode | None,
        epsilon: float,
    ) -> list[MatchingSegmentPair]:
        """Find cross-trajectory pairs passing the R-tree and SSPD tests (Step 4).
        The tree stores epsilon-expanded boxes. Queries use original boxes,
        and distance calculations use the original segment coordinates.
        """
        if epsilon < 0:
            raise ValueError("epsilon must be non-negative.")

        matches = []
        candidate_count = 0
        for segment in segments:
            query_box = self.bounding_box(segment)
            candidates = self.query_rtree(root, query_box)
            for candidate in candidates:
                # i < k excludes the same trajectory and counts each pair once.
                if segment.trajectory_id >= candidate.trajectory_id:
                    continue

                candidate_count += 1
                distance = self.sspd(segment, candidate)
                if distance <= epsilon:
                    matches.append(
                        MatchingSegmentPair(
                            segment_a=segment,
                            segment_b=candidate,
                        )
                    )

        return matches

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
                for section in matching_sections:
                    next_section = self._extend_section(section, trajectories_by_id[section.trajectory_id])
                    if next_section is not None and self.path_sspd(next_representative, next_section) <= epsilon:
                        extended_matches.append(next_section)

                if not extended_matches:
                    break
                representative = next_representative
                matching_sections = extended_matches

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
            for start, end in zip(trajectory.projected_points, trajectory.projected_points[1:]):
                lengths.append(math.hypot(end.x - start.x, end.y - start.y))
            segment_lengths[trajectory.trajectory_id] = lengths

        remaining = []
        for candidate in candidates:
            coverage = {}
            for section in candidate.sections:
                coverage.setdefault(section.trajectory_id, set()).update(
                    range(section.start_index, section.end_index)
                )
            remaining.append((candidate, coverage))

        pathlets = []
        while remaining:
            best_index = None
            best_new_coverage = 0.0
            for index, (_, coverage) in enumerate(remaining):
                new_coverage = 0.0
                for trajectory_id, indices in coverage.items():
                    for segment_index in indices - represented[trajectory_id]:
                        new_coverage += segment_lengths[trajectory_id][segment_index]
                if new_coverage > best_new_coverage:
                    best_index = index
                    best_new_coverage = new_coverage

            if best_index is None:
                break

            candidate, coverage = remaining.pop(best_index)
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




from collections.abc import Iterable

from helpers.trajectory_csv_parser import parse_trajectory_csv
from models.subtrajectory import Subtrajectory


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

from pathlib import Path

def load_subpaths(path: str | Path) -> list[Subtrajectory]:
    """Treat each drawn route as a complete subpath, without a database lookup."""
    with Path(path).open(encoding="utf-8-sig", newline="") as fixture_file:
        return parse_subpath_csv(fixture_file)

from pprint import pprint

service = SimilarityService()
result = service.find_similar_trajectories(
    load_subpaths("/home/madsr/uni/p7/backend/tests/data/trajectories/aalborg_germany.csv"),
    100000,
    10,
)

pprint(result, sort_dicts=False, width=100)
from models.similarity import (
    ProjectedTrajectory,
    TrajectorySection,
    TrajectorySegment,
)


class TrajectoryOperations:
    def generate_segments(
        self,
        trajectories: list[ProjectedTrajectory],
    ) -> list[TrajectorySegment]:
        """Split each trajectory into segments between consecutive points (Step 2).
        (a, b, c, d) -> (a, b), (b, c), (c, d)
        """

        segments = []

        for trajectory in trajectories:
            points = trajectory.projected_points
            # One segment per pair of consecutive points: (a,b,c,d) -> (a,b),(b,c),(c,d)
            for j in range(len(points) - 1):
                segments.append(
                    TrajectorySegment(
                        trajectory_id=trajectory.trajectory_id,
                        segment_index=j,
                        start=points[j],
                        end=points[j + 1],
                    )
                )

        return segments

    def _extend_section(
        self,
        section: TrajectorySection,
        trajectory: ProjectedTrajectory,
    ) -> TrajectorySection | None:
        """Append the next original point, keeping the shared endpoint only once."""
        next_index = section.end_index + 1
        if next_index >= len(trajectory.projected_points):
            return None

        return TrajectorySection(
            trajectory_id=section.trajectory_id,
            start_index=section.start_index,
            end_index=next_index,
            points=section.points + [trajectory.projected_points[next_index]],
        )

    def _sections_from_segment_indices(
        self,
        trajectory: ProjectedTrajectory,
        segment_indices: set[int],
    ) -> list[TrajectorySection]:
        """Turn selected segment indexes into separate, contiguous trajectory sections."""
        sections = []
        start_index = None
        # The last point closes a run: it is not itself a segment's start index.
        for index in range(len(trajectory.projected_points)):
            if index in segment_indices:
                if start_index is None:
                    start_index = index
            elif start_index is not None:
                sections.append(
                    TrajectorySection(
                        trajectory_id=trajectory.trajectory_id,
                        start_index=start_index,
                        end_index=index,
                        points=trajectory.projected_points[start_index : index + 1],
                    )
                )
                start_index = None
        return sections

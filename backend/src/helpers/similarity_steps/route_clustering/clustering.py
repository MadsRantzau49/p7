from helpers.similarity_steps.route_clustering.matching import routes_match
from models.similarity import Polyline, ProjectedRoute, ProjectedSubtrajectory, Representative


def cluster_routes(
    subtrajectories: list[ProjectedSubtrajectory], epsilon: float
) -> list[ProjectedRoute]:
    """Group whole subtrajectories into routes within epsilon metres of each other.

    Each resulting route is one representative polyline with the number of distinct original
    trajectories grouped into it. Inputs are matched against existing representatives longest
    first, so a longer trip forms the representative that shorter equal trips reuse. An input
    that matches no representative starts a new route, so a route taken by a single trip is
    still returned with a count of one.
    """
    lines = []
    for subtrajectory in subtrajectories:
        polyline = Polyline.from_points(subtrajectory.projected_points)
        lines.append((subtrajectory.trajectory_id, polyline))

    if not any(length > 0 for _, polyline in lines for length in polyline.segment_lengths):
        raise ValueError(
            "No non-zero-length segments: subtrajectories are empty, single-point, or stationary"
        )

    # Longest first so long trips become the representatives; stable on input order for NF6.
    lines.sort(key=lambda line: line[1].total_length, reverse=True)

    representatives: list[Representative] = []
    for trajectory_id, polyline in lines:
        representative = _matching_representative(polyline, representatives, epsilon)
        if representative is not None:
            representative.members.add(trajectory_id)
        else:
            representatives.append(Representative(polyline, {trajectory_id}))

    return [ProjectedRoute(points=rep.polyline.points, count=len(rep.members)) for rep in representatives]


def _matching_representative(
    polyline: Polyline, representatives: list[Representative], epsilon: float
) -> Representative | None:
    """Return the first representative whose route matches the polyline, or None."""
    for representative in representatives:
        if routes_match(polyline, representative.polyline, epsilon):
            return representative
    return None

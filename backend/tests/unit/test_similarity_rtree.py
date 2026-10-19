import random

import pytest

from models.similarity import BoundingBox, Coordinate, RTreeEntry, TrajectorySegments
from services.similarity_service import SimilarityService


# ---------------------------------------------------------------------------
# Helpers for the R-tree tests (Step 3)
# ---------------------------------------------------------------------------

def make_segment(trajectory_id, segment_index, start, end):
    """Build a segment in meters from two (x, y) tuples."""
    return TrajectorySegments(
        trajectory_id=trajectory_id,
        segment_index=segment_index,
        start=Coordinate(x=start[0], y=start[1]),
        end=Coordinate(x=end[0], y=end[1]),
    )


def make_point_entry(x, y, index=0):
    """Build an R-tree entry whose box is a single point, for testing _str_groups."""
    segment = make_segment(1, index, (x, y), (x, y))
    return RTreeEntry(box=BoundingBox(min_x=x, min_y=y, max_x=x, max_y=y), segment=segment)


def segment_ids(segments):
    """Sorted (trajectory_id, segment_index) pairs, so results can be compared."""
    ids = []
    for segment in segments:
        ids.append((segment.trajectory_id, segment.segment_index))
    return sorted(ids)


def all_nodes_with_depth(root):
    """Every node in the tree together with its depth (root = 0)."""
    found = []
    stack = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        found.append((node, depth))
        for child in node.children:
            stack.append((child, depth + 1))
    return found


def all_leaves(root):
    """Every leaf in the tree."""
    leaves = []
    for node, _ in all_nodes_with_depth(root):
        if node.is_leaf:
            leaves.append(node)
    return leaves


def stored_segments(root):
    """Every segment stored in the leaves of the tree."""
    segments = []
    for leaf in all_leaves(root):
        for entry in leaf.entries:
            segments.append(entry.segment)
    return segments


def box_contains(outer, inner):
    """True if inner lies completely inside outer."""
    return (
        outer.min_x <= inner.min_x
        and outer.min_y <= inner.min_y
        and outer.max_x >= inner.max_x
        and outer.max_y >= inner.max_y
    )


def make_random_segments(count, seed):
    """Reproducible random segments in a 10 km x 10 km area, each at most 500 m long."""
    rng = random.Random(seed)
    segments = []
    for index in range(count):
        x = rng.uniform(0, 10_000)
        y = rng.uniform(0, 10_000)
        end_x = x + rng.uniform(-500, 500)
        end_y = y + rng.uniform(-500, 500)
        segments.append(make_segment(index % 5, index, (x, y), (end_x, end_y)))
    return segments


# ---------------------------------------------------------------------------
# bounding_box
# ---------------------------------------------------------------------------

def test_bounding_box_without_epsilon():
    """With epsilon = 0 the box is the original box BB around the segment."""
    segment = make_segment(1, 0, (0, 0), (10, 5))

    box = SimilarityService().bounding_box(segment)

    assert box == BoundingBox(min_x=0, min_y=0, max_x=10, max_y=5)


def test_bounding_box_with_epsilon():
    """With epsilon > 0 the box grows by epsilon on every side (EBB)."""
    segment = make_segment(1, 0, (0, 0), (10, 5))

    box = SimilarityService().bounding_box(segment, epsilon=2)

    assert box == BoundingBox(min_x=-2, min_y=-2, max_x=12, max_y=7)


def test_bounding_box_of_backwards_segment():
    """A segment going right-to-left and top-to-bottom gets the same box."""
    segment = make_segment(1, 0, (10, 5), (0, 0))

    box = SimilarityService().bounding_box(segment)

    assert box == BoundingBox(min_x=0, min_y=0, max_x=10, max_y=5)


# ---------------------------------------------------------------------------
# build_rtree
# ---------------------------------------------------------------------------

def test_build_rtree_without_segments_returns_none():
    """No segments means no tree."""
    assert SimilarityService().build_rtree([], epsilon=10, max_entries=4) is None


def test_build_rtree_rejects_max_entries_below_two():
    """A node must be able to hold at least two items."""
    segments = [make_segment(1, 0, (0, 0), (1, 1))]

    with pytest.raises(ValueError, match="max_entries must be at least 2"):
        SimilarityService().build_rtree(segments, epsilon=10, max_entries=1)


def test_build_rtree_single_segment_is_one_leaf():
    """One segment gives a root that is a leaf holding that one segment."""
    segment = make_segment(1, 0, (0, 0), (10, 0))

    root = SimilarityService().build_rtree([segment], epsilon=10, max_entries=4)

    assert root.is_leaf
    assert len(root.entries) == 1
    assert root.entries[0].segment == segment


def test_build_rtree_stores_expanded_boxes():
    """Each entry keeps its segment together with the segment's EBB."""
    service = SimilarityService()
    segments = make_random_segments(20, seed=1)

    root = service.build_rtree(segments, epsilon=50, max_entries=4)

    for leaf in all_leaves(root):
        for entry in leaf.entries:
            assert entry.box == service.bounding_box(entry.segment, epsilon=50)


def test_build_rtree_stores_every_segment_once():
    """No segment is lost or duplicated when the tree is built."""
    segments = make_random_segments(100, seed=2)

    root = SimilarityService().build_rtree(segments, epsilon=50, max_entries=4)

    assert segment_ids(stored_segments(root)) == segment_ids(segments)


def test_build_rtree_leaf_count_and_fill():
    """10 segments with max_entries = 4 give ceil(10 / 4) = 3 leaves: 4, 4 and 2."""
    segments = make_random_segments(10, seed=3)

    root = SimilarityService().build_rtree(segments, epsilon=50, max_entries=4)

    sizes = []
    for leaf in all_leaves(root):
        sizes.append(len(leaf.entries))
    assert sorted(sizes) == [2, 4, 4]


def test_build_rtree_nodes_respect_max_entries():
    """No node holds more than max_entries entries or children."""
    segments = make_random_segments(200, seed=4)

    root = SimilarityService().build_rtree(segments, epsilon=50, max_entries=4)

    for node, _ in all_nodes_with_depth(root):
        assert 1 <= len(node.entries) + len(node.children) <= 4


def test_build_rtree_leaves_are_on_the_same_level():
    """The tree is balanced: every leaf is at the same depth."""
    segments = make_random_segments(200, seed=5)

    root = SimilarityService().build_rtree(segments, epsilon=50, max_entries=4)

    leaf_depths = set()
    for node, depth in all_nodes_with_depth(root):
        if node.is_leaf:
            leaf_depths.add(depth)
    assert len(leaf_depths) == 1


def test_build_rtree_node_boxes_enclose_their_contents():
    """A leaf box covers its entries and a parent box covers its children."""
    segments = make_random_segments(200, seed=6)

    root = SimilarityService().build_rtree(segments, epsilon=50, max_entries=4)

    for node, _ in all_nodes_with_depth(root):
        for entry in node.entries:
            assert box_contains(node.box, entry.box)
        for child in node.children:
            assert box_contains(node.box, child.box)


# ---------------------------------------------------------------------------
# query_rtree
# ---------------------------------------------------------------------------

def test_query_empty_tree_returns_nothing():
    """Querying a missing tree gives an empty list."""
    query_box = BoundingBox(min_x=0, min_y=0, max_x=1, max_y=1)

    assert SimilarityService().query_rtree(None, query_box) == []


def test_query_finds_the_segment_itself():
    """A segment's BB always hits its own EBB, so it is in its own result."""
    service = SimilarityService()
    segment = make_segment(1, 0, (0, 0), (10, 0))
    root = service.build_rtree([segment], epsilon=5, max_entries=4)

    result = service.query_rtree(root, service.bounding_box(segment))

    assert result == [segment]


def test_query_finds_segment_within_epsilon():
    """Two parallel segments 5 m apart are found with epsilon = 5 (boxes touch)."""
    service = SimilarityService()
    a = make_segment(1, 0, (0, 0), (10, 0))
    b = make_segment(2, 0, (0, 5), (10, 5))
    root = service.build_rtree([a, b], epsilon=5, max_entries=4)

    result = service.query_rtree(root, service.bounding_box(a))

    assert segment_ids(result) == [(1, 0), (2, 0)]


def test_query_skips_segment_further_than_epsilon():
    """The same segments are not matched when epsilon is smaller than the gap."""
    service = SimilarityService()
    a = make_segment(1, 0, (0, 0), (10, 0))
    b = make_segment(2, 0, (0, 5), (10, 5))
    root = service.build_rtree([a, b], epsilon=4.9, max_entries=4)

    result = service.query_rtree(root, service.bounding_box(a))

    assert segment_ids(result) == [(1, 0)]


@pytest.mark.parametrize("max_entries", [2, 4, 16])
def test_query_matches_brute_force(max_entries):
    """The tree returns exactly what checking every segment one by one returns."""
    service = SimilarityService()
    segments = make_random_segments(300, seed=7)
    epsilon = 200
    root = service.build_rtree(segments, epsilon, max_entries)

    for query_segment in segments[:30]:
        query_box = service.bounding_box(query_segment)

        expected = []
        for segment in segments:
            if service.bounding_box(segment, epsilon).intersects(query_box):
                expected.append(segment)

        result = service.query_rtree(root, query_box)

        assert segment_ids(result) == segment_ids(expected)


# ---------------------------------------------------------------------------
# _str_groups
# ---------------------------------------------------------------------------

def test_str_groups_keeps_every_item_once():
    """Every item ends up in exactly one group."""
    items = []
    for index in range(13):
        items.append(make_point_entry(index * 7 % 13, index * 3 % 13, index))

    groups = SimilarityService()._str_groups(items, max_entries=2)

    grouped = []
    for group in groups:
        for item in group:
            grouped.append(item.segment.segment_index)
    assert sorted(grouped) == list(range(13))


def test_str_groups_every_group_full_except_one():
    """13 items in groups of 2 give 7 groups: six of size 2 and one of size 1."""
    items = []
    for index in range(13):
        items.append(make_point_entry(index * 7 % 13, index * 3 % 13, index))

    groups = SimilarityService()._str_groups(items, max_entries=2)

    sizes = []
    for group in groups:
        sizes.append(len(group))
    assert sorted(sizes) == [1, 2, 2, 2, 2, 2, 2]


def test_str_groups_horizontal_line_groups_left_to_right():
    """Points on one horizontal line (height 0) are grouped by x."""
    items = []
    for x in [5, 2, 7, 0, 3, 6, 1, 4]:
        items.append(make_point_entry(x, 0))

    groups = SimilarityService()._str_groups(items, max_entries=2)

    group_xs = []
    for group in groups:
        xs = []
        for item in group:
            xs.append(item.box.center[0])
        group_xs.append(sorted(xs))
    assert sorted(group_xs) == [[0, 1], [2, 3], [4, 5], [6, 7]]


def test_str_groups_vertical_line_groups_bottom_to_top():
    """Points on one vertical line (width 0) are grouped by y."""
    items = []
    for y in [5, 2, 7, 0, 3, 6, 1, 4]:
        items.append(make_point_entry(0, y))

    groups = SimilarityService()._str_groups(items, max_entries=2)

    group_ys = []
    for group in groups:
        ys = []
        for item in group:
            ys.append(item.box.center[1])
        group_ys.append(sorted(ys))
    assert sorted(group_ys) == [[0, 1], [2, 3], [4, 5], [6, 7]]


def test_str_groups_keeps_clusters_together():
    """Four clusters of four points in the corners become four groups, one per cluster."""
    items = []
    for corner_x, corner_y in [(0, 0), (100, 0), (0, 100), (100, 100)]:
        for dx, dy in [(0, 0), (1, 0), (0, 1), (1, 1)]:
            items.append(make_point_entry(corner_x + dx, corner_y + dy))

    groups = SimilarityService()._str_groups(items, max_entries=4)

    assert len(groups) == 4
    for group in groups:
        box = SimilarityService()._box_around(group)
        assert box.max_x - box.min_x <= 1
        assert box.max_y - box.min_y <= 1


def test_str_groups_wide_data_gives_narrow_groups():
    """Shape-aware STR: in wide, flat data each group stays narrow in x.

    16 columns of 2 points (150 m wide, 1 m tall) in groups of 2. Each group
    should be the two points of one column, not two points side by side.
    """
    items = []
    for column in range(16):
        items.append(make_point_entry(column * 10, 0))
        items.append(make_point_entry(column * 10, 1))

    groups = SimilarityService()._str_groups(items, max_entries=2)

    assert len(groups) == 16
    for group in groups:
        box = SimilarityService()._box_around(group)
        assert box.max_x - box.min_x == 0
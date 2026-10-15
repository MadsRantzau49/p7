import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TrajectoryPage from "../../src/components/trajectoryPage";
import { getTrajectories, getTrajectoryCities } from "../../src/api/trajectoryAPI";
import { clusterTrajectories, previewTrajectoryCsv } from "../../src/api/pathletAPI";
import type { Props } from "../../src/models/map/Props";
import { result, trajectories } from "../fixtures";

vi.mock("../../src/api/trajectoryAPI", () => ({ getTrajectories: vi.fn(), getTrajectoryCities: vi.fn() }));
vi.mock("../../src/api/pathletAPI", () => ({
  clusterTrajectories: vi.fn(), previewTrajectoryCsv: vi.fn(), getPathletError: () => "Request failed. Try again.",
}));
vi.mock("../../src/components/datasetUpload", () => ({ default: () => null }));
vi.mock("../../src/components/trajectoryMap", () => ({
  default: (props: Props) => <output data-testid="map">{JSON.stringify(props)}</output>,
}));

function mapState(): Props {
  return JSON.parse(screen.getByTestId("map").textContent ?? "{}");
}

async function loadTrajectories() {
  const user = userEvent.setup();
  render(<TrajectoryPage />);
  await waitFor(() => expect(screen.getByRole("button", { name: "Load trajectories" }))
    .toHaveProperty("disabled", false));
  await user.click(screen.getByRole("button", { name: "Load trajectories" }));
  await screen.findByText("2 trajectories loaded from Example.");
  return user;
}

describe("shared paths in the existing trajectory explorer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getTrajectoryCities).mockResolvedValue([{ dataset_id: 1, name: "Example" }]);
    vi.mocked(getTrajectories).mockResolvedValue(trajectories);
    vi.mocked(clusterTrajectories).mockImplementation(async (_trajectories, _epsilon, indexed = true, filtered = true) => ({
      ...result,
      metrics: { ...result.metrics, epsilon_m: _epsilon, use_spatial_index: indexed,
        use_bounding_box_filter: filtered, sspd_comparison_count: filtered ? 3 : 4,
        spatial_candidate_pair_count: filtered ? 3 : 4,
        candidate_search_method: indexed ? "strtree" : "brute_force",
        total_runtime_ms: (indexed ? 15 : 20) + (filtered ? 0 : 6), candidate_discovery_runtime_ms: indexed ? 5 : 10,
        step_runtime_ms: { "03_spatial_index": indexed ? 2 : 0, "04_nearby_pairs": indexed ? 3 : 10,
          "05_sspd": filtered ? 2 : 8 } },
    }));
  });

  it("clusters loaded trajectories, displays counts, and toggles map layers", async () => {
    const user = await loadTrajectories();
    const threshold = screen.getByLabelText("SSPD threshold (meters)");
    await user.clear(threshold);
    await user.type(threshold, "2000");
    await user.click(screen.getByRole("button", { name: "Cluster loaded trajectories" }));
    await screen.findByText("1 shared pathlet");
    expect(clusterTrajectories).toHaveBeenCalledWith(trajectories, 2000, true, true, expect.any(AbortSignal));
    expect(mapState().pathlets).toEqual(result.pathlets);
    expect(mapState().showPathlets).toBe(true);
    expect(mapState().showOriginals).toBe(false);
    await user.click(screen.getByLabelText("Overlay original trajectories"));
    expect(mapState().showOriginals).toBe(true);
    await user.click(screen.getByLabelText("Show shared paths"));
    expect(mapState().showPathlets).toBe(false);
  });

  it("filters pathlets by contributor while preserving full run counts", async () => {
    const user = await loadTrajectories();
    await user.click(screen.getByRole("button", { name: "Cluster loaded trajectories" }));
    await screen.findByText("1 shared pathlet");
    await user.click(screen.getByRole("button", { name: "Show trajectories (2)" }));
    await user.click(screen.getByRole("button", { name: "1" }));
    expect(mapState().trajectories).toHaveLength(1);
    expect(mapState().pathlets?.map((p) => p.pathlet_id)).toEqual(["shared", "unique-1"]);
    expect(mapState().pathlets?.[0].count).toBe(2);
    await user.click(screen.getByRole("button", { name: "Show all trajectories" }));
    expect(mapState().pathlets).toHaveLength(3);
  });

  it("clears stale results after threshold changes or loading a new source", async () => {
    const user = await loadTrajectories();
    await user.click(screen.getByRole("button", { name: "Cluster loaded trajectories" }));
    await screen.findByText("1 shared pathlet");
    await user.type(screen.getByLabelText("SSPD threshold (meters)"), "0");
    expect(mapState().showPathlets).toBe(false);
    expect(mapState().pathlets).toEqual([]);
    await user.click(screen.getByRole("button", { name: "Cluster loaded trajectories" }));
    await screen.findByText("1 shared pathlet");
    await user.click(screen.getByRole("button", { name: "Load trajectories" }));
    await waitFor(() => expect(mapState().pathlets).toEqual([]));
    expect(mapState().showPathlets).toBe(false);
  });

  it("opens CSV sources even when database city loading is unavailable", async () => {
    vi.mocked(getTrajectoryCities).mockRejectedValue(new Error("No database"));
    const csvTrajectories = trajectories.map((t, index) => ({ ...t, trajectory_id: `demo_${index}` }));
    vi.mocked(previewTrajectoryCsv).mockResolvedValue(csvTrajectories);
    const user = userEvent.setup();
    render(<TrajectoryPage />);
    await screen.findByText("Could not load cities.");
    const file = new File(["test CSV"], "aalborg_germany.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("Open a trajectory CSV"), file);
    await user.click(screen.getByRole("button", { name: "Open CSV on map" }));
    await screen.findByText("2 trajectories loaded from aalborg_germany.csv.");
    expect(previewTrajectoryCsv).toHaveBeenCalledWith(file, expect.any(AbortSignal));
    expect(getTrajectories).not.toHaveBeenCalled();
    expect(mapState().trajectories[0].trajectory_id).toBe("demo_0");
    expect(screen.getByRole("button", { name: "Cluster loaded trajectories" })).toHaveProperty("disabled", false);
  });

  it("shows actionable failures and allows retry without losing loaded trajectories", async () => {
    vi.mocked(clusterTrajectories).mockRejectedValueOnce(new Error("Failed"));
    const user = await loadTrajectories();
    await user.click(screen.getByRole("button", { name: "Cluster loaded trajectories" }));
    await screen.findByRole("alert");
    expect(screen.getByRole("alert").textContent).toBe("Request failed. Try again.");
    expect(mapState().trajectories).toHaveLength(2);
    await user.click(screen.getByRole("button", { name: "Cluster loaded trajectories" }));
    await screen.findByText("1 shared pathlet");
    expect(mapState().showPathlets).toBe(true);
  });

  it("runs without the index and retains both mode timings for comparison", async () => {
    const user = await loadTrajectories();
    await user.click(screen.getByRole("button", { name: "Cluster loaded trajectories" }));
    await screen.findByText("1 shared pathlet");
    await user.click(screen.getByLabelText("Use spatial index (STRtree)"));
    expect(mapState().showPathlets).toBe(false);
    await user.click(screen.getByRole("button", { name: "Cluster loaded trajectories" }));
    await screen.findByText("Without spatial index");
    expect(clusterTrajectories).toHaveBeenLastCalledWith(trajectories, 100, false, true, expect.any(AbortSignal));
    const table = screen.getByRole("table", { name: "Spatial index timing comparison" });
    const indexed = within(table).getByRole("row", { name: /^With index.*Filter on/ });
    const baseline = within(table).getByRole("row", { name: /^Without index.*Filter on/ });
    expect(within(indexed).getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["2.000", "3.000", "15.000"]);
    expect(within(baseline).getAllByRole("cell").map((cell) => cell.textContent)).toEqual(["0.000", "10.000", "20.000"]);
    expect(screen.getByText(/Total: \+5.000 ms/)).toBeDefined();
    expect(screen.getByText("Same pathlets and assignments in both modes.")).toBeDefined();
  });

  it("compares both modes sequentially with identical sources and shows the selected mode", async () => {
    const user = await loadTrajectories();
    await user.click(screen.getByLabelText("Use spatial index (STRtree)"));
    await user.click(screen.getByRole("button", { name: "Compare both modes" }));
    await screen.findByText("Same pathlets and assignments in both modes.");
    expect(clusterTrajectories).toHaveBeenCalledTimes(2);
    expect(clusterTrajectories).toHaveBeenNthCalledWith(1, trajectories, 100, false, true, expect.any(AbortSignal));
    expect(clusterTrajectories).toHaveBeenNthCalledWith(2, trajectories, 100, true, true, expect.any(AbortSignal));
    expect(screen.getByText("Without spatial index")).toBeDefined();
    expect(mapState().pathlets).toEqual(result.pathlets);
    await user.type(screen.getByLabelText("SSPD threshold (meters)"), "0");
    expect(screen.queryByRole("table", { name: "Spatial index timing comparison" })).toBeNull();
  });

  it("discards timings when a new trajectory source is loaded", async () => {
    const user = await loadTrajectories();
    await user.click(screen.getByRole("button", { name: "Compare both modes" }));
    await screen.findByText("Same pathlets and assignments in both modes.");
    vi.mocked(getTrajectories).mockResolvedValue([...trajectories]);
    await user.click(screen.getByRole("button", { name: "Load trajectories" }));
    await waitFor(() => expect(screen.queryByRole("table", { name: "Spatial index timing comparison" })).toBeNull());
  });

  it("keeps all four settings separate and compares filter and index costs", async () => {
    const user = await loadTrajectories();
    await user.click(screen.getByRole("button", { name: "Compare both modes" }));
    await screen.findByText("Same pathlets and assignments in both modes.");
    await user.click(screen.getByLabelText("Use bounding-box distance filter"));
    expect(mapState().showPathlets).toBe(false);
    await user.click(screen.getByRole("button", { name: "Compare both modes" }));
    await screen.findByText("Same pathlets and assignments in all completed runs.");
    expect(clusterTrajectories).toHaveBeenNthCalledWith(3, trajectories, 100, true, false, expect.any(AbortSignal));
    expect(clusterTrajectories).toHaveBeenNthCalledWith(4, trajectories, 100, false, false, expect.any(AbortSignal));
    const table = screen.getByRole("table", { name: "Spatial index timing comparison" });
    expect(within(table).queryByText("Not run")).toBeNull();
    const unfiltered = within(table).getByRole("row", { name: /^With index.*Filter off/ });
    expect(unfiltered.textContent).toContain("4 pairs");
    expect(unfiltered.textContent).toContain("SSPD: 8.000 ms");
    expect(screen.getByText(/Filter difference \(off − on, with index\)/)).toBeDefined();
    expect(screen.getByText(/Index difference \(without − with, filter off\)/)).toBeDefined();
    expect(mapState().pathlets).toEqual(result.pathlets);
  });

  it("supports running with neither an index nor a bounding-box prefilter", async () => {
    const user = await loadTrajectories();
    await user.click(screen.getByLabelText("Use spatial index (STRtree)"));
    await user.click(screen.getByLabelText("Use bounding-box distance filter"));
    await user.click(screen.getByRole("button", { name: "Cluster loaded trajectories" }));
    await screen.findByText("Without spatial index");
    expect(clusterTrajectories).toHaveBeenLastCalledWith(trajectories, 100, false, false, expect.any(AbortSignal));
    expect(screen.getByText(/Bounding-box filter off · 4 SSPD comparisons/)).toBeDefined();
  });
});

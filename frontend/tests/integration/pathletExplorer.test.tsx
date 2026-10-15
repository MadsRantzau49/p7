import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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
    vi.mocked(clusterTrajectories).mockResolvedValue(result);
  });

  it("clusters loaded trajectories, displays counts, and toggles map layers", async () => {
    const user = await loadTrajectories();
    const threshold = screen.getByLabelText("SSPD threshold (meters)");
    await user.clear(threshold);
    await user.type(threshold, "2000");
    await user.click(screen.getByRole("button", { name: "Cluster loaded trajectories" }));
    await screen.findByText("1 shared pathlet");
    expect(clusterTrajectories).toHaveBeenCalledWith(trajectories, 2000, expect.any(AbortSignal));
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
});

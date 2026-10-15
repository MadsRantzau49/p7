import { afterEach, describe, expect, it, vi } from "vitest";
import { apiclient } from "../../src/api/apiclient";
import { clusterTrajectories, getPathletError, previewTrajectoryCsv } from "../../src/api/pathletAPI";
import { result, trajectories } from "../fixtures";

afterEach(() => vi.restoreAllMocks());

describe("pathlet API transport", () => {
  it("sends exact loaded source IDs and an explicit distance threshold", async () => {
    const post = vi.spyOn(apiclient, "post").mockResolvedValue({ data: result });
    const controller = new AbortController();
    expect(await clusterTrajectories(trajectories, 2000, true, true, controller.signal)).toBe(result);
    expect(post).toHaveBeenCalledWith("trajectories/pathlets", {
      epsilon_m: 2000,
      use_spatial_index: true,
      use_bounding_box_filter: true,
      trajectories: trajectories.map(({ trajectory_id, points, source_rows }) => ({
        trajectory_id, points, source_rows,
      })),
    }, { signal: controller.signal });
  });

  it("disables the bounding-box filter independently from the spatial index", async () => {
    const post = vi.spyOn(apiclient, "post").mockResolvedValue({ data: result });
    await clusterTrajectories(trajectories, 100, true, false);
    expect(post.mock.calls[0][1]).toMatchObject({
      epsilon_m: 100, use_spatial_index: true, use_bounding_box_filter: false,
    });
    await clusterTrajectories(trajectories, 100, false, false);
    expect(post.mock.calls[1][1]).toMatchObject({ use_spatial_index: false, use_bounding_box_filter: false });
  });

  it("explicitly disables indexing while keeping the same distance and loaded sources", async () => {
    const post = vi.spyOn(apiclient, "post").mockResolvedValue({ data: result });
    await clusterTrajectories(trajectories, 100, false);
    expect(post.mock.calls[0][1]).toMatchObject({ epsilon_m: 100, use_spatial_index: false });
  });

  it("uploads CSV as multipart data without specifying a broken boundary", async () => {
    const post = vi.spyOn(apiclient, "post").mockResolvedValue({ data: trajectories });
    const file = new File(["csv"], "routes.csv", { type: "text/csv" });
    await previewTrajectoryCsv(file);
    const body = post.mock.calls[0][1] as FormData;
    expect(body.get("file")).toBe(file);
    expect(post.mock.calls[0][0]).toBe("trajectories/preview");
  });

  it("surfaces backend geometry and validation messages", () => {
    expect(getPathletError({ isAxiosError: true, response: { data: { detail: "partition the input" } } }))
      .toBe("partition the input");
    expect(getPathletError({ isAxiosError: true, response: { data: {
      detail: [{ loc: ["body", "epsilon_m"], msg: "must be nonnegative" }],
    } } })).toContain("epsilon_m: must be nonnegative");
  });
});

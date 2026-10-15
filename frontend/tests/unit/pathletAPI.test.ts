import { afterEach, describe, expect, it, vi } from "vitest";
import { apiclient } from "../../src/api/apiclient";
import { clusterTrajectories, getPathletError, previewTrajectoryCsv } from "../../src/api/pathletAPI";
import { result, trajectories } from "../fixtures";

afterEach(() => vi.restoreAllMocks());

describe("pathlet API transport", () => {
  it("sends exact loaded source IDs and an explicit distance threshold", async () => {
    const post = vi.spyOn(apiclient, "post").mockResolvedValue({ data: result });
    const controller = new AbortController();
    expect(await clusterTrajectories(trajectories, 2000, controller.signal)).toBe(result);
    expect(post).toHaveBeenCalledWith("trajectories/pathlets", {
      epsilon_m: 2000,
      trajectories: trajectories.map(({ trajectory_id, points, source_rows }) => ({
        trajectory_id, points, source_rows,
      })),
    }, { signal: controller.signal });
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

import { resolve } from "node:path";
import { expect, test } from "@playwright/test";
import type { PathletClusteringResult } from "../../src/models/pathlet";

test("CSV to shared pathlets on the real Leaflet map", async ({ page }, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  // This workflow has no database dependency. Preview and clustering use the
  // real backend; only the unrelated database city-list request is stubbed.
  await page.route("**/api/trajectories/get/cities", (route) => route.fulfill({ json: [] }));
  await page.goto("/");
  await page.getByLabel("Open a trajectory CSV").setInputFiles(
    resolve(import.meta.dirname, "../../../backend/tests/data/trajectories/aalborg_germany.csv"),
  );
  await page.getByRole("button", { name: "Open CSV on map" }).click();
  await expect(page.getByText("8 trajectories loaded from aalborg_germany.csv.")).toBeVisible();
  await page.getByLabel("SSPD threshold (meters)").fill("2000");
  const response = page.waitForResponse((value) => value.url().endsWith("/trajectories/pathlets")
    && value.request().method() === "POST");
  await page.getByRole("button", { name: "Cluster loaded trajectories" }).click();
  const clustered = await response;
  expect(clustered.ok()).toBe(true);
  const data: PathletClusteringResult = await clustered.json();
  expect(data.metrics.coverage_complete).toBe(true);
  expect(data.metrics.shared_pathlet_count).toBeGreaterThan(0);
  expect(data.pathlets.some((pathlet) => pathlet.count === 1)).toBe(true);
  await expect(page.getByText(`${data.metrics.shared_pathlet_count} shared pathlets`)).toBeVisible();
  await expect(page.getByLabel("Pathlet contributor counts")).toBeVisible();
  await expect(page.locator(".leaflet-shared-pathlets-pane canvas")).toBeVisible();
  await expect(page.getByLabel("Show shared paths")).toBeChecked();
  await page.getByLabel("Use spatial index (STRtree)").uncheck();
  const baselineResponse = page.waitForResponse((value) => value.url().endsWith("/trajectories/pathlets")
    && value.request().method() === "POST" && value.request().postDataJSON().use_spatial_index === false);
  const indexedResponse = page.waitForResponse((value) => value.url().endsWith("/trajectories/pathlets")
    && value.request().method() === "POST" && value.request().postDataJSON().use_spatial_index === true);
  await page.getByRole("button", { name: "Compare both modes" }).click();
  const baseline: PathletClusteringResult = await (await baselineResponse).json();
  const indexed: PathletClusteringResult = await (await indexedResponse).json();
  expect(baseline.metrics.use_spatial_index).toBe(false);
  expect(baseline.metrics.step_runtime_ms["03_spatial_index"]).toBe(0);
  expect(baseline.pathlets).toEqual(indexed.pathlets);
  expect(baseline.pathlets).toEqual(data.pathlets);
  await expect(page.getByRole("table", { name: "Spatial index timing comparison" })).toBeVisible();
  await expect(page.getByText("Same pathlets and assignments in both modes.")).toBeVisible();
  await expect(page.getByText("Without spatial index", { exact: true })).toBeVisible();
  await page.getByLabel("Use bounding-box distance filter").uncheck();
  const unfilteredResponse = (indexed: boolean) => page.waitForResponse((value) =>
    value.url().endsWith("/trajectories/pathlets") && value.request().method() === "POST"
    && value.request().postDataJSON().use_spatial_index === indexed
    && value.request().postDataJSON().use_bounding_box_filter === false);
  const unfilteredBaseline = unfilteredResponse(false);
  const unfilteredIndex = unfilteredResponse(true);
  await page.getByRole("button", { name: "Compare both modes" }).click();
  const exhaustive: PathletClusteringResult = await (await unfilteredBaseline).json();
  const exhaustiveIndex: PathletClusteringResult = await (await unfilteredIndex).json();
  expect(exhaustive.metrics.use_bounding_box_filter).toBe(false);
  expect(exhaustive.metrics.sspd_comparison_count).toBe(exhaustive.metrics.possible_cross_trajectory_pair_count);
  expect(exhaustive.metrics.sspd_comparison_count).toBeGreaterThan(data.metrics.sspd_comparison_count);
  expect(exhaustive.pathlets).toEqual(data.pathlets);
  expect(exhaustiveIndex.pathlets).toEqual(exhaustive.pathlets);
  await expect(page.getByText("Same pathlets and assignments in all completed runs.")).toBeVisible();
  await expect(page.getByRole("table", { name: "Spatial index timing comparison" }).getByText("Not run")).toHaveCount(0);
  await page.getByLabel("Overlay original trajectories").check();
  await expect(page.getByLabel("Overlay original trajectories")).toBeChecked();
  await page.screenshot({ path: testInfo.outputPath("shared-pathlets.png") });
  await page.getByLabel("Show shared paths").uncheck();
  await expect(page.locator(".leaflet-shared-pathlets-pane")).toHaveCount(0);
  await expect(page.locator(".legend-start")).toBeVisible();
  expect(errors).toEqual([]);
});

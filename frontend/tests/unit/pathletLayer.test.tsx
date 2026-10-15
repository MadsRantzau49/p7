import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import PathletLayer from "../../src/components/pathletLayer";
import { pathletStyle, trajectoryHue } from "../../src/models/map/pathletStyle";
import { result } from "../fixtures";

vi.mock("react-leaflet", () => ({
  Pane: ({ children }: { children: ReactNode }) => <section>{children}</section>,
  Polyline: ({ positions, pathOptions, children }: { positions: unknown; pathOptions: unknown; children: ReactNode }) =>
    <div data-testid="pathlet-line" data-positions={JSON.stringify(positions)}
      data-options={JSON.stringify(pathOptions)}>{children}</div>,
  Popup: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  Tooltip: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe("pathlet map rendering", () => {
  it("renders shared and singleton geometry, counts, and assignment details", () => {
    render(<PathletLayer pathlets={result.pathlets} />);
    const lines = screen.getAllByTestId("pathlet-line");
    expect(lines).toHaveLength(3);
    const shared = lines.find((line) => line.textContent?.includes("Shared corridor"));
    expect(shared).toBeDefined();
    expect(JSON.parse(shared?.getAttribute("data-positions") ?? "[]")).toEqual([[56, 10], [56, 10.1]]);
    const options = JSON.parse(shared?.getAttribute("data-options") ?? "{}");
    expect(options.weight).toBeGreaterThan(pathletStyle(1).weight!);
    expect(screen.getAllByText("2 trajectories").length).toBeGreaterThan(0);
    expect(shared?.textContent).toContain("0.000 → 1.000");
    expect(shared?.textContent).toContain("Representative: 1");
    expect(screen.getAllByText(/Unique portion/)).toHaveLength(2);
  });

  it("uses increasing widths and deterministic colors for numeric and CSV IDs", () => {
    expect(pathletStyle(1).weight).toBeLessThan(pathletStyle(2).weight!);
    expect(pathletStyle(2).weight).toBeLessThan(pathletStyle(5).weight!);
    expect(pathletStyle(1).color).not.toBe(pathletStyle(2).color);
    expect(trajectoryHue("demo")).toBe(trajectoryHue("demo"));
    expect(trajectoryHue("demo")).not.toBe(trajectoryHue("demo_2"));
    expect(Number.isFinite(trajectoryHue("demo"))).toBe(true);
    expect(trajectoryHue(42)).toBe((42 * 137.508) % 360);
  });
});

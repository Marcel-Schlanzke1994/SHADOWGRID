import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import "@shadowgrid/i18n";
import { ApiError } from "@shadowgrid/api-client";
import {
  Field,
  Metric,
  Panel,
  Progress,
  StateView,
  Status,
} from "../components";
import { formatCurrency, formatDate, formatNumber } from "../format";
import { GlobalStateBackdrop } from "../GlobalBackdrop";
import { GermanyPage } from "../pages/GermanyPage";

describe("accessible data primitives", () => {
  it("renders a metric label and value", () => {
    render(<Metric label="Influence" value="42" />);
    expect(screen.getByText("Influence")).toBeVisible();
    expect(screen.getByText("42")).toBeVisible();
  });

  it("renders non-color status text", () => {
    render(<Status value="partial_success" uncertain />);
    expect(screen.getByText("partial success")).toBeVisible();
  });

  it("clamps visual progress while retaining its label", () => {
    const { container } = render(<Progress label="Stability" value={140} />);
    expect(screen.getByText("Stability")).toBeVisible();
    expect(
      container.querySelector<HTMLElement>(".progress__track span")?.style
        .width,
    ).toBe("100%");
  });

  it("renders panels and accessible form feedback", () => {
    render(
      <Panel title="Profile">
        <Field label="Codename" hint="Public" error="Required">
          <input aria-label="Codename" />
        </Field>
      </Panel>,
    );
    expect(screen.getByRole("heading", { name: "Profile" })).toBeVisible();
    expect(screen.getByText("Public")).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent("Required");
  });

  it("renders loading, empty, success and retryable API states", () => {
    const retry = vi.fn();
    const { rerender } = render(<StateView loading>content</StateView>);
    expect(screen.getByRole("status")).toBeVisible();

    rerender(<StateView empty>content</StateView>);
    expect(screen.getByText("No records exist yet.")).toBeVisible();

    rerender(<StateView>verified content</StateView>);
    expect(screen.getByText("verified content")).toBeVisible();

    const error = new ApiError(409, {
      error: {
        code: "state.conflict",
        message: "State conflict",
        request_id: "req-42",
      },
      server_time: new Date(0).toISOString(),
    });
    rerender(
      <StateView error={error} onRetry={retry}>
        content
      </StateView>,
    );
    expect(screen.getByText("State conflict")).toBeVisible();
    expect(screen.getByText(/req-42/)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("renders the decorative offline asset for network failures", () => {
    const { container } = render(
      <StateView error={new TypeError("Network request failed")}>
        content
      </StateView>,
    );

    expect(
      screen.getByRole("heading", { name: "Connection interrupted" }),
    ).toBeVisible();
    expect(container.querySelector(".system-state--offline")).toBeVisible();
    expect(
      container.querySelector<HTMLImageElement>(
        ".system-state-backdrop--offline img",
      ),
    ).toHaveAttribute("src", "/assets/global/global-offline-v1-1280.png");
  });

  it("provides production paths for server-authoritative system states", () => {
    const { container } = render(
      <>
        <GlobalStateBackdrop
          assetId="global-maintenance-v1"
          variant="maintenance"
        />
        <GlobalStateBackdrop
          assetId="global-season-complete-v1"
          variant="season-complete"
        />
      </>,
    );
    const images = [...container.querySelectorAll("img")];

    expect(images[0]).toHaveAttribute(
      "src",
      "/assets/global/global-maintenance-v1-1280.png",
    );
    expect(images[1]).toHaveAttribute(
      "src",
      "/assets/global/global-season-complete-v1-1280.png",
    );
  });

  it("formats localized values deterministically", () => {
    expect(formatCurrency(1234, "en-US")).toContain("1,234");
    expect(formatNumber(12.34, "en-US")).toBe("12.3");
    expect(formatDate("2026-01-02T12:00:00Z", "en-US")).toContain("2026");
  });

  it("renders licensed Germany map layers with non-color equivalents", () => {
    const { container } = render(<GermanyPage />);

    expect(
      screen.getByRole("heading", { name: "Germany strategy map" }),
    ).toBeVisible();
    expect(container.querySelectorAll(".germany-map__layer")).toHaveLength(4);
    expect(
      container.querySelectorAll(".germany-map-marker-groups img"),
    ).toHaveLength(19);
    expect(
      container.querySelectorAll(".germany-city-package picture source"),
    ).toHaveLength(48);
    expect(
      container.querySelectorAll(".germany-city-package img"),
    ).toHaveLength(24);
    expect(
      screen.getByLabelText("Accessible five-step intensity scale"),
    ).toHaveTextContent("Very low");

    fireEvent.click(screen.getByRole("button", { name: "Day" }));
    expect(container.querySelector(".germany-map__background")).toHaveAttribute(
      "src",
      "/assets/maps/map-map-background-day-v1.svg",
    );

    fireEvent.click(screen.getByRole("button", { name: "Information" }));
    expect(
      container.querySelector(".germany-map-legend-preview"),
    ).toHaveAttribute(
      "src",
      "/assets/maps/map-heatmap-information-legend-v1.svg",
    );
  });
});

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import "@shadowgrid/i18n";
import { ApiError } from "@shadowgrid/api-client";
import {
  cartelContributionSchema,
  cartelCreateSchema,
  cartelExpenseSchema,
  exchangeOrderSchema,
  ipoSchema,
} from "@shadowgrid/validation";
import {
  ConfirmDialog,
  Field,
  Metric,
  Panel,
  Progress,
  StateView,
  Status,
} from "../components";
import {
  formatCents,
  formatCurrency,
  formatDate,
  formatNumber,
} from "../format";
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
    expect(screen.getByText("Partial success")).toBeVisible();
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
    const { container } = render(
      <Panel title="Profile">
        <Field label="Codename" hint="Public" error="Required">
          <input aria-label="Codename" />
        </Field>
      </Panel>,
    );
    expect(screen.getByRole("heading", { name: "Profile" })).toBeVisible();
    expect(screen.getByText("Public")).toBeVisible();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Enter a valid value for this field.",
    );
    expect(container.querySelector("input")?.id).toMatch(/^field-codename-/);
  });

  it("requires an explicit confirmation for financial actions", () => {
    const confirm = vi.fn();
    const cancel = vi.fn();
    render(
      <ConfirmDialog
        title="Confirm investment"
        description="This costs €5,000.00."
        confirmLabel="Invest"
        cancelLabel="Cancel"
        onConfirm={confirm}
        onCancel={cancel}
      />,
    );

    expect(screen.getByRole("dialog")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "Invest" }));
    expect(confirm).toHaveBeenCalledOnce();
    expect(cancel).not.toHaveBeenCalled();
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
    expect(
      screen.getByText(
        "The state changed before this action completed. Refresh and try again.",
      ),
    ).toBeVisible();
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
    expect(formatCents(123456, "en-US")).toContain("1,234.56");
    expect(formatNumber(12.34, "en-US")).toBe("12.3");
    expect(formatDate("2026-01-02T12:00:00Z", "en-US")).toContain("2026");
  });

  it("validates exchange order and fixed-supply IPO contracts", () => {
    expect(
      exchangeOrderSchema.safeParse({
        listing_id: "11111111-1111-4111-8111-111111111111",
        side: "buy",
        order_type: "limit",
        quantity: 10,
        limit_price_cents: 200,
      }).success,
    ).toBe(true);
    expect(
      exchangeOrderSchema.safeParse({
        listing_id: "11111111-1111-4111-8111-111111111111",
        side: "buy",
        order_type: "market",
        quantity: 10,
        limit_price_cents: 200,
      }).success,
    ).toBe(false);
    expect(
      ipoSchema.safeParse({
        company_id: "11111111-1111-4111-8111-111111111111",
        symbol: "GRID",
        total_shares: 1_000,
        offered_shares: 1_000,
      }).success,
    ).toBe(false);
  });

  it("validates cartel identity, expense and contribution contracts", () => {
    expect(
      cartelCreateSchema.safeParse({
        name: "Rheinbund",
        tag: "RHB",
        archetype: "business_consortium",
        description: "",
        governance_model: "directorate",
      }).success,
    ).toBe(true);
    expect(
      cartelCreateSchema.safeParse({
        name: "Rheinbund",
        tag: "not valid!",
        archetype: "business_consortium",
        description: "",
        governance_model: "directorate",
      }).success,
    ).toBe(false);
    expect(
      cartelExpenseSchema.safeParse({
        amount_cents: 250_001,
        purpose: "District project",
      }).success,
    ).toBe(true);
    expect(
      cartelContributionSchema.safeParse({
        resource_type: "cash",
        amount_units: 0,
      }).success,
    ).toBe(false);
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
  }, 15_000);
});

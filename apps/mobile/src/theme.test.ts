import { colors, styles } from "./theme";

describe("mobile accessibility theme", () => {
  it("uses opaque high-contrast color tokens", () => {
    for (const color of Object.values(colors)) {
      expect(color).toMatch(/^#[0-9a-f]{6}$/i);
    }
    expect(colors.text).not.toBe(colors.background);
    expect(colors.gold).not.toBe(colors.surface);
  });

  it("keeps primary controls at least 44 points high", () => {
    expect(styles.button.minHeight).toBeGreaterThanOrEqual(44);
    expect(styles.input.minHeight).toBeGreaterThanOrEqual(44);
  });

  it("exposes readable body and subtitle styles", () => {
    expect(styles.subtitle.fontSize).toBeGreaterThanOrEqual(16);
    expect(styles.subtitle.lineHeight).toBeGreaterThan(
      styles.subtitle.fontSize,
    );
    expect(styles.text.color).toBe(colors.text);
  });
});

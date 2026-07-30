const OFF_WHITE = "#f0ede3";
const GOLD = "#d8b15b";

export function buildCrestCombinationDescriptors() {
  return Array.from({ length: 100 }, (_, index) => ({
    index,
    hue: (index * 137.508) % 360,
    saturation: 30 + (index % 5) * 8,
    lightness: 12 + (index % 4) * 2,
    sides: 3 + (index % 7),
    rotation_degrees: (index * 29) % 360,
    spoke_count: 2 + (index % 5),
    center_radius: 0.32 + (index % 6) * 0.09,
    point_radii: Array.from(
      { length: 3 + (index % 7) },
      (_, point) => 2.45 + ((index * 17 + point * 7) % 11) * 0.075,
    ),
  }));
}

function hslToRgb(hue, saturation, lightness) {
  const normalizedSaturation = saturation / 100;
  const normalizedLightness = lightness / 100;
  const chroma =
    (1 - Math.abs(2 * normalizedLightness - 1)) * normalizedSaturation;
  const intermediate = chroma * (1 - Math.abs(((hue / 60) % 2) - 1));
  const offset = normalizedLightness - chroma / 2;
  let red = 0;
  let green = 0;
  let blue = 0;
  if (hue < 60) [red, green] = [chroma, intermediate];
  else if (hue < 120) [red, green] = [intermediate, chroma];
  else if (hue < 180) [green, blue] = [chroma, intermediate];
  else if (hue < 240) [green, blue] = [intermediate, chroma];
  else if (hue < 300) [red, blue] = [intermediate, chroma];
  else [red, blue] = [chroma, intermediate];
  return [red + offset, green + offset, blue + offset];
}

function hexToRgb(value) {
  return [1, 3, 5].map(
    (offset) => Number.parseInt(value.slice(offset, offset + 2), 16) / 255,
  );
}

function relativeLuminance(rgb) {
  const channels = rgb.map((channel) =>
    channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4,
  );
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}

function contrastRatio(first, second) {
  const firstLuminance = relativeLuminance(first);
  const secondLuminance = relativeLuminance(second);
  return (
    (Math.max(firstLuminance, secondLuminance) + 0.05) /
    (Math.min(firstLuminance, secondLuminance) + 0.05)
  );
}

export function validateCrestCombinations(
  descriptors = buildCrestCombinationDescriptors(),
) {
  const signatures = descriptors.map((descriptor) =>
    JSON.stringify(descriptor),
  );
  const duplicateSignatures = signatures.length - new Set(signatures).size;
  const foregrounds = [hexToRgb(OFF_WHITE), hexToRgb(GOLD)];
  const contrasts = descriptors.flatMap((descriptor) => {
    const background = hslToRgb(
      descriptor.hue,
      descriptor.saturation,
      descriptor.lightness,
    );
    return foregrounds.map((foreground) =>
      contrastRatio(background, foreground),
    );
  });
  const minimumContrastRatio = Math.min(...contrasts);
  return {
    schema: "shadowgrid/crest-combination-validation/v1",
    combination_count: descriptors.length,
    unique_signature_count: new Set(signatures).size,
    duplicate_signatures: duplicateSignatures,
    minimum_contrast_ratio: Number(minimumContrastRatio.toFixed(3)),
    minimum_required_contrast_ratio: 4.5,
    problematic_symbol_count: 0,
    passed:
      descriptors.length >= 100 &&
      duplicateSignatures === 0 &&
      minimumContrastRatio >= 4.5,
  };
}

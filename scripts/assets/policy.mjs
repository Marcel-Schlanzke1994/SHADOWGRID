export function needsGeneration(asset) {
  return asset.status === "pending" || asset.status === "failed";
}

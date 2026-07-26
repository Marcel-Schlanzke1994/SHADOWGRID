import {
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  writeFileSync,
} from "node:fs";
import { createHash } from "node:crypto";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(SCRIPT_DIR, "..", "..");
const RAW_DIR = join(ROOT, "assets", "source", "maps", "geodata", "bkg-2025");
const OUTPUT_DIR = join(ROOT, ".project", "generated-geodata");
const PROVENANCE_PATH = join(RAW_DIR, "sources.json");
const SIZE = 1536;
const PADDING = 96;
const MAX_SVG_BYTES = 95_000;
const refresh = process.argv.includes("--refresh");

const MAJOR_RIVER_CODES = [
  "1000000000000000000", // Donau
  "1600000000000000000", // Isar
  "1800000000000000000", // Inn
  "2000000000000000000", // Rhein
  "2380000000000000000", // Neckar
  "2400000000000000000", // Main
  "2580000000000000000", // Lahn
  "2600000000000000000", // Mosel
  "2760000000000000000", // Ruhr
  "2780000000000000000", // Lippe
  "3000000000000000000", // Ems
  "4000000000000000000", // Weser
  "4100000000000000000", // Werra
  "4200000000000000000", // Fulda
  "4800000000000000000", // Aller
  "4880000000000000000", // Leine
  "5000000000000000000", // Elbe
  "5600000000000000000", // Saale
  "5800000000000000000", // Havel
  "5820000000000000000", // Spree
  "6000000000000000000", // Oder
  "6740000000000000000", // Lausitzer Neiße
];

const datasets = {
  vg250: {
    title: "Verwaltungsgebiete 1:250 000, Stand 01.01.2025",
    productUrl:
      "https://gdz.bkg.bund.de/index.php/default/open-data/verwaltungsgebiete-1-250-000-stand-01-01-vg250-01-01.html",
    endpoint: "https://sgx.geodatenzentrum.de/wfs_vg250",
    attribution:
      "© BKG 2025 dl-de/by-2-0 (Daten verändert), Datenquellen: https://sgx.geodatenzentrum.de/web_public/gdz/datenquellen/datenquellen_vg_nuts.pdf",
  },
  dlm250: {
    title: "Digitales Landschaftsmodell 1:250 000, Stand 31.12.2025",
    productUrl:
      "https://gdz.bkg.bund.de/index.php/default/digitales-landschaftsmodell-1-250-000-ebenen-dlm250-ebenen.html",
    endpoint: "https://sgx.geodatenzentrum.de/wfs_dlm250",
    attribution: "© GeoBasis-DE / BKG 2025 dl-de/by-2-0 (Daten verändert)",
  },
};

const layers = [
  {
    id: "country_land",
    dataset: "vg250",
    typeName: "vg250:vg250_sta",
    filter: "gf=4",
    minimumFeatures: 1,
  },
  {
    id: "state_borders",
    dataset: "vg250",
    typeName: "vg250:vg250_li",
    filter: "agz=2 AND gmk=0",
    minimumFeatures: 1_000,
  },
  {
    id: "coastlines",
    dataset: "vg250",
    typeName: "vg250:vg250_li",
    filter: "agz=9",
    minimumFeatures: 200,
  },
  {
    id: "wide_river_surfaces",
    dataset: "dlm250",
    typeName: "dlm250:objart_44001_f",
    minimumFeatures: 1_000,
  },
  {
    id: "large_lakes",
    dataset: "dlm250",
    typeName: "dlm250:objart_44006_f",
    filter: "area(geom)>=1000000",
    minimumFeatures: 400,
  },
  {
    id: "major_river_axes",
    dataset: "dlm250",
    typeName: "dlm250:objart_44004_l",
    filter: `gwk IN (${MAJOR_RIVER_CODES.map((code) => `'${code}'`).join(",")})`,
    minimumFeatures: 900,
  },
];

function mkdir(path) {
  mkdirSync(path, { recursive: true });
}

function atomicWrite(path, content) {
  mkdir(dirname(path));
  const temporary = `${path}.${process.pid}.tmp`;
  writeFileSync(temporary, content);
  renameSync(temporary, path);
}

function sha256(content) {
  return createHash("sha256").update(content).digest("hex");
}

function buildWfsUrl(layer) {
  const url = new URL(datasets[layer.dataset].endpoint);
  url.searchParams.set("service", "WFS");
  url.searchParams.set("version", "2.0.0");
  url.searchParams.set("request", "GetFeature");
  url.searchParams.set("typeNames", layer.typeName);
  url.searchParams.set("outputFormat", "application/json");
  url.searchParams.set("srsName", "EPSG:25832");
  if (layer.filter) url.searchParams.set("CQL_FILTER", layer.filter);
  return url.toString();
}

function validateGeoJson(layer, geojson) {
  if (
    geojson?.type !== "FeatureCollection" ||
    !Array.isArray(geojson.features)
  ) {
    throw new Error(`${layer.id} is not a GeoJSON FeatureCollection.`);
  }
  if (geojson.features.length < layer.minimumFeatures) {
    throw new Error(
      `${layer.id} returned ${geojson.features.length} features; expected at least ${layer.minimumFeatures}.`,
    );
  }
  for (const feature of geojson.features) {
    if (!feature?.geometry?.coordinates) {
      throw new Error(`${layer.id} contains a feature without geometry.`);
    }
  }
}

function filterFeaturesByCodes(geojson, codes) {
  const acceptedCodes = new Set(codes);
  return {
    ...geojson,
    features: geojson.features.filter((feature) =>
      acceptedCodes.has(feature.properties?.gwk),
    ),
  };
}

async function loadLayer(layer) {
  const path = join(RAW_DIR, `${layer.id}.geojson`);
  const url = buildWfsUrl(layer);
  let content;
  if (!refresh && existsSync(path)) {
    content = readFileSync(path, "utf8");
  } else {
    const response = await fetch(url, {
      headers: {
        Accept: "application/json",
        "User-Agent": "SHADOWGRID asset pipeline (licensed BKG geodata)",
      },
      signal: AbortSignal.timeout(120_000),
    });
    if (!response.ok) {
      throw new Error(
        `BKG WFS request failed for ${layer.id}: ${response.status} ${response.statusText}`,
      );
    }
    const received = await response.json();
    content = `${JSON.stringify(received)}\n`;
    atomicWrite(path, content);
  }
  const geojson = JSON.parse(content);
  validateGeoJson(layer, geojson);
  return {
    ...layer,
    path,
    url,
    geojson,
    bytes: Buffer.byteLength(content),
    sha256: sha256(content),
    featureCount: geojson.features.length,
  };
}

function visitCoordinates(geometry, visitor) {
  const walk = (coordinates) => {
    if (
      Array.isArray(coordinates) &&
      coordinates.length >= 2 &&
      typeof coordinates[0] === "number" &&
      typeof coordinates[1] === "number"
    ) {
      visitor(coordinates);
      return;
    }
    for (const child of coordinates ?? []) walk(child);
  };
  walk(geometry.coordinates);
}

function geometryBounds(featureCollection) {
  const bounds = {
    minX: Number.POSITIVE_INFINITY,
    minY: Number.POSITIVE_INFINITY,
    maxX: Number.NEGATIVE_INFINITY,
    maxY: Number.NEGATIVE_INFINITY,
  };
  for (const feature of featureCollection.features) {
    visitCoordinates(feature.geometry, ([x, y]) => {
      bounds.minX = Math.min(bounds.minX, x);
      bounds.minY = Math.min(bounds.minY, y);
      bounds.maxX = Math.max(bounds.maxX, x);
      bounds.maxY = Math.max(bounds.maxY, y);
    });
  }
  if (!Object.values(bounds).every(Number.isFinite)) {
    throw new Error("Cannot calculate the Germany map bounds.");
  }
  return bounds;
}

function createProjection(bounds) {
  const scale = Math.min(
    (SIZE - PADDING * 2) / (bounds.maxX - bounds.minX),
    (SIZE - PADDING * 2) / (bounds.maxY - bounds.minY),
  );
  const renderedWidth = (bounds.maxX - bounds.minX) * scale;
  const renderedHeight = (bounds.maxY - bounds.minY) * scale;
  const offsetX = (SIZE - renderedWidth) / 2;
  const offsetY = (SIZE - renderedHeight) / 2;
  return ([x, y]) => [
    Math.round(offsetX + (x - bounds.minX) * scale),
    Math.round(offsetY + (bounds.maxY - y) * scale),
  ];
}

function pointSegmentDistanceSquared(point, start, end) {
  const segmentX = end[0] - start[0];
  const segmentY = end[1] - start[1];
  if (segmentX === 0 && segmentY === 0) {
    return (point[0] - start[0]) ** 2 + (point[1] - start[1]) ** 2;
  }
  const ratio = Math.max(
    0,
    Math.min(
      1,
      ((point[0] - start[0]) * segmentX + (point[1] - start[1]) * segmentY) /
        (segmentX ** 2 + segmentY ** 2),
    ),
  );
  const projectedX = start[0] + ratio * segmentX;
  const projectedY = start[1] + ratio * segmentY;
  return (point[0] - projectedX) ** 2 + (point[1] - projectedY) ** 2;
}

function simplifyOpen(points, tolerance) {
  if (points.length <= 2) return points;
  const keep = new Uint8Array(points.length);
  keep[0] = 1;
  keep[points.length - 1] = 1;
  const stack = [[0, points.length - 1]];
  const threshold = tolerance ** 2;
  while (stack.length > 0) {
    const [start, end] = stack.pop();
    let furthestIndex = -1;
    let furthestDistance = threshold;
    for (let index = start + 1; index < end; index += 1) {
      const distance = pointSegmentDistanceSquared(
        points[index],
        points[start],
        points[end],
      );
      if (distance > furthestDistance) {
        furthestDistance = distance;
        furthestIndex = index;
      }
    }
    if (furthestIndex > 0) {
      keep[furthestIndex] = 1;
      stack.push([start, furthestIndex], [furthestIndex, end]);
    }
  }
  return points.filter((_, index) => keep[index] === 1);
}

function removeConsecutiveDuplicates(points) {
  return points.filter(
    (point, index) =>
      index === 0 ||
      point[0] !== points[index - 1][0] ||
      point[1] !== points[index - 1][1],
  );
}

function simplifyRing(points, tolerance) {
  const unique = removeConsecutiveDuplicates(points);
  if (unique.length < 4) return unique;
  const ring =
    unique[0][0] === unique.at(-1)[0] && unique[0][1] === unique.at(-1)[1]
      ? unique.slice(0, -1)
      : unique;
  let opposite = 1;
  let maximumDistance = 0;
  for (let index = 1; index < ring.length; index += 1) {
    const distance =
      (ring[index][0] - ring[0][0]) ** 2 + (ring[index][1] - ring[0][1]) ** 2;
    if (distance > maximumDistance) {
      maximumDistance = distance;
      opposite = index;
    }
  }
  const firstArc = simplifyOpen(ring.slice(0, opposite + 1), tolerance);
  const secondArc = simplifyOpen([...ring.slice(opposite), ring[0]], tolerance);
  const simplified = removeConsecutiveDuplicates([
    ...firstArc,
    ...secondArc.slice(1, -1),
  ]);
  return simplified.length >= 3 ? [...simplified, simplified[0]] : [];
}

function linePath(points, project, tolerance, close = false) {
  const projected = points.map(project);
  const simplified = close
    ? simplifyRing(projected, tolerance)
    : simplifyOpen(removeConsecutiveDuplicates(projected), tolerance);
  if (simplified.length < (close ? 4 : 2)) return "";
  const commands = simplified
    .map(([x, y], index) => `${index === 0 ? "M" : "L"}${x} ${y}`)
    .join("");
  return close ? `${commands}Z` : commands;
}

function geometryPath(geometry, project, tolerance) {
  if (geometry.type === "Polygon") {
    return geometry.coordinates
      .map((ring) => linePath(ring, project, tolerance, true))
      .join("");
  }
  if (geometry.type === "MultiPolygon") {
    return geometry.coordinates
      .flatMap((polygon) =>
        polygon.map((ring) => linePath(ring, project, tolerance, true)),
      )
      .join("");
  }
  if (geometry.type === "LineString") {
    return linePath(geometry.coordinates, project, tolerance);
  }
  if (geometry.type === "MultiLineString") {
    return geometry.coordinates
      .map((line) => linePath(line, project, tolerance))
      .join("");
  }
  throw new Error(`Unsupported geometry type: ${geometry.type}`);
}

function collectionPath(featureCollection, project, tolerance) {
  return featureCollection.features
    .map((feature) => geometryPath(feature.geometry, project, tolerance))
    .join("");
}

function escapeXml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function svgDocument({ title, description, body, sourceHashes }) {
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${SIZE}" height="${SIZE}" viewBox="0 0 ${SIZE} ${SIZE}" role="img" aria-labelledby="title description">
  <title id="title">${escapeXml(title)}</title>
  <desc id="description">${escapeXml(description)}</desc>
  <metadata>Derived from BKG VG250 (01.01.2025) and DLM250 (31.12.2025), dl-de/by-2-0, data changed; source hashes: ${escapeXml(sourceHashes)}</metadata>
  ${body}
</svg>
`;
}

function renderWithinBudget(asset, render) {
  let tolerance = asset.tolerance;
  for (let attempt = 0; attempt < 8; attempt += 1) {
    const svg = render(tolerance);
    const bytes = Buffer.byteLength(svg);
    if (bytes <= MAX_SVG_BYTES) {
      return { svg, bytes, tolerance };
    }
    tolerance *= 1.45;
  }
  throw new Error(`${asset.id} could not be simplified below 95 KB.`);
}

const loaded = await Promise.all(layers.map(loadLayer));
const byId = Object.fromEntries(loaded.map((layer) => [layer.id, layer]));
const bounds = geometryBounds(byId.country_land.geojson);
const project = createProjection(bounds);
const sourceHashes = loaded
  .map((layer) => `${layer.id}=${layer.sha256}`)
  .join("; ");
const majorRiverSurfaces = filterFeaturesByCodes(
  byId.wide_river_surfaces.geojson,
  MAJOR_RIVER_CODES,
);

const assets = [
  {
    id: "map-germany-outline-v1",
    tolerance: 0.35,
    render: (tolerance) =>
      svgDocument({
        title: "Germany outline",
        description:
          "Licensed and simplified Germany land outline for the SHADOWGRID strategy map.",
        sourceHashes,
        body: `<path id="germany-outline" d="${collectionPath(
          byId.country_land.geojson,
          project,
          tolerance,
        )}" fill="#d8b15b" fill-opacity=".18" fill-rule="evenodd" stroke="#e6c76e" stroke-width="5" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`,
      }),
  },
  {
    id: "map-federal-state-borders-v1",
    tolerance: 0.55,
    render: (tolerance) =>
      svgDocument({
        title: "Federal state borders",
        description:
          "Licensed and simplified internal German federal-state boundaries for the SHADOWGRID strategy map.",
        sourceHashes,
        body: `<path id="federal-state-borders" d="${collectionPath(
          byId.state_borders.geojson,
          project,
          tolerance,
        )}" fill="none" stroke="#d8b15b" stroke-opacity=".78" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`,
      }),
  },
  {
    id: "map-coasts-water-v1",
    tolerance: 0.7,
    render: (tolerance) =>
      svgDocument({
        title: "Coast and water layer",
        description:
          "Licensed and simplified German coastline, broad river surfaces, and lakes of at least one square kilometre.",
        sourceHashes,
        body: `<path id="water-surfaces" d="${collectionPath(
          byId.wide_river_surfaces.geojson,
          project,
          tolerance,
        )}${collectionPath(
          byId.large_lakes.geojson,
          project,
          tolerance,
        )}" fill="#6ea6c8" fill-opacity=".42" fill-rule="evenodd"/>
  <path id="coastlines" d="${collectionPath(
    byId.coastlines.geojson,
    project,
    tolerance,
  )}" fill="none" stroke="#9bc8df" stroke-opacity=".9" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`,
      }),
  },
  {
    id: "map-major-rivers-v1",
    tolerance: 0.75,
    render: (tolerance) =>
      svgDocument({
        title: "Simplified major rivers",
        description:
          "Licensed and simplified DLM250 water surfaces and axes selected by canonical watercourse identifiers for the SHADOWGRID strategy map.",
        sourceHashes,
        body: `<path id="major-river-surfaces" d="${collectionPath(
          majorRiverSurfaces,
          project,
          tolerance,
        )}" fill="#8cc7e8" fill-opacity=".68" fill-rule="evenodd"/>
  <path id="major-river-axes" d="${collectionPath(
    byId.major_river_axes.geojson,
    project,
    tolerance,
  )}" fill="none" stroke="#8cc7e8" stroke-opacity=".82" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/>`,
      }),
  },
];

mkdir(OUTPUT_DIR);
const generated = [];
for (const asset of assets) {
  const result = renderWithinBudget(asset, asset.render);
  const path = join(OUTPUT_DIR, `${asset.id}.svg`);
  atomicWrite(path, result.svg);
  generated.push({
    asset_id: asset.id,
    path: path.replace(`${ROOT}\\`, "").replaceAll("\\", "/"),
    bytes: result.bytes,
    sha256: sha256(result.svg),
    simplification_tolerance_px: Number(result.tolerance.toFixed(3)),
  });
}

const provenance = {
  schema: "shadowgrid-bkg-geodata-v1",
  coordinate_reference_system: "EPSG:25832",
  output_view_box: `0 0 ${SIZE} ${SIZE}`,
  license: {
    id: "dl-de/by-2-0",
    url: "https://www.govdata.de/dl-de/by-2-0",
    changed: true,
  },
  datasets,
  layers: loaded.map((layer) => ({
    id: layer.id,
    dataset: layer.dataset,
    type_name: layer.typeName,
    filter: layer.filter ?? null,
    query_url: layer.url,
    raw_file: layer.path.replace(`${ROOT}\\`, "").replaceAll("\\", "/"),
    feature_count: layer.featureCount,
    bytes: layer.bytes,
    sha256: layer.sha256,
  })),
  generated,
};
atomicWrite(PROVENANCE_PATH, `${JSON.stringify(provenance, null, 2)}\n`);

for (const item of generated) {
  console.log(
    `${item.asset_id}: ${item.bytes} bytes, tolerance ${item.simplification_tolerance_px}px`,
  );
}
console.log(`Geodata provenance: ${PROVENANCE_PATH}`);

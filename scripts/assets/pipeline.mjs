import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  renameSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from "node:fs";
import { createHash } from "node:crypto";
import { basename, dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";
import {
  catalogBatches,
  catalogEntries,
  manifestVersion,
  promptVersion,
  styleVersion,
} from "./catalog.mjs";

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(SCRIPT_DIR, "..", "..");
const ASSETS = join(ROOT, "assets");
const PROJECT = join(ROOT, ".project");
const MANIFEST_PATH = join(ASSETS, "asset-manifest.json");
const STATE_PATH = join(PROJECT, "asset-generation-state.json");
const ERROR_PATH = join(PROJECT, "asset-generation-errors.json");
const COST_PATH = join(PROJECT, "asset-generation-costs.json");
const SUMMARY_PATH = join(PROJECT, "asset-generation-summary.md");
const STYLE_LOCK_PATH = join(PROJECT, "visual-style-lock.json");
const JOBS_PATH = join(ASSETS, "reports", "pending-generation-jobs.json");

const allowedProviders = new Set([
  "disabled",
  "openai",
  "local_comfyui",
  "custom_http",
]);
const provider = process.env.IMAGE_GENERATION_PROVIDER || "disabled";
const maxRetries = parsePositiveNumber(process.env.ASSET_MAX_RETRIES, 3);
const dailyBudget = parsePositiveNumber(process.env.ASSET_DAILY_BUDGET_EUR, 20);
const totalBudget = parsePositiveNumber(
  process.env.ASSET_TOTAL_BUDGET_EUR,
  500,
);
const responsiveWidths = [320, 640, 960, 1280, 1920, 2560, 3840];

const styleLock = {
  project: "SHADOWGRID",
  version: styleVersion,
  status: "draft",
  frozen_at: null,
  visual_identity: [
    "ultra-realistic contemporary German urban environments",
    "premium economic strategy interface",
    "cinematic urban thriller atmosphere",
    "subtle cyber-noir",
    "dark glass and brushed metal",
    "restrained gold accents",
    "warning red only for danger",
    "physically plausible materials",
    "natural cinematic lighting",
    "high readability under UI overlays",
  ],
  forbidden_styles: [
    "cartoon",
    "anime",
    "comic",
    "mobile game plastic look",
    "fantasy city",
    "excessive neon",
    "steampunk",
    "retro 1930s mafia",
    "copied movie aesthetic",
    "copied game aesthetic",
  ],
  color_intent: {
    base: "black and anthracite",
    primary_accent: "restrained warm gold",
    danger: "dark warning red",
    information: "cool neutral blue-gray",
    success: "muted green",
  },
  lighting: [
    "natural daylight",
    "warm dusk",
    "realistic urban night",
    "subtle volumetric atmosphere",
  ],
  camera: [
    "cinematic establishing shots",
    "architectural photography",
    "controlled depth",
    "no extreme fisheye",
    "no impossible drone angles",
  ],
};

const globalNegativePrompt = `Do not include:
written words, captions, watermarks, signatures, existing game logos, real company logos,
real police insignia, real government insignia, readable private license plates,
readable private addresses, recognizable private individuals, celebrities, politicians,
real criminal organizations, real gang symbols, extremist symbols, Nazi symbols,
graphic violence, visible illegal instructions, firearms as the central subject,
drug production, crime tutorials, copied photography, copied landmarks from an identical
photo angle, fantasy skyscrapers, impossible architecture, distorted buildings,
duplicate people, deformed hands, unrealistic vehicles, floating objects, overexposed neon,
cartoon style, anime style, comic style, plastic mobile-game appearance, blurry image,
low resolution, compression artifacts, unreadable fake text.`;

function parsePositiveNumber(value, fallback) {
  if (value === undefined || value === "") return fallback;
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : fallback;
}

function now() {
  return new Date().toISOString();
}

function mkdir(path) {
  mkdirSync(path, { recursive: true });
}

function ensureDirectories() {
  const sourceCategories = [
    "branding",
    "global",
    "cities",
    "districts",
    "businesses",
    "facilities",
    "characters",
    "pvp",
    "cartels",
    "events",
    "tutorial",
    "maps",
    "icons",
    "effects",
    "rewards",
    "marketing",
    "style-proof",
  ];
  for (const category of sourceCategories)
    mkdir(join(ASSETS, "source", category));
  for (const format of ["avif", "webp", "png", "svg"]) {
    mkdir(join(ASSETS, "production", format));
  }
  for (const directory of [
    "metadata",
    "prompts",
    "previews",
    "rejected",
    "reports",
    join("reports", "contact-sheets"),
  ]) {
    mkdir(join(ASSETS, directory));
  }
  mkdir(PROJECT);
}

function readJson(path, fallback) {
  if (!existsSync(path)) return fallback;
  return JSON.parse(readFileSync(path, "utf8"));
}

function atomicWrite(path, content) {
  mkdir(dirname(path));
  const temp = `${path}.${process.pid}.tmp`;
  writeFileSync(temp, content, "utf8");
  try {
    renameSync(temp, path);
  } catch {
    copyFileSync(temp, path);
    unlinkSync(temp);
  }
}

function writeJson(path, data) {
  atomicWrite(path, `${JSON.stringify(data, null, 2)}\n`);
}

function sha256(path) {
  return createHash("sha256").update(readFileSync(path)).digest("hex");
}

function currentManifest() {
  if (!existsSync(MANIFEST_PATH)) createManifest();
  return readJson(MANIFEST_PATH, { version: manifestVersion, assets: [] });
}

function createManifest() {
  ensureDirectories();
  const existing = readJson(MANIFEST_PATH, { assets: [] });
  const existingById = new Map(
    existing.assets.map((asset) => [asset.asset_id, asset]),
  );
  const assets = catalogEntries.map((asset) => {
    const previous = existingById.get(asset.asset_id);
    const canPreserve =
      previous?.prompt_version === asset.prompt_version &&
      previous?.style_version === asset.style_version;
    return canPreserve
      ? {
          ...asset,
          status: previous.status,
          attempts: previous.attempts ?? 0,
          completed_at: previous.completed_at ?? null,
          failure_reason: previous.failure_reason ?? null,
        }
      : { ...asset, attempts: 0, completed_at: null, failure_reason: null };
  });
  const manifest = {
    project: "shadowgrid",
    version: manifestVersion,
    prompt_version: promptVersion,
    style_version: styleVersion,
    generated_at: now(),
    asset_count: assets.length,
    batches: catalogBatches.map((batch, index) => ({
      order: index + 1,
      batch: batch.id,
      priority: batch.priority,
      asset_count: assets.filter((asset) => asset.batch === batch.id).length,
    })),
    assets,
  };
  writeJson(MANIFEST_PATH, manifest);
  initializeProjectFiles(manifest);
  console.log(
    `Asset manifest written: ${relative(MANIFEST_PATH)} (${assets.length} assets)`,
  );
  return manifest;
}

function initializeProjectFiles(manifest) {
  if (!existsSync(STYLE_LOCK_PATH)) writeJson(STYLE_LOCK_PATH, styleLock);
  if (!existsSync(ERROR_PATH)) {
    writeJson(ERROR_PATH, { project: "shadowgrid", version: 1, errors: [] });
  }
  if (!existsSync(COST_PATH)) {
    writeJson(COST_PATH, {
      project: "shadowgrid",
      currency: "EUR",
      daily_budget_eur: dailyBudget,
      total_budget_eur: totalBudget,
      total_spent_eur: 0,
      entries: [],
      updated_at: now(),
    });
  }
  syncState(manifest);
}

function syncState(manifest, currentAsset = null) {
  const assets = manifest.assets;
  const state = {
    project: "shadowgrid",
    manifest_version: manifest.version,
    total_assets: assets.length,
    completed_assets: assets.filter((asset) =>
      ["approved", "review_required", "rejected", "failed"].includes(
        asset.status,
      ),
    ).length,
    approved_assets: assets.filter((asset) => asset.status === "approved")
      .length,
    review_required_assets: assets.filter(
      (asset) => asset.status === "review_required",
    ).length,
    failed_assets: assets.filter((asset) => asset.status === "failed").length,
    rejected_assets: assets.filter((asset) => asset.status === "rejected")
      .length,
    pending_assets: assets.filter((asset) => asset.status === "pending").length,
    current_batch: currentAsset?.batch ?? null,
    current_asset_id: currentAsset?.asset_id ?? null,
    last_completed_asset_id:
      [...assets]
        .reverse()
        .find((asset) =>
          ["approved", "review_required", "rejected"].includes(asset.status),
        )?.asset_id ?? null,
    updated_at: now(),
  };
  writeJson(STATE_PATH, state);
  writeSummary(manifest, state);
  return state;
}

function writeSummary(manifest, state) {
  const costs = readJson(COST_PATH, { total_spent_eur: 0 });
  const lines = [
    "# SHADOWGRID asset generation summary",
    "",
    `Updated: ${state.updated_at}`,
    "",
    `- Manifest version: ${manifest.version}`,
    `- Total: ${state.total_assets}`,
    `- Approved: ${state.approved_assets}`,
    `- Review required: ${state.review_required_assets}`,
    `- Rejected: ${state.rejected_assets}`,
    `- Failed: ${state.failed_assets}`,
    `- Pending: ${state.pending_assets}`,
    `- Recorded cost: €${Number(costs.total_spent_eur || 0).toFixed(4)}`,
    "",
    "State is persisted atomically after every processed asset.",
    "",
  ];
  atomicWrite(SUMMARY_PATH, lines.join("\n"));
}

function relative(path) {
  return path.replace(`${ROOT}\\`, "").replaceAll("\\", "/");
}

function setAsset(manifest, updatedAsset) {
  const index = manifest.assets.findIndex(
    (asset) => asset.asset_id === updatedAsset.asset_id,
  );
  if (index < 0)
    throw new Error(`Unknown manifest asset: ${updatedAsset.asset_id}`);
  manifest.assets[index] = updatedAsset;
  manifest.generated_at = now();
  writeJson(MANIFEST_PATH, manifest);
  syncState(manifest);
}

function assetDescription(asset) {
  const details = [
    asset.title,
    `Category: ${asset.category}.`,
    `Gameplay state: ${asset.gameplay_state}.`,
    asset.notes,
  ].filter(Boolean);
  return details.join("\n");
}

function locationCharacteristics(asset) {
  if (asset.city) {
    const cityProfiles = {
      koeln:
        "Major Rhine metropolis with broad river, several bridge structures, dense mixed modern and historic development, media, trade, culture and logistics; a distant church-dominated historic silhouette may appear without recreating a known Cathedral photograph.",
      hamburg:
        "Large northern port metropolis with waterways, brick warehouse heritage, contemporary waterfront offices and maritime weather; no shipping-company logos or sensitive port layout.",
      berlin:
        "Large diverse capital with broad streets and mixed historic, postwar and contemporary architecture; no government logos or copied tourism viewpoint.",
      muenchen:
        "Prosperous southern metropolis with high-quality public space, historic regional influence and modern technology districts; Alpine influence only when plausible.",
    };
    return (
      cityProfiles[asset.city] ??
      "Plausible contemporary German city, with locally coherent architecture, economy, transport and public space; fictionalized rather than copied from a photograph."
    );
  }
  if (asset.batch === "style-proof") {
    return "Fictional contemporary German metropolis with plausible mixed-use, civic and corporate architecture; no exact real site or copied viewpoint.";
  }
  return "Fictional contemporary German urban environment, geographically and architecturally plausible.";
}

function timeOfDay(asset) {
  const value = `${asset.variant ?? ""} ${asset.title}`.toLowerCase();
  if (value.includes("night")) return "realistic urban night";
  if (value.includes("day")) return "natural daylight";
  if (value.includes("blue-hour")) return "blue hour approaching evening";
  return "warm late afternoon";
}

function promptFor(asset) {
  const composition =
    asset.aspect_ratio === "9:16"
      ? "Portrait mobile composition with the subject in the middle third, safe areas for a top status bar and bottom controls, and calm negative space for overlays."
      : "Wide cinematic establishing composition, human eye-level or plausible elevated viewpoint, controlled depth, and calm negative space on the left for user-interface overlays.";
  return `Use case: stylized-concept
Asset type: ${asset.category} asset for a cross-platform strategy game
Primary request: Create a premium ultra-realistic visual asset for the multiplayer strategy game SHADOWGRID.
Scene/backdrop: ${locationCharacteristics(asset)}
Subject: ${assetDescription(asset)}
Style/medium: contemporary Germany; high-end urban economic strategy simulation; cinematic corporate thriller atmosphere; subtle cyber-noir; physically plausible glass, concrete, steel, stone and asphalt; original scene, not a known photograph, film frame, game screenshot or branded design.
Composition/framing: ${composition}
Lighting/mood: ${timeOfDay(asset)} with natural cinematic lighting, realistic reflections and restrained atmosphere.
Color palette: black and anthracite framing, cool neutral blue-gray, restrained warm gold accents; warning red only if the gameplay state requires danger.
Materials/textures: physically plausible dark glass, brushed metal, concrete, stone and asphalt with realistic scale.
Constraints: no embedded captions or interface text; no real brands; no real authorities; no readable plates or addresses; no recognizable private people; no copied landmark-photo angle; space reserved for UI overlays; suitable for desktop and mobile crops; output aspect ratio ${asset.aspect_ratio}.
Avoid: ${globalNegativePrompt.replaceAll("\n", " ")}
Seed reference: ${asset.seed}. Style lock: ${styleVersion}.`;
}

function writePrompt(asset) {
  const path = join(ASSETS, "prompts", `${asset.asset_id}.txt`);
  atomicWrite(path, `${promptFor(asset)}\n`);
  return path;
}

function seeded(seed) {
  let value = seed >>> 0;
  return () => {
    value = (value * 1664525 + 1013904223) >>> 0;
    return value / 4294967296;
  };
}

function escapeXml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function proceduralSceneSvg(asset) {
  const { width, height, seed } = asset;
  const random = seeded(seed);
  const isNight = timeOfDay(asset).includes("night");
  const skyTop = isNight ? "#05070b" : "#aab8c2";
  const skyBottom = isNight ? "#18222a" : "#e2c8a4";
  const horizon = Math.round(height * 0.58);
  const buildings = [];
  let x = -Math.round(width * 0.02);
  while (x < width * 1.02) {
    const buildingWidth = Math.round(width * (0.025 + random() * 0.055));
    const buildingHeight = Math.round(height * (0.12 + random() * 0.32));
    const y = horizon - buildingHeight;
    const shade = Math.round(18 + random() * 28);
    const windows = [];
    const columns = Math.max(
      2,
      Math.floor(buildingWidth / Math.max(20, width / 90)),
    );
    const rows = Math.max(
      2,
      Math.floor(buildingHeight / Math.max(25, height / 32)),
    );
    for (let column = 0; column < columns; column += 1) {
      for (let row = 0; row < rows; row += 1) {
        if (random() > (isNight ? 0.48 : 0.78)) {
          const wx = x + 8 + column * ((buildingWidth - 16) / columns);
          const wy = y + 10 + row * ((buildingHeight - 18) / rows);
          windows.push(
            `<rect x="${wx.toFixed(1)}" y="${wy.toFixed(1)}" width="${Math.max(
              2,
              buildingWidth / columns - 8,
            ).toFixed(1)}" height="${Math.max(
              2,
              buildingHeight / rows - 10,
            ).toFixed(
              1,
            )}" rx="1" fill="${isNight ? "#d8b15b" : "#dce7eb"}" opacity="${
              isNight ? "0.55" : "0.25"
            }"/>`,
          );
        }
      }
    }
    buildings.push(
      `<g><rect x="${x}" y="${y}" width="${buildingWidth}" height="${buildingHeight}" fill="rgb(${shade},${
        shade + 5
      },${shade + 9})"/>${windows.join("")}</g>`,
    );
    x += buildingWidth + Math.round(width * (0.004 + random() * 0.008));
  }
  const towerX = Math.round(width * (0.61 + random() * 0.08));
  const towerWidth = Math.round(width * 0.11);
  const towerHeight = Math.round(height * 0.55);
  const gold = "#d8b15b";
  const controlCenter =
    asset.asset_id.includes("control-center") ||
    asset.asset_id.includes("headquarters")
      ? `<g filter="url(#shadow)">
          <path d="M ${towerX} ${horizon} L ${towerX + towerWidth * 0.12} ${
            horizon - towerHeight
          } L ${towerX + towerWidth * 0.84} ${horizon - towerHeight * 0.93} L ${
            towerX + towerWidth
          } ${horizon} Z" fill="#171e24"/>
          <path d="M ${towerX + towerWidth * 0.18} ${horizon - towerHeight * 0.91} L ${
            towerX + towerWidth * 0.78
          } ${horizon - towerHeight * 0.86} L ${towerX + towerWidth * 0.9} ${
            horizon - towerHeight * 0.06
          } L ${towerX + towerWidth * 0.08} ${
            horizon - towerHeight * 0.06
          } Z" fill="url(#glass)" stroke="${gold}" stroke-opacity="0.28"/>
        </g>`
      : "";
  const foreground = asset.asset_id.includes("control-center")
    ? `<path d="M0 ${height * 0.72} C${width * 0.25} ${height * 0.61}, ${width * 0.68} ${
        height * 0.67
      }, ${width} ${height * 0.57} L${width} ${height} L0 ${height}Z" fill="#07090c"/>
         <path d="M${width * 0.08} ${height * 0.78} L${width * 0.48} ${
           height * 0.68
         } L${width * 0.93} ${height * 0.78}" fill="none" stroke="${gold}" stroke-opacity="0.33" stroke-width="${
           width / 800
         }"/>`
    : `<path d="M0 ${height * 0.76} C${width * 0.3} ${height * 0.69}, ${width * 0.72} ${
        height * 0.74
      }, ${width} ${height * 0.64} L${width} ${height} L0 ${height}Z" fill="#11161a"/>`;
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
    <defs>
      <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop stop-color="${skyTop}"/><stop offset="1" stop-color="${skyBottom}"/></linearGradient>
      <linearGradient id="glass" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#33444e"/><stop offset=".48" stop-color="#111820"/><stop offset="1" stop-color="#26343c"/></linearGradient>
      <radialGradient id="glow" cx="${isNight ? "72%" : "22%"}" cy="24%" r="52%"><stop stop-color="${
        isNight ? "#6f8794" : "#f4d9a5"
      }" stop-opacity=".38"/><stop offset="1" stop-opacity="0"/></radialGradient>
      <filter id="shadow"><feDropShadow dx="0" dy="${height / 90}" stdDeviation="${
        height / 80
      }" flood-opacity=".45"/></filter>
      <filter id="grain"><feTurbulence baseFrequency=".85" numOctaves="2" seed="${
        seed % 97
      }" type="fractalNoise"/><feColorMatrix values="1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 .035 0"/></filter>
    </defs>
    <rect width="100%" height="100%" fill="url(#sky)"/>
    <rect width="100%" height="100%" fill="url(#glow)"/>
    <path d="M0 ${horizon + height * 0.03} Q${width * 0.32} ${horizon - height * 0.12} ${
      width * 0.62
    } ${horizon + height * 0.02} T${width} ${horizon - height * 0.02} L${width} ${
      horizon + height * 0.18
    } L0 ${horizon + height * 0.2}Z" fill="#6b7a7e" opacity=".18"/>
    ${buildings.join("")}
    ${controlCenter}
    <path d="M0 ${horizon + height * 0.09} C${width * 0.33} ${horizon + height * 0.01}, ${
      width * 0.72
    } ${horizon + height * 0.12}, ${width} ${horizon + height * 0.04}" fill="none" stroke="#8e9ca0" stroke-opacity=".23" stroke-width="${
      height * 0.035
    }"/>
    ${foreground}
    <path d="M${width * 0.55} ${height * 0.88} L${width * 0.83} ${
      height * 0.69
    }" stroke="${gold}" stroke-opacity=".56" stroke-width="${Math.max(
      2,
      width / 900,
    )}"/>
    <rect width="100%" height="100%" filter="url(#grain)" opacity=".45"/>
    <rect x="${width * 0.035}" y="${height * 0.06}" width="${width * 0.35}" height="${
      height * 0.78
    }" rx="${width * 0.006}" fill="#05080b" opacity=".08"/>
  </svg>`;
}

function brandMark({ centerX, centerY, radius, color, simplified = false }) {
  const scale = radius / 500;
  const transform = `translate(${centerX - radius} ${centerY - radius}) scale(${scale})`;
  const inner = simplified
    ? ""
    : `<path d="M500 260 700 375v250L500 740 300 625V375Z" fill="none" stroke="${color}" stroke-width="34" stroke-linejoin="round" opacity=".72"/>
       <path d="M500 260v480M300 375l400 250M700 375 300 625" fill="none" stroke="${color}" stroke-width="24" stroke-linecap="round"/>
       <circle cx="500" cy="500" r="58" fill="${color}"/>`;
  return `<g transform="${transform}">
    <path d="M500 90 850 290v420L500 910 150 710V290Z" fill="none" stroke="${color}" stroke-width="${simplified ? 76 : 52}" stroke-linejoin="round"/>
    ${inner}
  </g>`;
}

function brandDefs() {
  return `<defs>
    <radialGradient id="brand-bg" cx="32%" cy="22%" r="88%">
      <stop stop-color="#1b222a"/>
      <stop offset=".55" stop-color="#0d1116"/>
      <stop offset="1" stop-color="#06080b"/>
    </radialGradient>
    <pattern id="brand-grid" width="96" height="96" patternUnits="userSpaceOnUse">
      <path d="M96 0H0V96" fill="none" stroke="#8fa0aa" stroke-opacity=".09" stroke-width="3"/>
    </pattern>
  </defs>`;
}

function brandingSvg(asset) {
  const { asset_id: id, width, height } = asset;
  const dark = id.includes("-dark");
  const light = id.includes("-light");
  const gold = "#d8b15b";
  const nearBlack = "#080a0d";
  const offWhite = "#f6f4ee";
  const markColor = id.includes("-white")
    ? "#ffffff"
    : id.includes("-black") || light
      ? nearBlack
      : gold;
  const textColor = light ? nearBlack : offWhite;
  const rootStart = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="title"><title id="title">${escapeXml(asset.title)}</title>${brandDefs()}`;
  const rootEnd = "</svg>";

  if (id.includes("logo-horizontal")) {
    const background = `<rect width="${width}" height="${height}" fill="${dark ? nearBlack : "#f3f0e8"}"/>`;
    return `${rootStart}${background}
      ${brandMark({ centerX: 500, centerY: 500, radius: 400, color: markColor })}
      <text x="1020" y="604" fill="${textColor}" font-family="Arial, Helvetica, sans-serif" font-size="280" font-weight="700" letter-spacing="20" textLength="2020" lengthAdjust="spacing">SHADOWGRID</text>
    ${rootEnd}`;
  }
  if (id.includes("logo-vertical")) {
    const background = `<rect width="${width}" height="${height}" fill="${dark ? nearBlack : "#f3f0e8"}"/>`;
    return `${rootStart}${background}
      ${brandMark({ centerX: width / 2, centerY: 560, radius: 390, color: markColor })}
      <text x="${width / 2}" y="1240" text-anchor="middle" fill="${textColor}" font-family="Arial, Helvetica, sans-serif" font-size="150" font-weight="700" letter-spacing="10">SHADOWGRID</text>
    ${rootEnd}`;
  }
  if (id.includes("wordmark-horizontal")) {
    return `${rootStart}
      <text x="180" y="610" fill="${gold}" font-family="Arial, Helvetica, sans-serif" font-size="330" font-weight="700" letter-spacing="28" textLength="2840" lengthAdjust="spacing">SHADOWGRID</text>
      <path d="M184 706H3016" stroke="${gold}" stroke-width="12" opacity=".42"/>
    ${rootEnd}`;
  }
  if (id.includes("wordmark-compact")) {
    return `${rootStart}
      <text x="${width / 2}" y="690" text-anchor="middle" fill="${offWhite}" font-family="Arial, Helvetica, sans-serif" font-size="250" font-weight="700" letter-spacing="22">SHADOW</text>
      <text x="${width / 2}" y="1060" text-anchor="middle" fill="${gold}" font-family="Arial, Helvetica, sans-serif" font-size="310" font-weight="700" letter-spacing="52">GRID</text>
    ${rootEnd}`;
  }
  if (id.includes("app-icon-master")) {
    return `${rootStart}
      <rect width="${width}" height="${height}" fill="url(#brand-bg)"/>
      <rect width="${width}" height="${height}" fill="url(#brand-grid)"/>
      ${brandMark({ centerX: width / 2, centerY: height / 2, radius: width * 0.34, color: gold })}
    ${rootEnd}`;
  }
  if (id.includes("android-adaptive-foreground")) {
    return `${rootStart}
      ${brandMark({ centerX: width / 2, centerY: height / 2, radius: width * 0.28, color: gold })}
    ${rootEnd}`;
  }
  if (id.includes("android-adaptive-background")) {
    return `${rootStart}
      <rect width="${width}" height="${height}" fill="url(#brand-bg)"/>
      <rect width="${width}" height="${height}" fill="url(#brand-grid)"/>
      <circle cx="${width / 2}" cy="${height / 2}" r="${width * 0.32}" fill="none" stroke="${gold}" stroke-width="${width * 0.006}" opacity=".12"/>
    ${rootEnd}`;
  }
  if (id.includes("favicon")) {
    return `${rootStart}
      ${brandMark({ centerX: width / 2, centerY: height / 2, radius: width * 0.4, color: gold, simplified: true })}
    ${rootEnd}`;
  }
  return `${rootStart}
    ${brandMark({
      centerX: width / 2,
      centerY: height / 2,
      radius: width * (id.includes("monochrome") ? 0.39 : 0.4),
      color: markColor,
      simplified: id.includes("monochrome"),
    })}
  ${rootEnd}`;
}

function genericSvg(asset) {
  const color = asset.asset_id.includes("gold")
    ? "#d8b15b"
    : asset.asset_id.includes("silver")
      ? "#b8c0c7"
      : asset.asset_id.includes("bronze")
        ? "#a97245"
        : "currentColor";
  return `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" role="img" aria-labelledby="title">
    <title id="title">${escapeXml(asset.title)}</title>
    <path d="M12 2.5 20 7v10l-8 4.5L4 17V7Z" stroke="${color}" stroke-width="1.8" stroke-linejoin="round"/>
    <path d="m8 12 2.5 2.5L16.5 8.5M12 2.5V7M4 7l4 2.2M20 7l-4 2.2" stroke="${color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
  </svg>`;
}

function mapMarkerSvg(asset) {
  const name = asset.asset_id.replace(/^marker-/, "").replace(/-v1$/, "");
  const categoryColor = name.startsWith("influence-")
    ? "#8cc7e8"
    : name.startsWith("control-")
      ? "#e8e5dc"
      : "#d8b15b";
  const commonStart = `<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" color="${categoryColor}" role="img" aria-labelledby="title description">
    <title id="title">${escapeXml(asset.title)}</title>`;
  const commonEnd = `
    <desc id="description">Distinct text-free SHADOWGRID strategy-map marker.</desc>
  </svg>`;
  const cityMarkers = {
    metropolis: `<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.7"/>
      <circle cx="12" cy="12" r="6.5" stroke="currentColor" stroke-width="1.2" stroke-dasharray="1.5 1.5"/>
      <path d="M8 16V10h2v6m2 0V7h2v9m2 0v-4h2v4M6.5 16.5h11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>`,
    "large-city": `<path d="M12 2.5 21.5 12 12 21.5 2.5 12Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
      <path d="M7.5 16V10h2v6m2 0V7.5h2V16m2 0v-4h2v4M6.5 16.5h11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>`,
    "medium-city": `<circle cx="12" cy="12" r="7.5" stroke="currentColor" stroke-width="1.7"/>
      <path d="M8.5 16v-6h2.5v6m2 0V8h2.5v8M7.5 16.5h9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>`,
    "small-town": `<rect x="6.5" y="6.5" width="11" height="11" rx="2.5" stroke="currentColor" stroke-width="1.7"/>
      <path d="m8.5 12 3.5-3 3.5 3v4h-7Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
      <path d="M11 16v-3h2v3" stroke="currentColor" stroke-width="1.2"/>`,
    "home-city": `<path d="M12 2.5a7 7 0 0 1 7 7c0 4.8-7 12-7 12s-7-7.2-7-12a7 7 0 0 1 7-7Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
      <path d="m8.5 10.5 3.5-3 3.5 3v4h-7Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
      <circle cx="12" cy="12.2" r="1.2" fill="currentColor"/>`,
    "cartel-headquarters": `<path d="M12 2.5 20 7v10l-8 4.5L4 17V7Z" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round"/>
      <path d="M8 15.5V9l4-2 4 2v6.5M7 16h10M10 16v-4h4v4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="M9 5.5h6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>`,
    "contested-city": `<circle cx="12" cy="12" r="8.5" stroke="currentColor" stroke-width="1.7" stroke-dasharray="5 2"/>
      <path d="M5.5 9.5h5l-2-2m10 7h-5l2 2" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
      <path d="m9 15 6-6" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>`,
    "seasonal-event": `<path d="m12 2.5 2.1 5.4 5.4-2.1-2.1 5.4 5.1 2.1-5.5 2.1 2.2 5.3-5.3-2.1-2.1 4.9-2.1-5.2-5.4 2.1 2.1-5.3-4.9-2.1 5.2-2.1-2.1-5.4L10 8Z" stroke="currentColor" stroke-width="1.35" stroke-linejoin="round"/>
      <circle cx="12" cy="12.8" r="2.4" fill="currentColor"/>`,
  };
  if (cityMarkers[name]) {
    return `${commonStart}${cityMarkers[name]}${commonEnd}`;
  }

  const influenceGlyphs = {
    "influence-economy": `<path d="M7.5 16.5V12h2.5v4.5m2 0V8h2.5v8.5m2 0V10h2.5v6.5" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
      <path d="m7 9 4-3 3 1.5 3.5-3" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>`,
    "influence-street": `<path d="M7 5v5l3 2-3 2v5m10-14v5l-3 2 3 2v5M10 12h4" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="12" cy="12" r="1.7" fill="currentColor"/>`,
    "influence-information": `<path d="M6 12s2.3-4.2 6-4.2 6 4.2 6 4.2-2.3 4.2-6 4.2S6 12 6 12Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
      <circle cx="12" cy="12" r="2.1" stroke="currentColor" stroke-width="1.4"/>
      <circle cx="12" cy="12" r=".7" fill="currentColor"/>`,
    "influence-society": `<circle cx="12" cy="7.5" r="2" stroke="currentColor" stroke-width="1.4"/>
      <circle cx="7.5" cy="15.5" r="2" stroke="currentColor" stroke-width="1.4"/>
      <circle cx="16.5" cy="15.5" r="2" stroke="currentColor" stroke-width="1.4"/>
      <path d="m11 9.3-2.4 4.4m4.4-4.4 2.4 4.4M9.5 15.5h5" stroke="currentColor" stroke-width="1.3"/>`,
    "influence-digital": `<rect x="8" y="8" width="8" height="8" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
      <path d="M10.5 10.5h3v3h-3Zm1.5-6v3m0 9v3M4.5 12h3m9 0h3M6.5 6.5 8.7 8.7m6.6 6.6 2.2 2.2m0-11-2.2 2.2m-6.6 6.6-2.2 2.2" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>`,
  };
  if (influenceGlyphs[name]) {
    return `${commonStart}
      <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.6"/>
      <path d="M12 3v2m9 7h-2m-7 9v-2M3 12h2" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
      ${influenceGlyphs[name]}${commonEnd}`;
  }

  const controlGlyphs = {
    "control-economic-network": `<circle cx="8" cy="12" r="1.5" fill="currentColor"/><circle cx="12" cy="8" r="1.5" fill="currentColor"/><circle cx="16" cy="12" r="1.5" fill="currentColor"/><circle cx="12" cy="16" r="1.5" fill="currentColor"/>
      <path d="m9 11 2-2m2 0 2 2m0 2-2 2m-2 0-2-2" stroke="currentColor" stroke-width="1.3"/>`,
    "control-information-center": `<path d="M12 7 17 12 12 17 7 12Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
      <circle cx="12" cy="12" r="1.6" fill="currentColor"/>
      <path d="M12 4v3m8 5h-3m-5 8v-3M4 12h3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>`,
    "control-logistics-node": `<rect x="8" y="8" width="8" height="8" rx="1.5" stroke="currentColor" stroke-width="1.5"/>
      <path d="M4 8h3l-1.5-1.5M20 16h-3l1.5 1.5M8 20v-3l-1.5 1.5M16 4v3l1.5-1.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="12" cy="12" r="1.5" fill="currentColor"/>`,
    "control-social-access": `<circle cx="9" cy="10" r="1.8" stroke="currentColor" stroke-width="1.4"/><circle cx="15" cy="10" r="1.8" stroke="currentColor" stroke-width="1.4"/>
      <path d="M6.5 17c.4-2.6 1.4-4 3-4 1.2 0 2 .6 2.5 1.6.5-1 1.3-1.6 2.5-1.6 1.6 0 2.6 1.4 3 4M12 4v4" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/>`,
    "control-digital-node": `<circle cx="12" cy="12" r="2.4" stroke="currentColor" stroke-width="1.5"/>
      <path d="M12 4v5.5m0 5V20M4 12h5.5m5 0H20M6.5 6.5l3.9 3.9m3.2 3.2 3.9 3.9m0-11-3.9 3.9m-3.2 3.2-3.9 3.9" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
      <circle cx="12" cy="12" r=".9" fill="currentColor"/>`,
    "control-coordination-center": `<path d="M12 6.5 17.5 9.7v6.6L12 19.5l-5.5-3.2V9.7Z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/>
      <circle cx="12" cy="13" r="1.7" fill="currentColor"/>
      <path d="M12 3v3.5m7.8 2-2.8 1.6m2.8 7.4L17 15.9M12 21v-1.5m-7.8-2L7 15.9M4.2 8.5 7 10.1" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>`,
  };
  if (!controlGlyphs[name]) {
    throw new Error(`Unsupported map marker '${asset.asset_id}'.`);
  }
  return `${commonStart}
    <path d="M12 2.5 20 7v10l-8 4.5L4 17V7Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>
    ${controlGlyphs[name]}${commonEnd}`;
}

function citySilhouetteSvg(asset) {
  const { width, height, seed } = asset;
  const random = seeded(seed);
  const skylineBase = height * 0.63;
  const buildings = [];
  let x = 0;
  while (x < width) {
    const buildingWidth = Math.round(54 + random() * 118);
    const buildingHeight = Math.round(105 + random() * 275);
    const y = skylineBase - buildingHeight;
    const roofVariant = Math.floor(random() * 4);
    const roof =
      roofVariant === 0
        ? `L${x + buildingWidth * 0.5} ${y - buildingWidth * 0.13} L${x + buildingWidth} ${y}`
        : roofVariant === 1
          ? `L${x + buildingWidth * 0.18} ${y - 24} L${x + buildingWidth * 0.82} ${y - 24} L${x + buildingWidth} ${y}`
          : `L${x + buildingWidth} ${y}`;
    buildings.push(
      `<path d="M${x} ${skylineBase}V${y}${roof}V${skylineBase}Z" fill="#d8b15b" fill-opacity="${(0.42 + random() * 0.34).toFixed(2)}"/>`,
    );
    x += buildingWidth + Math.round(8 + random() * 24);
  }
  const trussSegments = Array.from({ length: 14 }, (_, index) => {
    const start = 230 + index * 190;
    return `M${start} 718l95-64 95 64`;
  }).join(" ");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" fill="none" role="img" aria-labelledby="title description">
    <title id="title">${escapeXml(asset.title)}</title>
    <desc id="description">Text-free fictionalized city silhouette with an abstract river and bridge.</desc>
    <g>
      ${buildings.join("")}
      <path d="M1420 ${skylineBase}V468h74v-72h56v72h76V${skylineBase}Zm36-72c0-82 52-136 66-136s66 54 66 136Z" fill="#d8b15b" fill-opacity=".76"/>
      <path d="M0 ${skylineBase}H${width}" stroke="#e6c76e" stroke-width="12" stroke-opacity=".84"/>
      <path d="M0 828c420-34 720 28 1110 0s720-26 1040 4 650 22 1050-10M0 900c470-28 790 18 1200-2s720-16 1080 4 550 12 920-10" stroke="#8cc7e8" stroke-width="10" stroke-linecap="round" stroke-opacity=".42"/>
      <path d="M190 724H2940" stroke="#d8b15b" stroke-width="28" stroke-linecap="round"/>
      <path d="${trussSegments}" stroke="#d8b15b" stroke-width="15" stroke-linejoin="round" stroke-opacity=".9"/>
      <path d="M430 724v116m680-116v116m680-116v116m680-116v116" stroke="#d8b15b" stroke-width="26" stroke-linecap="round"/>
      <path d="M382 840h96m584 0h96m584 0h96m584 0h96" stroke="#d8b15b" stroke-width="18" stroke-linecap="round"/>
    </g>
  </svg>`;
}

function germanyMapSvg(asset) {
  const { asset_id: id, title, width, height } = asset;
  const rootStart = `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-labelledby="title description">
    <title id="title">${escapeXml(title)}</title>`;
  const rootEnd = "</svg>";

  if (id.includes("map-background")) {
    const themes = {
      day: {
        base: "#283136",
        edge: "#11171b",
        glow: "#718088",
        grid: "#d5dde0",
        contour: "#e5c66e",
      },
      night: {
        base: "#111b23",
        edge: "#04070a",
        glow: "#36566b",
        grid: "#8fb3c5",
        contour: "#d8b15b",
      },
      neutral: {
        base: "#252a2d",
        edge: "#0c0f11",
        glow: "#596166",
        grid: "#c4c8ca",
        contour: "#9da5a8",
      },
    };
    const variant = id.includes("-day-")
      ? "day"
      : id.includes("-night-")
        ? "night"
        : "neutral";
    const theme = themes[variant];
    return `${rootStart}
    <desc id="description">Text-free ${variant} strategy-map background with a restrained grid and contour texture.</desc>
    <defs>
      <radialGradient id="map-base" cx="44%" cy="38%" r="78%">
        <stop stop-color="${theme.glow}"/>
        <stop offset=".5" stop-color="${theme.base}"/>
        <stop offset="1" stop-color="${theme.edge}"/>
      </radialGradient>
      <pattern id="map-grid-small" width="48" height="48" patternUnits="userSpaceOnUse">
        <path d="M48 0H0V48" fill="none" stroke="${theme.grid}" stroke-opacity=".055" stroke-width="2"/>
      </pattern>
      <pattern id="map-grid-large" width="240" height="240" patternUnits="userSpaceOnUse">
        <path d="M240 0H0V240" fill="none" stroke="${theme.grid}" stroke-opacity=".1" stroke-width="3"/>
      </pattern>
      <linearGradient id="map-vignette" x1="0" y1="0" x2="1" y2="1">
        <stop stop-color="#000000" stop-opacity=".2"/>
        <stop offset=".45" stop-color="#000000" stop-opacity="0"/>
        <stop offset="1" stop-color="#000000" stop-opacity=".34"/>
      </linearGradient>
    </defs>
    <rect width="${width}" height="${height}" fill="url(#map-base)"/>
    <rect width="${width}" height="${height}" fill="url(#map-grid-small)"/>
    <rect width="${width}" height="${height}" fill="url(#map-grid-large)"/>
    <g fill="none" stroke="${theme.contour}" stroke-opacity=".075" stroke-width="3">
      <path d="M-120 262C214 62 484 102 750 256s574 172 876 18 466-98 650 16"/>
      <path d="M-160 426C146 232 438 240 702 400s584 186 890 26 492-86 676 88"/>
      <path d="M-140 654C186 448 502 486 744 632s534 176 842 24 504-82 682 76"/>
      <path d="M-180 888C168 674 462 704 746 856s562 162 852 20 474-72 668 96"/>
    </g>
    <path d="M0 ${height * 0.18}H${width}M0 ${height * 0.82}H${width}" stroke="${theme.grid}" stroke-opacity=".06" stroke-width="2"/>
    <rect width="${width}" height="${height}" fill="url(#map-vignette)"/>
    <rect x="32" y="32" width="${width - 64}" height="${height - 64}" rx="24" fill="none" stroke="${theme.grid}" stroke-opacity=".12" stroke-width="3"/>
    ${rootEnd}`;
  }

  const palettes = {
    economy: ["#182129", "#38505b", "#92753d", "#d8b15b", "#f4df99"],
    information: ["#111c26", "#24465b", "#377a96", "#75bfd0", "#d5f2f3"],
    authority: ["#1b2127", "#4c555c", "#8b7047", "#bd7048", "#d6a064"],
    organization: ["#171a20", "#3d334e", "#67527c", "#a08273", "#d8b15b"],
    event: ["#111a22", "#285064", "#4f8b92", "#bd9251", "#e6c76e"],
  };
  const variant = Object.keys(palettes).find((name) => id.includes(name));
  if (!variant) throw new Error(`Unsupported Germany-map asset '${id}'.`);
  const colors = palettes[variant];
  const segmentWidth = width * 0.14;
  const barX = width * 0.15;
  const barY = height * 0.38;
  const barHeight = height * 0.24;
  const segments = colors
    .map((color, index) => {
      const x = barX + segmentWidth * index;
      const dots = Array.from(
        { length: index + 1 },
        (_, dotIndex) =>
          `<circle cx="${x + segmentWidth * (0.5 + (dotIndex - index / 2) * 0.13)}" cy="${barY + barHeight * 0.5}" r="${10 + index * 2}" fill="#ffffff" fill-opacity="${0.24 + index * 0.1}"/>`,
      ).join("");
      return `<g>
        <rect x="${x}" y="${barY}" width="${segmentWidth}" height="${barHeight}" fill="${color}"/>
        ${dots}
        <path d="M${x + segmentWidth} ${barY}V${barY + barHeight}" stroke="#f4f1e8" stroke-opacity=".28" stroke-width="3"/>
      </g>`;
    })
    .join("");
  return `${rootStart}
    <desc id="description">Text-free five-step ${variant} heatmap legend. Increasing dot count and density duplicate the color progression.</desc>
    <defs>
      <radialGradient id="legend-background" cx="50%" cy="44%" r="72%">
        <stop stop-color="#253039"/>
        <stop offset=".58" stop-color="#10161b"/>
        <stop offset="1" stop-color="#06090c"/>
      </radialGradient>
      <pattern id="legend-grid" width="64" height="64" patternUnits="userSpaceOnUse">
        <path d="M64 0H0V64" fill="none" stroke="#c9d0d3" stroke-opacity=".045" stroke-width="2"/>
      </pattern>
    </defs>
    <rect width="${width}" height="${height}" fill="url(#legend-background)"/>
    <rect width="${width}" height="${height}" fill="url(#legend-grid)"/>
    <g>
      ${segments}
      <rect x="${barX}" y="${barY}" width="${segmentWidth * colors.length}" height="${barHeight}" rx="18" fill="none" stroke="#f4f1e8" stroke-opacity=".62" stroke-width="5"/>
    </g>
    <path d="M${barX} ${barY + barHeight + 54}H${barX + segmentWidth * colors.length}" stroke="#d8b15b" stroke-opacity=".42" stroke-width="3"/>
    <rect x="32" y="32" width="${width - 64}" height="${height - 64}" rx="24" fill="none" stroke="#d8b15b" stroke-opacity=".14" stroke-width="3"/>
    ${rootEnd}`;
}

async function generateProcedural(asset) {
  writePrompt(asset);
  const sourceDirectory = sourceDirectoryFor(asset);
  mkdir(sourceDirectory);
  const isVector =
    asset.source_type === "procedural" &&
    (asset.batch === "branding" ||
      asset.batch === "map-markers" ||
      asset.batch === "germany-map" ||
      asset.batch === "premium-cities" ||
      asset.batch === "ui-icons" ||
      asset.batch === "cartel-crests" ||
      asset.batch === "rankings-rewards");
  if (isVector) {
    const svg =
      asset.batch === "branding"
        ? brandingSvg(asset)
        : asset.batch === "germany-map"
          ? germanyMapSvg(asset)
          : asset.batch === "map-markers"
            ? mapMarkerSvg(asset)
            : asset.batch === "premium-cities"
              ? citySilhouetteSvg(asset)
              : genericSvg(asset);
    const sourcePath = join(sourceDirectory, `${asset.asset_id}.svg`);
    atomicWrite(sourcePath, `${svg}\n`);
    const productionPath = join(
      ASSETS,
      "production",
      "svg",
      `${asset.asset_id}.svg`,
    );
    copyFileSync(sourcePath, productionPath);
    const productionFiles = [productionPath];
    if (
      asset.batch === "branding" &&
      (asset.transparent_background ||
        asset.asset_id.includes("app-icon-master") ||
        asset.asset_id.includes("adaptive-background"))
    ) {
      const pngPath = join(
        ASSETS,
        "production",
        "png",
        `${asset.asset_id}-${asset.width}.png`,
      );
      const webpPath = join(
        ASSETS,
        "production",
        "webp",
        `${asset.asset_id}-${asset.width}.webp`,
      );
      const pngSource = sharp(Buffer.from(svg));
      const webpSource = sharp(Buffer.from(svg));
      if (!asset.transparent_background) {
        pngSource.flatten({ background: "#080a0d" });
        webpSource.flatten({ background: "#080a0d" });
      }
      await Promise.all([
        pngSource.png({ compressionLevel: 9 }).toFile(pngPath),
        webpSource.webp({ lossless: true, effort: 4 }).toFile(webpPath),
      ]);
      productionFiles.push(pngPath, webpPath);
      const runtimeSize = asset.asset_id.includes("favicon")
        ? 64
        : asset.asset_id.includes("app-icon") ||
            asset.asset_id.includes("adaptive-foreground")
          ? 1024
          : null;
      if (runtimeSize) {
        const runtimePngPath = join(
          ASSETS,
          "production",
          "png",
          `${asset.asset_id}-${runtimeSize}.png`,
        );
        const runtimeSource = sharp(Buffer.from(svg)).resize(
          runtimeSize,
          runtimeSize,
        );
        if (!asset.transparent_background) {
          runtimeSource.flatten({ background: "#080a0d" });
        }
        await runtimeSource.png({ compressionLevel: 9 }).toFile(runtimePngPath);
        productionFiles.push(runtimePngPath);
      }
    }
    const validation = validateSvg(productionPath, asset);
    const updated = await completeAsset(asset, {
      providerName: "procedural",
      sourcePath,
      productionFiles,
      validation,
      sourceType: "procedural",
      qualityStatus: validation.ok ? "approved" : "review_required",
      qualityScore: validation.ok ? 88 : null,
      reviewStatus: validation.ok ? "automatic-approved" : "review-required",
      notes: validation.issues,
    });
    return updated;
  }
  const sourcePath = join(sourceDirectory, `${asset.asset_id}.png`);
  const svg = proceduralSceneSvg(asset);
  const source = sharp(Buffer.from(svg));
  if (!asset.transparent_background) source.flatten({ background: "#080a0d" });
  await source.png({ compressionLevel: 9 }).toFile(sourcePath);
  const variants = await optimizeRaster(asset, sourcePath);
  const validation = await validateRaster(sourcePath, asset);
  return completeAsset(asset, {
    providerName: "disabled",
    sourcePath,
    productionFiles: variants,
    validation,
    sourceType: "procedural-fallback",
    qualityStatus: "review_required",
    qualityScore: null,
    reviewStatus: "provider-disabled-review-required",
    notes: [
      ...validation.issues,
      "Provider is disabled. This deterministic premium fallback is functional but is not represented as a photorealistic generated image.",
    ],
  });
}

function sourceDirectoryFor(asset) {
  const map = {
    "style-proof": "style-proof",
    branding: "branding",
    city: "cities",
    district: "districts",
    business: "businesses",
    facility: "facilities",
    character: "characters",
    avatar: "characters",
    pvp: "pvp",
    "organization-conflict": "cartels",
    crest: "cartels",
    event: "events",
    tutorial: "tutorial",
    map: "maps",
    marker: "maps",
    icon: "icons",
    overlay: "effects",
    reward: "rewards",
    marketing: "marketing",
    mobile: "marketing",
  };
  return join(ASSETS, "source", map[asset.category] ?? "global");
}

async function optimizeRaster(asset, sourcePath) {
  const outputFiles = [];
  const source = sharp(sourcePath, { failOn: "error" });
  const metadata = await source.metadata();
  const ratio = asset.width / asset.height;
  await Promise.all(
    responsiveWidths.map(async (width) => {
      const height = Math.round(width / ratio);
      const resize = {
        width,
        height,
        fit: "cover",
        position: "centre",
        withoutEnlargement: false,
      };
      const avifPath = join(
        ASSETS,
        "production",
        "avif",
        `${asset.asset_id}-${width}.avif`,
      );
      const webpPath = join(
        ASSETS,
        "production",
        "webp",
        `${asset.asset_id}-${width}.webp`,
      );
      await Promise.all([
        sharp(sourcePath)
          .resize(resize)
          .avif({ quality: width <= 640 ? 55 : 62, effort: 1 })
          .toFile(avifPath),
        sharp(sourcePath)
          .resize(resize)
          .webp({ quality: width <= 640 ? 68 : 76, effort: 3 })
          .toFile(webpPath),
      ]);
      outputFiles.push(avifPath, webpPath);
    }),
  );
  const pngWidth = Math.min(1280, metadata.width ?? asset.width);
  const pngPath = join(
    ASSETS,
    "production",
    "png",
    `${asset.asset_id}-${pngWidth}.png`,
  );
  await sharp(sourcePath)
    .resize({
      width: pngWidth,
      height: Math.round(pngWidth / ratio),
      fit: "cover",
      position: "centre",
    })
    .png({ compressionLevel: 9, palette: false })
    .toFile(pngPath);
  outputFiles.push(pngPath);
  return outputFiles;
}

async function validateRaster(path, asset) {
  const issues = [];
  if (!existsSync(path))
    return { ok: false, issues: ["Source file is missing."] };
  if (statSync(path).size < 20_000)
    issues.push("Source file is below the 20 KB minimum.");
  let metadata;
  try {
    metadata = await sharp(path, { failOn: "error" }).metadata();
  } catch (error) {
    return { ok: false, issues: [`Image decoder failed: ${error.message}`] };
  }
  if (metadata.width !== asset.width || metadata.height !== asset.height) {
    issues.push(
      `Unexpected source dimensions ${metadata.width}x${metadata.height}; expected ${asset.width}x${asset.height}.`,
    );
  }
  if (!["srgb", "rgb16", "p3"].includes(metadata.space ?? "")) {
    issues.push(
      `Unexpected or missing color space: ${metadata.space ?? "unknown"}.`,
    );
  }
  if (!asset.transparent_background && metadata.hasAlpha) {
    issues.push("Unexpected alpha channel on an opaque asset.");
  }
  return {
    ok: issues.length === 0,
    issues,
    technical: {
      width: metadata.width,
      height: metadata.height,
      format: metadata.format,
      color_space: metadata.space,
      has_alpha: metadata.hasAlpha ?? false,
      bytes: statSync(path).size,
    },
  };
}

function validateSvg(path, asset) {
  const issues = [];
  const source = readFileSync(path, "utf8");
  if (!source.includes("<svg")) issues.push("Missing SVG root.");
  if (!source.includes("viewBox=")) issues.push("Missing SVG viewBox.");
  if (!source.includes(`width="${asset.width}"`)) {
    issues.push(`SVG width does not match manifest width ${asset.width}.`);
  }
  if (!source.includes(`height="${asset.height}"`)) {
    issues.push(`SVG height does not match manifest height ${asset.height}.`);
  }
  if (source.includes("<image"))
    issues.push("Embedded raster images are forbidden.");
  if (source.includes("<script"))
    issues.push("Scripts are forbidden in production SVG.");
  if (asset.batch === "ui-icons" && !source.includes('viewBox="0 0 24 24"')) {
    issues.push("UI icon does not use the required 24 × 24 viewBox.");
  }
  if (statSync(path).size > 100_000) issues.push("SVG exceeds 100 KB.");
  return {
    ok: issues.length === 0,
    issues,
    technical: { format: "svg", bytes: statSync(path).size },
  };
}

async function completeAsset(
  asset,
  {
    providerName,
    sourcePath,
    productionFiles,
    validation,
    sourceType,
    qualityStatus,
    qualityScore,
    reviewStatus,
    notes,
    visualReview = null,
    license = "project-owned-generated-asset",
    provenance = null,
  },
) {
  const createdAt = now();
  const runtimeFiles = integrateRuntimeAsset(asset, productionFiles);
  const isAuthBackground = /^global-(login|registration)-/.test(asset.asset_id);
  const isWorldSelectionBackground = asset.asset_id.startsWith(
    "global-world-selection-",
  );
  const isMobileAuthBackground =
    isAuthBackground && asset.asset_id.includes("-mobile-");
  const isMobileWorldSelectionBackground =
    isWorldSelectionBackground && asset.asset_id.includes("-mobile-");
  const focalPoint =
    isAuthBackground || isWorldSelectionBackground
      ? isMobileAuthBackground || isMobileWorldSelectionBackground
        ? { x: 0.76, y: 0.34 }
        : { x: 0.82, y: 0.48 }
      : { x: 0.62, y: 0.44 };
  const safeArea =
    isAuthBackground || isWorldSelectionBackground
      ? isMobileAuthBackground || isMobileWorldSelectionBackground
        ? { x: 0.08, y: 0.14, width: 0.84, height: 0.76 }
        : isWorldSelectionBackground
          ? { x: 0.2, y: 0.14, width: 0.6, height: 0.76 }
          : { x: 0.28, y: 0.16, width: 0.44, height: 0.72 }
      : { x: 0.08, y: 0.08, width: 0.84, height: 0.76 };
  const metadata = {
    asset_id: asset.asset_id,
    manifest_order: asset.order,
    category: asset.category,
    batch: asset.batch,
    city: asset.city ?? null,
    variant: asset.variant ?? null,
    gameplay_state: asset.gameplay_state,
    aspect_ratio: asset.aspect_ratio,
    width: asset.width,
    height: asset.height,
    source_type: sourceType,
    provider: providerName,
    model:
      providerName === "codex-built-in" ? "built-in-image-generator" : null,
    prompt_file: `assets/prompts/${asset.asset_id}.txt`,
    prompt_version: asset.prompt_version,
    style_version: asset.style_version,
    seed: asset.seed,
    content_hash: sha256(sourcePath),
    source_file: relative(sourcePath),
    production_files: productionFiles.map((path) => ({
      path: relative(path),
      bytes: statSync(path).size,
      sha256: sha256(path),
    })),
    runtime_files: runtimeFiles.map((path) => ({
      path: relative(path),
      bytes: statSync(path).size,
      sha256: sha256(path),
    })),
    contains_text:
      asset.batch === "branding" &&
      (asset.asset_id.includes("logo") || asset.asset_id.includes("wordmark")),
    contains_real_people: false,
    contains_real_logos: false,
    moderation_status: "approved",
    quality_score: qualityScore,
    quality_status: qualityStatus,
    review_status: reviewStatus,
    visual_review: visualReview,
    technical_validation: validation,
    focal_point: focalPoint,
    safe_area: safeArea,
    created_at: createdAt,
    license,
    provenance,
    notes,
  };
  writeJson(join(ASSETS, "metadata", `${asset.asset_id}.json`), metadata);
  const status =
    qualityStatus === "approved"
      ? "approved"
      : validation.ok
        ? "review_required"
        : asset.attempts + 1 >= maxRetries
          ? "failed"
          : "review_required";
  return {
    ...asset,
    status,
    attempts: (asset.attempts ?? 0) + 1,
    completed_at: createdAt,
    failure_reason: validation.ok ? null : validation.issues.join(" "),
  };
}

function integrateRuntimeAsset(asset, productionFiles) {
  if (
    asset.asset_id.startsWith("global-") ||
    asset.batch === "germany-map" ||
    asset.batch === "map-markers" ||
    asset.batch === "premium-cities"
  ) {
    const runtimeAssetDirectory =
      asset.batch === "germany-map"
        ? "maps"
        : asset.batch === "map-markers"
          ? "markers"
          : asset.batch === "premium-cities"
            ? "cities"
            : "global";
    const runtimeDirectory = join(
      ROOT,
      "apps",
      "web",
      "public",
      "assets",
      runtimeAssetDirectory,
    );
    mkdir(runtimeDirectory);
    return productionFiles.map((source) => {
      const target = join(runtimeDirectory, basename(source));
      copyFileSync(source, target);
      return target;
    });
  }
  const integrations = {
    "branding-shadowgrid-logo-horizontal-dark-v1": [
      {
        target: join(
          ROOT,
          "apps",
          "web",
          "public",
          "assets",
          "branding",
          "shadowgrid-logo-horizontal-dark.svg",
        ),
        sourceSuffix: ".svg",
      },
    ],
    "branding-shadowgrid-app-icon-master-v1": [
      {
        target: join(ROOT, "apps", "mobile", "assets", "icon.png"),
        sourceSuffix: "-1024.png",
      },
      {
        target: join(ROOT, "apps", "mobile", "assets", "icon-source.svg"),
        sourceSuffix: ".svg",
      },
      {
        target: join(ROOT, "apps", "web", "public", "icon.svg"),
        sourceSuffix: ".svg",
      },
    ],
    "branding-shadowgrid-android-adaptive-foreground-v1": [
      {
        target: join(ROOT, "apps", "mobile", "assets", "adaptive-icon.png"),
        sourceSuffix: "-1024.png",
      },
    ],
    "branding-shadowgrid-favicon-v1": [
      {
        target: join(ROOT, "apps", "mobile", "assets", "favicon.png"),
        sourceSuffix: "-64.png",
      },
      {
        target: join(ROOT, "apps", "web", "public", "favicon.svg"),
        sourceSuffix: ".svg",
      },
    ],
  };
  const targets = integrations[asset.asset_id] ?? [];
  const runtimeFiles = [];
  for (const { target, sourceSuffix } of targets) {
    const source = productionFiles.find((path) => path.endsWith(sourceSuffix));
    if (!source) {
      throw new Error(
        `No ${extname(target)} production file exists for ${asset.asset_id}.`,
      );
    }
    mkdir(dirname(target));
    copyFileSync(source, target);
    runtimeFiles.push(target);
  }
  return runtimeFiles;
}

function recordError(asset, message, code = "generation_error") {
  const errors = readJson(ERROR_PATH, {
    project: "shadowgrid",
    version: 1,
    errors: [],
  });
  errors.errors.push({
    asset_id: asset.asset_id,
    batch: asset.batch,
    code,
    message,
    created_at: now(),
  });
  writeJson(ERROR_PATH, errors);
}

function estimatedCost(asset) {
  const configured = Number(
    process.env.IMAGE_GENERATION_ESTIMATED_COST_EUR || 0,
  );
  if (provider === "disabled" || asset.source_type === "procedural") return 0;
  return Number.isFinite(configured) && configured >= 0 ? configured : 0;
}

function budgetAllows(asset) {
  const cost = readJson(COST_PATH, { total_spent_eur: 0, entries: [] });
  const today = now().slice(0, 10);
  const spentToday = cost.entries
    .filter((entry) => String(entry.created_at).startsWith(today))
    .reduce((sum, entry) => sum + Number(entry.cost_eur || 0), 0);
  const estimate = estimatedCost(asset);
  return {
    ok:
      spentToday + estimate <= dailyBudget &&
      Number(cost.total_spent_eur || 0) + estimate <= totalBudget,
    estimate,
    spentToday,
    spentTotal: Number(cost.total_spent_eur || 0),
  };
}

async function processAsset(manifest, asset) {
  syncState(manifest, asset);
  writePrompt(asset);
  const budget = budgetAllows(asset);
  if (!budget.ok) {
    recordError(
      asset,
      "Configured budget would be exceeded; procedural fallback used.",
      "provider_budget_blocked",
    );
  }
  if (
    asset.source_type === "svg-geodata" ||
    asset.source_type === "app-screenshot"
  ) {
    const reason =
      asset.source_type === "svg-geodata"
        ? "Licensed geographic source data must be supplied before this asset can be processed."
        : "A functioning application screen must be captured; generated mock interfaces are forbidden.";
    const updated = {
      ...asset,
      status: "review_required",
      attempts: (asset.attempts ?? 0) + 1,
      completed_at: now(),
      failure_reason: reason,
    };
    recordError(asset, reason, `${asset.source_type}_input_required`);
    setAsset(manifest, updated);
    return updated;
  }
  if (
    asset.source_type === "generated" &&
    provider !== "disabled" &&
    budget.ok
  ) {
    const reason = `Provider '${provider}' is configured, but live provider execution is intentionally not performed by this repository command. Use the secret-safe provider boundary or Codex built-in generation and ingest the result.`;
    recordError(asset, reason, "external_generation_required");
    enqueueGeneration(asset);
    const updated = {
      ...asset,
      status: "review_required",
      attempts: asset.attempts ?? 0,
      completed_at: null,
      failure_reason: reason,
    };
    setAsset(manifest, updated);
    return updated;
  }
  const updated = await generateProcedural(asset);
  setAsset(manifest, updated);
  console.log(`${updated.status}: ${asset.asset_id}`);
  return updated;
}

function enqueueGeneration(asset) {
  const jobs = readJson(JOBS_PATH, {
    project: "shadowgrid",
    prompt_version: promptVersion,
    style_version: styleVersion,
    jobs: [],
  });
  const job = {
    asset_id: asset.asset_id,
    prompt_file: `assets/prompts/${asset.asset_id}.txt`,
    width: asset.width,
    height: asset.height,
    aspect_ratio: asset.aspect_ratio,
    seed: asset.seed,
    status: "awaiting_external_generation",
    updated_at: now(),
  };
  const index = jobs.jobs.findIndex(
    (candidate) => candidate.asset_id === asset.asset_id,
  );
  if (index >= 0) jobs.jobs[index] = job;
  else jobs.jobs.push(job);
  writeJson(JOBS_PATH, jobs);
}

async function runStyleProof() {
  const manifest = createManifest();
  const styleAssets = manifest.assets.filter(
    (asset) => asset.batch === "style-proof",
  );
  for (const asset of styleAssets) {
    if (asset.status === "approved") continue;
    await processAsset(manifest, asset);
  }
  await createContactSheet("style-proof");
  updateStyleGate(manifest);
  writeReports(manifest);
}

function updateStyleGate(manifest) {
  const styleAssets = manifest.assets.filter(
    (asset) => asset.batch === "style-proof",
  );
  const approved =
    styleAssets.length === 5 &&
    styleAssets.every((asset) => asset.status === "approved");
  const lock = readJson(STYLE_LOCK_PATH, styleLock);
  lock.status = approved ? "frozen" : "awaiting-review";
  lock.frozen_at = approved ? (lock.frozen_at ?? now()) : null;
  lock.style_proof_assets = styleAssets.map((asset) => ({
    asset_id: asset.asset_id,
    status: asset.status,
  }));
  writeJson(STYLE_LOCK_PATH, lock);
  if (approved)
    console.log("Style gate approved and visual style lock frozen.");
  else {
    console.log(
      "Style gate remains closed. Ingest and approve all five generated style proofs before assets:next.",
    );
  }
}

function styleGateApproved(manifest) {
  const lock = readJson(STYLE_LOCK_PATH, styleLock);
  return (
    lock.status === "frozen" &&
    manifest.assets
      .filter((asset) => asset.batch === "style-proof")
      .every((asset) => asset.status === "approved")
  );
}

async function runNext() {
  const manifest = currentManifest();
  if (!styleGateApproved(manifest)) {
    throw new Error(
      "Style-proof gate is closed. Run assets:style-proof, visually review the five references, and ingest approved generated images first.",
    );
  }
  const asset = manifest.assets.find(
    (candidate) =>
      candidate.batch !== "style-proof" &&
      candidate.required &&
      candidate.status !== "approved",
  );
  if (!asset) {
    console.log("Every required manifest entry is approved.");
    return;
  }
  await processAsset(manifest, asset);
  await createContactSheet(asset.batch);
  writeReports(manifest);
}

function readOption(name) {
  const exact = `--${name}`;
  const equals = `--${name}=`;
  const argument = process.argv.find((value) => value.startsWith(equals));
  if (argument) return argument.slice(equals.length);
  const index = process.argv.indexOf(exact);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

async function runBatch() {
  const batch = readOption("batch");
  if (!batch) throw new Error("Missing --batch=<batch-id>.");
  const manifest = currentManifest();
  if (batch !== "style-proof" && !styleGateApproved(manifest)) {
    throw new Error("Style-proof gate is closed.");
  }
  const assets = manifest.assets.filter(
    (asset) => asset.batch === batch && asset.status !== "approved",
  );
  if (assets.length === 0)
    throw new Error(`No pending assets found for batch '${batch}'.`);
  for (const asset of assets) await processAsset(manifest, asset);
  await createContactSheet(batch);
  writeReports(manifest);
}

async function runCity() {
  const city = readOption("city");
  if (!city) throw new Error("Missing --city=<city-id>.");
  const manifest = currentManifest();
  if (!styleGateApproved(manifest))
    throw new Error("Style-proof gate is closed.");
  const assets = manifest.assets.filter(
    (asset) => asset.city === city && asset.status !== "approved",
  );
  if (assets.length === 0)
    throw new Error(`No pending assets found for city '${city}'.`);
  for (const asset of assets) await processAsset(manifest, asset);
  await createContactSheet("premium-cities");
  writeReports(manifest);
}

async function runAll() {
  const manifest = currentManifest();
  if (!styleGateApproved(manifest))
    throw new Error("Style-proof gate is closed.");
  for (const asset of manifest.assets) {
    if (asset.status !== "approved") await processAsset(manifest, asset);
  }
  await createAllContactSheets();
  writeReports(manifest);
}

async function regenerate() {
  const assetId = readOption("asset");
  if (!assetId) throw new Error("Missing --asset=<asset-id>.");
  const manifest = currentManifest();
  const asset = manifest.assets.find(
    (candidate) => candidate.asset_id === assetId,
  );
  if (!asset) throw new Error(`Unknown asset '${assetId}'.`);
  if (asset.batch !== "style-proof" && !styleGateApproved(manifest)) {
    throw new Error("Style-proof gate is closed.");
  }
  const updated = await processAsset(manifest, {
    ...asset,
    status: "pending",
    failure_reason: null,
  });
  await createContactSheet(updated.batch);
  if (updated.batch === "style-proof") updateStyleGate(manifest);
  writeReports(manifest);
}

async function ingest() {
  const assetId = readOption("asset");
  const input = readOption("file");
  const reviewPath = readOption("review");
  if (!assetId || !input || !reviewPath) {
    throw new Error(
      "Usage: pnpm assets:ingest --asset=<id> --file=<image> --review=<json>",
    );
  }
  const manifest = currentManifest();
  const asset = manifest.assets.find(
    (candidate) => candidate.asset_id === assetId,
  );
  if (!asset) throw new Error(`Unknown asset '${assetId}'.`);
  const absoluteInput = resolve(ROOT, input);
  const absoluteReview = resolve(ROOT, reviewPath);
  if (!existsSync(absoluteInput))
    throw new Error(`Input asset not found: ${absoluteInput}`);
  if (!existsSync(absoluteReview))
    throw new Error(`Review JSON not found: ${absoluteReview}`);
  const review = readJson(absoluteReview, {});
  const isGeodata = asset.source_type === "svg-geodata";
  const requiredScores = isGeodata
    ? [
        "geographic_fidelity",
        "geometry_quality",
        "composition",
        "small_size_legibility",
        "contrast",
        "ui_suitability",
        "mobile_suitability",
        "originality",
        "technical_quality",
        "safety_compliance",
      ]
    : [
        "realism",
        "style_consistency",
        "composition",
        "material_quality",
        "lighting_quality",
        "architecture_plausibility",
        "ui_suitability",
        "mobile_suitability",
        "originality",
        "safety_compliance",
      ];
  for (const key of requiredScores) {
    if (!Number.isFinite(review[key]) || review[key] < 0 || review[key] > 100) {
      throw new Error(`Review score '${key}' must be a number from 0 to 100.`);
    }
  }
  const overall =
    requiredScores.reduce((sum, key) => sum + Number(review[key]), 0) /
    requiredScores.length;
  const approved =
    overall >= 85 &&
    review.safety_compliance === 100 &&
    review.ui_suitability >= 80 &&
    review.originality >= 85;
  const savedPromptPath = writePrompt(asset);
  if (isGeodata && review.process_documentation) {
    atomicWrite(
      savedPromptPath,
      `${promptFor(asset)}\n\nLicensed geodata derivation:\n${review.process_documentation}\n`,
    );
  } else if (review.accepted_prompt) {
    const references = (review.reference_images ?? [])
      .map((path) => `- ${path}`)
      .join("\n");
    atomicWrite(
      savedPromptPath,
      `${promptFor(asset)}\n\nAccepted generation prompt:\n${review.accepted_prompt}\n${
        references ? `\nStyle-reference images:\n${references}\n` : ""
      }`,
    );
  } else if (review.revision_prompt) {
    atomicWrite(
      savedPromptPath,
      `${promptFor(asset)}\n\nRevision used for the accepted image:\n${review.revision_prompt}\n`,
    );
  }
  if (isGeodata) {
    if (extname(absoluteInput).toLowerCase() !== ".svg") {
      throw new Error("Licensed geodata assets must be ingested as SVG.");
    }
    const sourcePath = join(sourceDirectoryFor(asset), `${asset.asset_id}.svg`);
    const productionPath = join(
      ASSETS,
      "production",
      "svg",
      `${asset.asset_id}.svg`,
    );
    copyFileSync(absoluteInput, sourcePath);
    copyFileSync(sourcePath, productionPath);
    const validation = validateSvg(productionPath, asset);
    const qualityStatus =
      approved && validation.ok ? "approved" : "review_required";
    const updated = await completeAsset(asset, {
      providerName: "bkg-wfs",
      sourcePath,
      productionFiles: [productionPath],
      validation,
      sourceType: "svg-geodata",
      qualityStatus,
      qualityScore: Number(overall.toFixed(1)),
      reviewStatus:
        qualityStatus === "approved"
          ? "codex-geodata-approved"
          : "review-required",
      notes: review.notes ?? [],
      visualReview: review,
      license: review.license ?? "dl-de/by-2-0",
      provenance: review.provenance ?? null,
    });
    setAsset(manifest, updated);
    await createContactSheet(asset.batch);
    writeReports(manifest);
    console.log(`${updated.status}: ingested ${asset.asset_id}`);
    return;
  }
  const sourcePath = join(sourceDirectoryFor(asset), `${asset.asset_id}.png`);
  await sharp(absoluteInput, { failOn: "error" })
    .rotate()
    .resize({
      width: asset.width,
      height: asset.height,
      fit: "cover",
      position: "centre",
    })
    .flatten(
      asset.transparent_background ? undefined : { background: "#080a0d" },
    )
    .withMetadata({ icc: "srgb" })
    .png({ compressionLevel: 9 })
    .toFile(sourcePath);
  const variants = await optimizeRaster(asset, sourcePath);
  const validation = await validateRaster(sourcePath, asset);
  const qualityStatus =
    approved && validation.ok ? "approved" : "review_required";
  const updated = await completeAsset(asset, {
    providerName: "codex-built-in",
    sourcePath,
    productionFiles: variants,
    validation,
    sourceType: "generated",
    qualityStatus,
    qualityScore: Number(overall.toFixed(1)),
    reviewStatus:
      qualityStatus === "approved"
        ? "codex-visual-approved"
        : "review-required",
    notes: review.notes ?? [],
    visualReview: review,
  });
  setAsset(manifest, updated);
  await createContactSheet(asset.batch);
  if (asset.batch === "style-proof") updateStyleGate(manifest);
  writeReports(manifest);
  console.log(`${updated.status}: ingested ${asset.asset_id}`);
}

function validateScores(scores, keys) {
  for (const key of keys) {
    if (!Number.isFinite(scores[key]) || scores[key] < 0 || scores[key] > 100) {
      throw new Error(`Review score '${key}' must be a number from 0 to 100.`);
    }
  }
}

async function applyBatchReview() {
  const reviewPath = readOption("review");
  if (!reviewPath) throw new Error("Missing --review=<batch-review.json>.");
  const absoluteReview = resolve(ROOT, reviewPath);
  if (!existsSync(absoluteReview))
    throw new Error(`Review JSON not found: ${absoluteReview}`);
  const review = readJson(absoluteReview, {});
  const keys = [
    "style_consistency",
    "composition",
    "small_size_legibility",
    "contrast",
    "geometry_quality",
    "ui_suitability",
    "mobile_suitability",
    "originality",
    "technical_quality",
    "safety_compliance",
  ];
  if (!review.batch || !review.scores) {
    throw new Error("Batch review requires 'batch' and base 'scores'.");
  }
  const manifest = currentManifest();
  const assets = manifest.assets.filter(
    (asset) => asset.batch === review.batch,
  );
  if (assets.length === 0)
    throw new Error(`Unknown or empty batch '${review.batch}'.`);
  for (const asset of assets) {
    const metadataPath = join(ASSETS, "metadata", `${asset.asset_id}.json`);
    if (!existsSync(metadataPath)) {
      throw new Error(`Cannot review ${asset.asset_id}: metadata is missing.`);
    }
    const override = review.assets?.[asset.asset_id] ?? {};
    const scores = { ...review.scores, ...(override.scores ?? {}) };
    validateScores(scores, keys);
    const overall =
      keys.reduce((sum, key) => sum + scores[key], 0) / keys.length;
    const approved =
      overall >= 85 &&
      scores.safety_compliance === 100 &&
      scores.ui_suitability >= 80 &&
      scores.originality >= 85 &&
      scores.small_size_legibility >= 80;
    const metadata = readJson(metadataPath, {});
    metadata.quality_score = Number(overall.toFixed(1));
    metadata.quality_status = approved ? "approved" : "review_required";
    metadata.review_status = approved
      ? "codex-visual-approved"
      : "review-required";
    metadata.visual_review = {
      schema: review.schema ?? "vector-branding-v1",
      reviewer: review.reviewer ?? "codex-visual",
      reviewed_at: review.reviewed_at ?? now(),
      scores,
      notes: [...(review.notes ?? []), ...(override.notes ?? [])],
    };
    writeJson(metadataPath, metadata);
    const index = manifest.assets.findIndex(
      (candidate) => candidate.asset_id === asset.asset_id,
    );
    manifest.assets[index] = {
      ...asset,
      status: approved ? "approved" : "review_required",
      failure_reason: approved
        ? null
        : "Visual batch review did not meet approval thresholds.",
    };
  }
  writeJson(MANIFEST_PATH, manifest);
  syncState(manifest);
  await createContactSheet(review.batch);
  writeReports(manifest);
  console.log(
    `Visual review applied to ${assets.length} assets in batch '${review.batch}'.`,
  );
}

async function createContactSheet(batch) {
  const manifest = currentManifest();
  const assets = manifest.assets.filter(
    (asset) =>
      asset.batch === batch &&
      ["approved", "review_required"].includes(asset.status) &&
      existsSync(join(ASSETS, "metadata", `${asset.asset_id}.json`)),
  );
  if (assets.length === 0) return null;
  const cellWidth = 480;
  const cellHeight = 300;
  const columns = Math.min(3, assets.length);
  const rows = Math.ceil(assets.length / columns);
  const composites = [];
  for (let index = 0; index < assets.length; index += 1) {
    const metadata = readJson(
      join(ASSETS, "metadata", `${assets[index].asset_id}.json`),
      {},
    );
    const path = join(ROOT, metadata.source_file);
    if (!existsSync(path)) continue;
    const previewBackground =
      assets[index].asset_id.includes("-black") ||
      assets[index].asset_id.includes("monochrome")
        ? "#f3f0e8"
        : "#080a0d";
    const buffer = await sharp(path)
      .resize({
        width: cellWidth,
        height: cellHeight,
        fit: "contain",
        position: "centre",
        background: previewBackground,
      })
      .flatten({ background: previewBackground })
      .png()
      .toBuffer();
    composites.push({
      input: buffer,
      left: (index % columns) * cellWidth,
      top: Math.floor(index / columns) * cellHeight,
    });
  }
  const output =
    batch === "style-proof"
      ? join(ASSETS, "reports", "style-reference-contact-sheet.png")
      : join(ASSETS, "reports", "contact-sheets", `${batch}.png`);
  await sharp({
    create: {
      width: columns * cellWidth,
      height: rows * cellHeight,
      channels: 3,
      background: "#080a0d",
    },
  })
    .composite(composites)
    .png({ compressionLevel: 9 })
    .toFile(output);
  console.log(`Contact sheet written: ${relative(output)}`);
  return output;
}

async function createAllContactSheets() {
  for (const { id } of catalogBatches) await createContactSheet(id);
}

async function validateProcessed() {
  const manifest = currentManifest();
  const findings = [];
  for (const asset of manifest.assets.filter(
    (candidate) => candidate.status !== "pending",
  )) {
    const metadataPath = join(ASSETS, "metadata", `${asset.asset_id}.json`);
    if (!existsSync(metadataPath)) {
      findings.push({
        asset_id: asset.asset_id,
        severity: "error",
        message: "Missing metadata.",
      });
      continue;
    }
    const metadata = readJson(metadataPath, {});
    const sourcePath = join(ROOT, metadata.source_file ?? "");
    if (!existsSync(sourcePath)) {
      findings.push({
        asset_id: asset.asset_id,
        severity: "error",
        message: "Missing source.",
      });
      continue;
    }
    const result =
      extname(sourcePath).toLowerCase() === ".svg"
        ? validateSvg(sourcePath, asset)
        : await validateRaster(sourcePath, asset);
    for (const issue of result.issues) {
      findings.push({
        asset_id: asset.asset_id,
        severity: "error",
        message: issue,
      });
    }
    for (const production of metadata.production_files ?? []) {
      if (!existsSync(join(ROOT, production.path))) {
        findings.push({
          asset_id: asset.asset_id,
          severity: "error",
          message: `Missing production variant: ${production.path}`,
        });
      }
    }
    for (const runtime of metadata.runtime_files ?? []) {
      const runtimePath = join(ROOT, runtime.path);
      if (!existsSync(runtimePath)) {
        findings.push({
          asset_id: asset.asset_id,
          severity: "error",
          message: `Missing runtime integration: ${runtime.path}`,
        });
        continue;
      }
      if (sha256(runtimePath) !== runtime.sha256) {
        findings.push({
          asset_id: asset.asset_id,
          severity: "error",
          message: `Runtime content hash changed: ${runtime.path}`,
        });
      }
      if (extname(runtimePath).toLowerCase() === ".png") {
        const runtimeMetadata = await sharp(runtimePath, {
          failOn: "error",
        }).metadata();
        const runtimeStats = await sharp(runtimePath, {
          failOn: "error",
        }).stats();
        const requirements = {
          "branding-shadowgrid-app-icon-master-v1": {
            width: 1024,
            height: 1024,
            opaque: true,
          },
          "branding-shadowgrid-android-adaptive-foreground-v1": {
            width: 1024,
            height: 1024,
            opaque: false,
          },
          "branding-shadowgrid-favicon-v1": {
            width: 64,
            height: 64,
            opaque: false,
          },
        }[asset.asset_id];
        if (
          requirements &&
          (runtimeMetadata.width !== requirements.width ||
            runtimeMetadata.height !== requirements.height ||
            runtimeStats.isOpaque !== requirements.opaque)
        ) {
          findings.push({
            asset_id: asset.asset_id,
            severity: "error",
            message: `Runtime PNG requirements failed for ${runtime.path}.`,
          });
        }
      }
    }
  }
  writeJson(join(ASSETS, "reports", "asset-validation.json"), {
    project: "shadowgrid",
    checked_at: now(),
    processed_assets: manifest.assets.filter(
      (asset) => asset.status !== "pending",
    ).length,
    findings,
    passed: findings.length === 0,
  });
  console.log(
    findings.length === 0
      ? "Processed asset validation passed."
      : `Processed asset validation found ${findings.length} issue(s).`,
  );
  if (findings.length > 0) process.exitCode = 1;
}

async function optimizeExisting() {
  const manifest = currentManifest();
  for (const asset of manifest.assets.filter((candidate) =>
    ["approved", "review_required"].includes(candidate.status),
  )) {
    const metadataPath = join(ASSETS, "metadata", `${asset.asset_id}.json`);
    if (!existsSync(metadataPath)) continue;
    const metadata = readJson(metadataPath, {});
    const sourcePath = join(ROOT, metadata.source_file);
    if (extname(sourcePath).toLowerCase() === ".svg") continue;
    const files = await optimizeRaster(asset, sourcePath);
    metadata.production_files = files.map((path) => ({
      path: relative(path),
      bytes: statSync(path).size,
      sha256: sha256(path),
    }));
    writeJson(metadataPath, metadata);
  }
  console.log("Responsive production variants refreshed.");
}

function syncRuntimeAssets() {
  const manifest = currentManifest();
  let syncedAssets = 0;
  let syncedFiles = 0;
  for (const asset of manifest.assets.filter(
    (candidate) => candidate.status === "approved",
  )) {
    const metadataPath = join(ASSETS, "metadata", `${asset.asset_id}.json`);
    if (!existsSync(metadataPath)) continue;
    const metadata = readJson(metadataPath, {});
    const productionFiles = (metadata.production_files ?? [])
      .map((file) => join(ROOT, file.path))
      .filter((path) => existsSync(path));
    const runtimeFiles = integrateRuntimeAsset(asset, productionFiles);
    metadata.runtime_files = runtimeFiles.map((path) => ({
      path: relative(path),
      bytes: statSync(path).size,
      sha256: sha256(path),
    }));
    writeJson(metadataPath, metadata);
    if (runtimeFiles.length > 0) {
      syncedAssets += 1;
      syncedFiles += runtimeFiles.length;
    }
  }
  writeReports(manifest);
  console.log(
    `Runtime assets synchronized: ${syncedAssets} assets, ${syncedFiles} files.`,
  );
}

function writeReports(manifest = currentManifest()) {
  const metadata = manifest.assets
    .map((asset) =>
      readJson(join(ASSETS, "metadata", `${asset.asset_id}.json`), null),
    )
    .filter(Boolean);
  const costs = readJson(COST_PATH, { total_spent_eur: 0 });
  const totalBytes = metadata
    .flatMap((entry) => entry.production_files ?? [])
    .reduce((sum, file) => sum + Number(file.bytes || 0), 0);
  const counts = Object.fromEntries(
    ["pending", "approved", "review_required", "rejected", "failed"].map(
      (status) => [
        status,
        manifest.assets.filter((asset) => asset.status === status).length,
      ],
    ),
  );
  const byCategory = Object.fromEntries(
    [...new Set(manifest.assets.map((asset) => asset.category))]
      .sort()
      .map((category) => [
        category,
        manifest.assets.filter((asset) => asset.category === category).length,
      ]),
  );
  const byCity = Object.fromEntries(
    [...new Set(manifest.assets.map((asset) => asset.city).filter(Boolean))]
      .sort()
      .map((city) => [
        city,
        manifest.assets.filter((asset) => asset.city === city).length,
      ]),
  );
  const manifestReport = `# Asset manifest report

- Manifest version: ${manifest.version}
- Entries: ${manifest.assets.length}
- Unique IDs: ${new Set(manifest.assets.map((asset) => asset.asset_id)).size}
- Unique order values: ${new Set(manifest.assets.map((asset) => asset.order)).size}
- Required entries: ${manifest.assets.filter((asset) => asset.required).length}
`;
  const styleReport = `# Style consistency report

- Style version: ${styleVersion}
- Style lock: ${readJson(STYLE_LOCK_PATH, styleLock).status}
- Style-proof approved: ${manifest.assets.filter((asset) => asset.batch === "style-proof" && asset.status === "approved").length}/5
- Contact sheet: \`assets/reports/style-reference-contact-sheet.png\`
`;
  const qualityReport = `# Image quality report

- Approved: ${counts.approved}
- Review required: ${counts.review_required}
- Rejected: ${counts.rejected}
- Failed: ${counts.failed}
- Pending: ${counts.pending}

Quality approval requires overall ≥ 85, UI suitability ≥ 80, originality ≥ 85 and safety compliance = 100. Procedural provider-disabled scene fallbacks remain review-required and are never described as photorealistic generated imagery.
`;
  const safetyReport = `# Image safety report

All prompts prohibit real criminal groups, extremist symbols, real authority or company branding, readable private addresses or plates, identifiable private people, graphic violence, weapon focus and operational wrongdoing instructions.

- Metadata moderation approved: ${metadata.filter((entry) => entry.moderation_status === "approved").length}
- Rejected assets excluded from production: ${counts.rejected}
`;
  const licenseReport = `# Asset license report

- Project-owned generated/procedural assets with metadata: ${metadata.filter((entry) => entry.license === "project-owned-generated-asset").length}
- Licensed geographic inputs still required: ${manifest.assets.filter((asset) => asset.source_type === "svg-geodata" && asset.status !== "approved").length}
- Real app screenshots still required: ${manifest.assets.filter((asset) => asset.source_type === "app-screenshot" && asset.status !== "approved").length}
`;
  const performanceReport = `# Asset performance report

- Current production storage: ${(totalBytes / 1024 / 1024).toFixed(2)} MiB
- Production files: ${metadata.flatMap((entry) => entry.production_files ?? []).length}
- Raster masters with AVIF and WebP variants: ${metadata.filter((entry) => (entry.production_files ?? []).some((file) => file.path.endsWith(".avif")) && (entry.production_files ?? []).some((file) => file.path.endsWith(".webp"))).length}
`;
  const cropReport = `# Mobile crop report

- Assets with focal points: ${metadata.filter((entry) => entry.focal_point).length}
- Assets with safe areas: ${metadata.filter((entry) => entry.safe_area).length}
- Important pending assets without reviewed mobile crops: ${manifest.assets.filter((asset) => asset.required && asset.status !== "approved").length}
`;
  const integrationReport = `# Asset integration report

- Processed assets with source files: ${metadata.filter((entry) => existsSync(join(ROOT, entry.source_file))).length}
- Processed assets with production variants: ${metadata.filter((entry) => (entry.production_files ?? []).length > 0).length}
- Runtime-integrated assets: ${metadata.filter((entry) => (entry.runtime_files ?? []).length > 0).length}
- Rejected asset references permitted: 0
- Store screenshots are gated on functioning application captures and are not generated as mock interfaces.
`;
  const costReport = `# Asset generation cost report

- Provider configuration: \`${provider}\`
- Daily budget: €${dailyBudget.toFixed(2)}
- Total budget: €${totalBudget.toFixed(2)}
- Recorded spend: €${Number(costs.total_spent_eur || 0).toFixed(4)}
- Cost entries: ${(costs.entries ?? []).length}

No provider credentials are persisted in repository files, metadata, prompts or logs.
`;
  const coverage = `# Final asset coverage

- Total: ${manifest.assets.length}
- Generated or processed: ${metadata.length}
- Procedurally produced: ${metadata.filter((entry) => String(entry.source_type).includes("procedural")).length}
- Approved: ${counts.approved}
- Review required: ${counts.review_required}
- Rejected: ${counts.rejected}
- Missing/pending: ${counts.pending}
- Failed: ${counts.failed}
- Recorded cost: €${Number(costs.total_spent_eur || 0).toFixed(4)}
- Production storage: ${(totalBytes / 1024 / 1024).toFixed(2)} MiB
- Assets without metadata: ${manifest.assets.length - metadata.length}
- Assets without a valid license field: ${metadata.filter((entry) => !entry.license).length}

## Assets per category

\`\`\`json
${JSON.stringify(byCategory, null, 2)}
\`\`\`

## Assets per city

\`\`\`json
${JSON.stringify(byCity, null, 2)}
\`\`\`

This report is intentionally named as specified by the master goal, but the library is not complete while pending, review-required, rejected or failed counts are non-zero.
`;
  const reports = {
    "ASSET_MANIFEST_REPORT.md": manifestReport,
    "STYLE_CONSISTENCY_REPORT.md": styleReport,
    "IMAGE_QUALITY_REPORT.md": qualityReport,
    "IMAGE_SAFETY_REPORT.md": safetyReport,
    "ASSET_LICENSE_REPORT.md": licenseReport,
    "ASSET_PERFORMANCE_REPORT.md": performanceReport,
    "MOBILE_CROP_REPORT.md": cropReport,
    "ASSET_INTEGRATION_REPORT.md": integrationReport,
    "ASSET_GENERATION_COST_REPORT.md": costReport,
    "FINAL_ASSET_COVERAGE.md": coverage,
  };
  for (const [name, content] of Object.entries(reports)) {
    atomicWrite(join(ASSETS, "reports", name), `${content.trim()}\n`);
  }
  syncState(manifest);
  console.log("Asset reports refreshed.");
}

async function integrationTest() {
  const manifest = currentManifest();
  const forbiddenProduction = manifest.assets
    .filter((asset) => asset.status === "rejected")
    .flatMap((asset) => {
      const metadata = readJson(
        join(ASSETS, "metadata", `${asset.asset_id}.json`),
        {},
      );
      return metadata.production_files ?? [];
    });
  if (forbiddenProduction.length > 0) {
    throw new Error(
      "Rejected assets are still referenced by production metadata.",
    );
  }
  await validateProcessed();
  writeReports(manifest);
  console.log("Asset integration checks completed.");
}

async function main() {
  if (!allowedProviders.has(provider)) {
    throw new Error(
      `Unsupported IMAGE_GENERATION_PROVIDER '${provider}'. Expected disabled, openai, local_comfyui or custom_http.`,
    );
  }
  ensureDirectories();
  const command = process.argv[2] ?? "report";
  switch (command) {
    case "manifest":
      createManifest();
      writeReports();
      break;
    case "style-proof":
      await runStyleProof();
      break;
    case "next":
    case "resume":
      await runNext();
      break;
    case "batch":
      await runBatch();
      break;
    case "city":
      await runCity();
      break;
    case "all":
      await runAll();
      break;
    case "validate":
      await validateProcessed();
      break;
    case "optimize":
      await optimizeExisting();
      writeReports();
      break;
    case "runtime-sync":
      syncRuntimeAssets();
      break;
    case "contact-sheets":
      await createAllContactSheets();
      break;
    case "integration-test":
      await integrationTest();
      break;
    case "report":
      writeReports();
      break;
    case "ingest":
      await ingest();
      break;
    case "regenerate":
      await regenerate();
      break;
    case "review":
      await applyBatchReview();
      break;
    default:
      throw new Error(`Unknown asset command '${command}'.`);
  }
}

main().catch((error) => {
  console.error(`Asset pipeline failed: ${error.message}`);
  process.exitCode = 1;
});

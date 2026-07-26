const STYLE_VERSION = "1.0.0";
const PROMPT_VERSION = "1.0.0";

const slugify = (value) =>
  value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/&/g, "and")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");

const dimensions = {
  "21:9": [2688, 1152],
  "16:9": [2048, 1152],
  "9:16": [1152, 2048],
  "16:5": [3200, 1000],
  "4:5": [1280, 1600],
  "3:2": [1800, 1200],
  "1:1": [1536, 1536],
  "24:24": [24, 24],
};

const batches = [
  { id: "style-proof", priority: 1 },
  { id: "branding", priority: 1 },
  { id: "global-backgrounds", priority: 1 },
  { id: "germany-map", priority: 1 },
  { id: "map-markers", priority: 2 },
  { id: "premium-cities", priority: 1 },
  { id: "procedural-city-templates", priority: 2 },
  { id: "districts", priority: 2 },
  { id: "businesses", priority: 2 },
  { id: "facilities", priority: 2 },
  { id: "specialists", priority: 2 },
  { id: "pvp", priority: 2 },
  { id: "cartel-conflicts", priority: 2 },
  { id: "cartel-crests", priority: 2 },
  { id: "world-events", priority: 2 },
  { id: "tutorial", priority: 2 },
  { id: "ui-icons", priority: 1 },
  { id: "weather-overlays", priority: 2 },
  { id: "rankings-rewards", priority: 2 },
  { id: "mobile", priority: 1 },
  { id: "store-marketing", priority: 3 },
];

const entries = [];

function add({
  batch,
  category,
  name,
  title,
  ratio = "16:9",
  transparent = false,
  sourceType = "generated",
  template,
  city,
  variant,
  gameplayState = "normal",
  required = true,
  notes,
}) {
  const [width, height] = dimensions[ratio];
  const batchInfo = batches.find((candidate) => candidate.id === batch);
  const order = entries.length + 1;
  entries.push({
    order,
    asset_id: `${category}-${slugify(name)}-v1`,
    batch,
    category,
    title,
    source_type: sourceType,
    required,
    priority: batchInfo.priority,
    width,
    height,
    aspect_ratio: ratio,
    transparent_background: transparent,
    prompt_template: template ?? category,
    prompt_version: PROMPT_VERSION,
    style_version: STYLE_VERSION,
    seed: 100000 + order,
    variants: [],
    status: "pending",
    ...(city ? { city } : {}),
    ...(variant ? { variant } : {}),
    gameplay_state: gameplayState,
    ...(notes ? { notes } : {}),
  });
}

const styleProofs = [
  ["urban-control-center-day", "SHADOWGRID urban control center, day", "day"],
  ["urban-control-center-night", "SHADOWGRID urban control center, night", "night"],
  ["german-metropolis-day", "Contemporary German metropolis, day", "day"],
  ["german-metropolis-night", "Contemporary German metropolis, night", "night"],
  [
    "corporate-headquarters",
    "Ultra-realistic contemporary corporate headquarters",
    "blue-hour",
  ],
];
for (const [name, title, variant] of styleProofs) {
  add({
    batch: "style-proof",
    category: "style-proof",
    name,
    title,
    ratio: "16:9",
    template: "style-proof",
    variant,
  });
}

const branding = [
  ["shadowgrid-logo-horizontal-dark", "Main horizontal logo, dark background", "16:5", false],
  ["shadowgrid-logo-horizontal-light", "Main horizontal logo, light background", "16:5", false],
  ["shadowgrid-logo-vertical-dark", "Main vertical logo, dark background", "1:1", false],
  ["shadowgrid-logo-vertical-light", "Main vertical logo, light background", "1:1", false],
  ["shadowgrid-symbol-gold", "Gold symbol", "1:1", true],
  ["shadowgrid-symbol-white", "White symbol", "1:1", true],
  ["shadowgrid-symbol-black", "Black symbol", "1:1", true],
  ["shadowgrid-symbol-monochrome", "Simplified monochrome symbol", "1:1", true],
  ["shadowgrid-wordmark-horizontal", "Horizontal wordmark", "16:5", true],
  ["shadowgrid-wordmark-compact", "Compact wordmark", "1:1", true],
  ["shadowgrid-app-icon-master", "App icon master", "1:1", false],
  ["shadowgrid-android-adaptive-foreground", "Android adaptive icon foreground", "1:1", true],
  ["shadowgrid-android-adaptive-background", "Android adaptive icon background", "1:1", false],
  ["shadowgrid-favicon", "Favicon symbol", "1:1", true],
];
for (const [name, title, ratio, transparent] of branding) {
  add({
    batch: "branding",
    category: "branding",
    name,
    title,
    ratio,
    transparent,
    sourceType: "procedural",
    template: "branding-logo",
  });
}

const globalBackgrounds = [
  ["landing-desktop-day", "Landing page desktop, day", "21:9"],
  ["landing-desktop-night", "Landing page desktop, night", "21:9"],
  ["landing-mobile-day", "Landing page mobile, day", "9:16"],
  ["landing-mobile-night", "Landing page mobile, night", "9:16"],
  ["login-desktop", "Login desktop background", "16:9"],
  ["login-mobile", "Login mobile background", "9:16"],
  ["registration-desktop", "Registration desktop background", "16:9"],
  ["registration-mobile", "Registration mobile background", "9:16"],
  ["world-selection-desktop", "Game world selection desktop", "16:9"],
  ["world-selection-mobile", "Game world selection mobile", "9:16"],
  ["command-center-day", "Global command center, day", "16:9"],
  ["command-center-night", "Global command center, night", "16:9"],
  ["germany-map-atmosphere", "Atmospheric Germany map background", "16:9"],
  ["season-complete", "Season completion background", "16:9"],
  ["maintenance", "Maintenance mode background", "16:9"],
  ["offline", "Offline mode background", "16:9"],
];
for (const [name, title, ratio] of globalBackgrounds) {
  add({ batch: "global-backgrounds", category: "global", name, title, ratio });
}

const mapLayers = [
  ["germany-outline", "Germany outline", "svg-geodata"],
  ["federal-state-borders", "Federal state borders", "svg-geodata"],
  ["coasts-water", "Coast and water layer", "svg-geodata"],
  ["major-rivers", "Simplified major rivers", "svg-geodata"],
  ["map-background-day", "Map background, day", "procedural"],
  ["map-background-night", "Map background, night", "procedural"],
  ["map-background-neutral", "Neutral map layer", "procedural"],
  ["heatmap-economy-legend", "Economy heatmap legend", "procedural"],
  ["heatmap-information-legend", "Information heatmap legend", "procedural"],
  ["heatmap-authority-legend", "Authority activity heatmap legend", "procedural"],
  ["heatmap-organization-legend", "Organization presence heatmap legend", "procedural"],
  ["heatmap-event-legend", "Event heatmap legend", "procedural"],
];
for (const [name, title, sourceType] of mapLayers) {
  add({
    batch: "germany-map",
    category: "map",
    name,
    title,
    ratio: sourceType === "svg-geodata" ? "1:1" : "16:9",
    transparent: sourceType === "svg-geodata",
    sourceType,
    notes:
      sourceType === "svg-geodata"
        ? "Must be derived from a documented licensed geographic source; never generated by image AI."
        : undefined,
  });
}

const mapMarkers = [
  "metropolis",
  "large-city",
  "medium-city",
  "small-town",
  "home-city",
  "cartel-headquarters",
  "contested-city",
  "seasonal-event",
  "influence-economy",
  "influence-street",
  "influence-information",
  "influence-society",
  "influence-digital",
  "control-economic-network",
  "control-information-center",
  "control-logistics-node",
  "control-social-access",
  "control-digital-node",
  "control-coordination-center",
];
for (const name of mapMarkers) {
  add({
    batch: "map-markers",
    category: "marker",
    name,
    title: `Map marker: ${name.replaceAll("-", " ")}`,
    ratio: "24:24",
    transparent: true,
    sourceType: "procedural",
  });
}

const cities = [
  ["koeln", "Köln", "North Rhine-Westphalia"],
  ["hamburg", "Hamburg", "Hamburg"],
  ["berlin", "Berlin", "Berlin"],
  ["muenchen", "München", "Bavaria"],
  ["frankfurt-am-main", "Frankfurt am Main", "Hesse"],
  ["duesseldorf", "Düsseldorf", "North Rhine-Westphalia"],
  ["stuttgart", "Stuttgart", "Baden-Württemberg"],
  ["leipzig", "Leipzig", "Saxony"],
  ["dortmund", "Dortmund", "North Rhine-Westphalia"],
  ["essen", "Essen", "North Rhine-Westphalia"],
  ["bremen", "Bremen", "Bremen"],
  ["dresden", "Dresden", "Saxony"],
  ["hannover", "Hannover", "Lower Saxony"],
  ["nuernberg", "Nürnberg", "Bavaria"],
  ["duisburg", "Duisburg", "North Rhine-Westphalia"],
  ["bochum", "Bochum", "North Rhine-Westphalia"],
  ["wuppertal", "Wuppertal", "North Rhine-Westphalia"],
  ["bielefeld", "Bielefeld", "North Rhine-Westphalia"],
  ["bonn", "Bonn", "North Rhine-Westphalia"],
  ["muenster", "Münster", "North Rhine-Westphalia"],
  ["aachen", "Aachen", "North Rhine-Westphalia"],
  ["mannheim", "Mannheim", "Baden-Württemberg"],
  ["karlsruhe", "Karlsruhe", "Baden-Württemberg"],
  ["augsburg", "Augsburg", "Bavaria"],
  ["wiesbaden", "Wiesbaden", "Hesse"],
  ["moenchengladbach", "Mönchengladbach", "North Rhine-Westphalia"],
  ["gelsenkirchen", "Gelsenkirchen", "North Rhine-Westphalia"],
  ["braunschweig", "Braunschweig", "Lower Saxony"],
  ["kiel", "Kiel", "Schleswig-Holstein"],
  ["chemnitz", "Chemnitz", "Saxony"],
];
const cityVariants = [
  ["ultrawide-day", "Ultra-wide hero, day", "21:9", "day"],
  ["ultrawide-night", "Ultra-wide hero, night", "21:9", "night"],
  ["desktop-day", "Desktop hero, day", "16:9", "day"],
  ["desktop-night", "Desktop hero, night", "16:9", "night"],
  ["mobile-day", "Mobile hero, day", "9:16", "day"],
  ["mobile-night", "Mobile hero, night", "9:16", "night"],
  ["card", "Square city card", "1:1", "day"],
  ["silhouette", "Stylized city silhouette", "16:5", "neutral"],
];
for (const [city, cityName, state] of cities) {
  for (const [variant, variantTitle, ratio, time] of cityVariants) {
    add({
      batch: "premium-cities",
      category: "city",
      name: `${city}-${variant}`,
      title: `${cityName}, ${state}: ${variantTitle}`,
      ratio,
      transparent: variant === "silhouette",
      sourceType: variant === "silhouette" ? "procedural" : "generated",
      template: "city-hero",
      city,
      variant,
      notes: `Contemporary, fictionalized representation of ${cityName}; no exact landmark photograph recreation; time=${time}.`,
    });
  }
}

const cityTemplates = [
  "metropolis-river",
  "metropolis-inland",
  "metropolis-port",
  "large-city-industrial",
  "large-city-technology",
  "large-city-administration",
  "medium-city-historic-center",
  "medium-city-industry-commerce",
  "medium-city-university",
  "small-town-rural",
  "small-town-river-lake",
  "small-town-commerce-commuter",
];
for (const template of cityTemplates) {
  for (const [variant, ratio] of [
    ["day-desktop", "16:9"],
    ["night-desktop", "16:9"],
    ["day-mobile", "9:16"],
    ["night-mobile", "9:16"],
    ["square", "1:1"],
  ]) {
    add({
      batch: "procedural-city-templates",
      category: "city-template",
      name: `${template}-${variant}`,
      title: `${template.replaceAll("-", " ")}, ${variant.replaceAll("-", " ")}`,
      ratio,
      variant,
    });
  }
}

const districts = [
  "financial-center",
  "harbor-quarter",
  "industrial-belt",
  "old-town",
  "technology-park",
  "administrative-center",
  "nightlife-quarter",
  "university-quarter",
  "logistics-corridor",
  "affluent-residential",
  "dense-mixed-residential",
  "outer-district-commerce-ring",
];
const districtStates = [
  "normal-day",
  "normal-night",
  "economic-boom-day",
  "economic-boom-night",
  "crisis-day",
  "crisis-night",
  "authority-activity-day",
  "authority-activity-night",
];
for (const district of districts) {
  for (const state of districtStates) {
    add({
      batch: "districts",
      category: "district",
      name: `${district}-${state}`,
      title: `${district.replaceAll("-", " ")}, ${state.replaceAll("-", " ")}`,
      gameplayState: state,
    });
  }
}

const businesses = [
  "hospitality",
  "event-agency",
  "security-company",
  "logistics-company",
  "technology-company",
  "property-management",
  "construction-company",
  "media-company",
];
const businessStates = [
  "exterior-level-1",
  "exterior-level-2",
  "exterior-max",
  "management-interior",
  "poor-condition",
  "audited-frozen-closed",
];
for (const business of businesses) {
  for (const state of businessStates) {
    add({
      batch: "businesses",
      category: "business",
      name: `${business}-${state}`,
      title: `${business.replaceAll("-", " ")}, ${state.replaceAll("-", " ")}`,
      gameplayState: state,
    });
  }
}

const facilities = [
  "headquarters",
  "finance-office",
  "information-center",
  "logistics-center",
  "personnel-academy",
  "compliance-office",
];
for (const facility of facilities) {
  for (const state of ["level-1", "level-2", "maximum-level", "disrupted"]) {
    add({
      batch: "facilities",
      category: "facility",
      name: `${facility}-${state}`,
      title: `${facility.replaceAll("-", " ")}, ${state.replaceAll("-", " ")}`,
      gameplayState: state,
    });
  }
}

const specialistRoles = [
  "strategist",
  "finance-lead",
  "district-coordination",
  "information-analysis",
  "negotiation",
  "security-management",
  "personnel-management",
  "technology-expert",
];
for (const role of specialistRoles) {
  for (const presentation of [
    "younger-woman",
    "younger-man",
    "experienced-woman",
    "experienced-man",
  ]) {
    add({
      batch: "specialists",
      category: "character",
      name: `${role}-${presentation}`,
      title: `${role.replaceAll("-", " ")}, ${presentation.replaceAll("-", " ")}`,
      ratio: "4:5",
      template: "specialist-character",
      variant: presentation,
    });
  }
}
for (let index = 1; index <= 16; index += 1) {
  add({
    batch: "specialists",
    category: "avatar",
    name: `boss-player-preset-${String(index).padStart(2, "0")}`,
    title: `Boss and player avatar preset ${index}`,
    ratio: "1:1",
    template: "specialist-character",
  });
}

const pvpTypes = [
  "economic-attack",
  "information-operation",
  "influence-conflict",
  "talent-recruitment",
  "covert-disruption",
];
for (const type of pvpTypes) {
  for (const phase of ["preparation", "success", "failure"]) {
    add({
      batch: "pvp",
      category: "pvp",
      name: `${type}-${phase}`,
      title: `${type.replaceAll("-", " ")}, ${phase}`,
      gameplayState: phase,
      template: "pvp-abstract",
    });
  }
}

for (const name of [
  "tension",
  "ultimatum",
  "preparation",
  "active-conflict",
  "turning-point",
  "ceasefire",
  "aftermath",
  "neutral-territory",
  "contested-territory",
  "controlled-territory",
  "dominant-territory",
  "blocked-territory",
  "alliance-formed",
  "treaty-broken",
  "peace-treaty",
]) {
  add({
    batch: "cartel-conflicts",
    category: "organization-conflict",
    name,
    title: name.replaceAll("-", " "),
    template: "strategic-conflict",
    gameplayState: name,
  });
}

for (const [group, count] of [
  ["shape", 20],
  ["symbol", 40],
  ["pattern", 12],
  ["frame", 12],
]) {
  for (let index = 1; index <= count; index += 1) {
    add({
      batch: "cartel-crests",
      category: "crest",
      name: `${group}-${String(index).padStart(2, "0")}`,
      title: `Neutral crest ${group} ${index}`,
      ratio: "1:1",
      transparent: true,
      sourceType: "procedural",
    });
  }
}
add({
  batch: "cartel-crests",
  category: "crest-test",
  name: "random-combinations-100",
  title: "Accessibility and uniqueness test for 100 randomized crests",
  ratio: "1:1",
  sourceType: "procedural",
});

for (const event of [
  "port-strike",
  "financial-audit",
  "data-leak",
  "economic-crisis",
  "media-campaign",
  "technology-boom",
  "major-inspection",
  "labor-shortage",
  "property-boom",
  "security-crisis",
  "peace-initiative",
  "supply-chain-disruption",
]) {
  add({
    batch: "world-events",
    category: "event",
    name: event,
    title: event.replaceAll("-", " "),
    template: "world-event",
  });
}

for (const tutorial of [
  "germany-map-city-selection",
  "city-profile",
  "first-business",
  "specialists",
  "resources",
  "first-operation",
  "district-control",
  "player-versus-player",
  "organization-membership",
  "organization-conflict-season-goals",
]) {
  add({
    batch: "tutorial",
    category: "tutorial",
    name: tutorial,
    title: `Tutorial: ${tutorial.replaceAll("-", " ")}`,
    template: "tutorial",
  });
}

const iconGroups = {
  navigation: [
    "command",
    "city",
    "germany",
    "network",
    "businesses",
    "specialists",
    "operations",
    "pvp",
    "organization",
    "organization-conflict",
    "territories",
    "alliances",
    "diplomacy",
    "investigations",
    "research",
    "messages",
    "rankings",
    "profile",
    "settings",
    "administration",
  ],
  resource: [
    "cash",
    "capital",
    "influence",
    "information",
    "logistics",
    "personnel",
    "loyalty",
    "legitimacy",
    "fear",
    "investigation-pressure",
    "stress",
    "stability",
    "reputation",
    "market-share",
    "defense",
    "activity",
  ],
  status: [
    "pending",
    "active",
    "completed",
    "failed",
    "blocked",
    "locked",
    "warning",
    "online",
    "offline",
    "boosted",
    "reduced",
  ],
  pvp: pvpTypes,
  diplomacy: [
    "alliance",
    "treaty",
    "ceasefire",
    "negotiation",
    "proposal",
    "accepted",
    "rejected",
    "neutral",
    "contested",
    "controlled",
  ],
  building: [...businesses, ...facilities],
  control: [
    "add",
    "remove",
    "edit",
    "close",
    "menu",
    "search",
    "filter",
    "sort",
    "previous",
    "next",
    "expand",
    "collapse",
    "refresh",
    "download",
    "upload",
    "share",
    "copy",
    "check",
    "alert",
    "help",
  ],
};
for (const [group, names] of Object.entries(iconGroups)) {
  for (const name of names) {
    add({
      batch: "ui-icons",
      category: "icon",
      name: `${group}-${name}`,
      title: `${group} icon: ${name.replaceAll("-", " ")}`,
      ratio: "24:24",
      transparent: true,
      sourceType: "procedural",
      template: "ui-icon",
    });
  }
}

for (const item of [
  "rain",
  "heavy-rain",
  "snow",
  "fog",
  "storm",
  "heat",
  "cloudy-light-filter",
  "economic-boom",
  "crisis",
  "authority-activity",
  "organization-control",
  "contested-district",
  "blocked-territory",
  "dark-glass",
  "brushed-metal",
  "fine-map-grid",
  "document-texture",
  "concrete",
  "asphalt",
  "technical-network",
]) {
  add({
    batch: "weather-overlays",
    category: "overlay",
    name: item,
    title: item.replaceAll("-", " "),
    ratio: "16:9",
    transparent: true,
    sourceType: "procedural",
  });
}

for (const reward of [
  "gold-medal",
  "silver-medal",
  "bronze-medal",
  "strongest-player",
  "strongest-organization",
  "best-economy",
  "best-district-control",
  "best-diplomacy",
  "best-information-network",
  "highest-stability",
  "best-defense",
  "strongest-recovery",
  "most-successful-alliance",
  "top-1",
  "top-10",
  "top-100",
  "city-champion",
  "state-champion",
  "germany-champion",
]) {
  add({
    batch: "rankings-rewards",
    category: "reward",
    name: reward,
    title: reward.replaceAll("-", " "),
    ratio: "1:1",
    transparent: true,
    sourceType: "procedural",
  });
}

for (const mobile of [
  "ios-app-icon",
  "android-app-icon",
  "android-adaptive-foreground",
  "android-adaptive-background",
  "android-monochrome-icon",
  "splash-wide",
  "splash-android",
  "splash-ios",
  "notification-symbol",
  "offline-background",
  "maintenance-background",
  "conflict-room-background",
]) {
  const portrait = /android|ios|offline|maintenance|conflict-room/.test(mobile);
  add({
    batch: "mobile",
    category: "mobile",
    name: mobile,
    title: mobile.replaceAll("-", " "),
    ratio: /icon|symbol/.test(mobile) ? "1:1" : portrait ? "9:16" : "16:9",
    transparent: /foreground|monochrome|notification/.test(mobile),
    sourceType: /icon|symbol/.test(mobile) ? "procedural" : "generated",
  });
}

const marketing = [
  "google-play-app-icon",
  "google-play-feature-graphic",
  "google-play-city-selection",
  "google-play-dashboard",
  "google-play-city-map",
  "google-play-pvp",
  "google-play-organization",
  "google-play-organization-conflict",
  "google-play-business",
  "google-play-ranking",
  ...Array.from({ length: 8 }, (_, index) => `app-store-iphone-${index + 1}`),
  ...Array.from({ length: 4 }, (_, index) => `app-store-ipad-${index + 1}`),
  "open-graph",
  "community-banner",
  "discord-banner",
  "season-start-banner",
  "season-final-banner",
  "closed-alpha-banner",
  "open-beta-banner",
  "release-banner",
];
for (const item of marketing) {
  const storeScreenshot = /google-play-(?!app-icon|feature)|app-store-/.test(item);
  add({
    batch: "store-marketing",
    category: "marketing",
    name: item,
    title: item.replaceAll("-", " "),
    ratio: item.includes("iphone") ? "9:16" : item.includes("ipad") ? "4:5" : "16:9",
    sourceType: storeScreenshot ? "app-screenshot" : "generated",
    notes: storeScreenshot
      ? "Must be captured from a functioning application; generated or mock user interfaces are forbidden."
      : undefined,
  });
}

export const catalogBatches = batches;
export const catalogEntries = entries;
export const manifestVersion = "1.0.0";
export const promptVersion = PROMPT_VERSION;
export const styleVersion = STYLE_VERSION;

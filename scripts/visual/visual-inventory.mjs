import { readFile, readdir, writeFile } from "node:fs/promises";
import { dirname, extname, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const scriptDirectory = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(scriptDirectory, "../..");
const webSource = resolve(projectRoot, "apps/web/src");
const mobileSource = resolve(projectRoot, "apps/mobile/app");
const outputPath = resolve(
  projectRoot,
  "assets/reports/visual-implementation-inventory.json",
);

async function sourceFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = await Promise.all(
    entries.map(async (entry) => {
      const path = resolve(directory, entry.name);
      if (entry.isDirectory()) return sourceFiles(path);
      if ([".ts", ".tsx"].includes(extname(entry.name))) return [path];
      return [];
    }),
  );
  return files.flat().sort();
}

const webFiles = await sourceFiles(webSource);
const mobileFiles = await sourceFiles(mobileSource);
const appSource = await readFile(resolve(webSource, "App.tsx"), "utf8");

const routeBlocks = [...appSource.matchAll(/<Route\b[\s\S]*?\/>/g)];
const publicPaths = new Set([
  "/",
  "/login",
  "/register",
  "/forgot-password",
  "/verify-email",
  "/reset-password",
]);
const routes = routeBlocks
  .map(([block]) => {
    const path = block.match(/\bpath="([^"]+)"/)?.[1];
    if (!path) return null;
    const components = [...block.matchAll(/<([A-Z][A-Za-z0-9]*)\b/g)]
      .map((match) => match[1])
      .filter((name) => !["Protected", "Navigate", "Route"].includes(name));
    return {
      path,
      component: components.at(-1) ?? null,
      kind: block.includes("<Navigate")
        ? "redirect"
        : path.includes(":") || path.includes("*")
          ? "dynamic"
          : "screen",
      protected: !publicPaths.has(path) && path !== "*",
    };
  })
  .filter(Boolean);

const elementPatterns = {
  html_button: /<button\b/g,
  html_input: /<input\b/g,
  html_select: /<select\b/g,
  html_textarea: /<textarea\b/g,
  html_table: /<table\b/g,
  html_dialog: /<dialog\b/g,
  html_details: /<details\b/g,
  html_svg: /<svg\b/g,
  html_progress: /<progress\b/g,
  rn_pressable: /<Pressable\b/g,
  rn_text_input: /<TextInput\b/g,
  rn_scroll_view: /<ScrollView\b/g,
  rn_flat_list: /<FlatList\b/g,
  rn_modal: /<Modal\b/g,
  rn_image: /<Image\b/g,
  rn_activity_indicator: /<ActivityIndicator\b/g,
};

async function inventoryFile(path, base) {
  const source = await readFile(path, "utf8");
  const exports = [
    ...source.matchAll(
      /export\s+(?:function|const|class)\s+([A-Z][A-Za-z0-9]*)/g,
    ),
  ].map((match) => match[1]);
  const components = [
    ...source.matchAll(
      /(?:export\s+)?(?:function|const|class)\s+([A-Z][A-Za-z0-9]*)/g,
    ),
  ].map((match) => match[1]);
  const classes = new Set();
  for (const match of source.matchAll(/className=(?:"([^"]+)"|`([^`]+)`)/g)) {
    for (const token of (match[1] ?? match[2] ?? "").split(/\s+/)) {
      if (/^[a-z][a-z0-9_-]*$/i.test(token)) classes.add(token);
    }
  }
  const primitives = Object.fromEntries(
    Object.entries(elementPatterns).map(([name, pattern]) => [
      name,
      [...source.matchAll(pattern)].length,
    ]),
  );
  return {
    file: relative(projectRoot, path).replaceAll("\\", "/"),
    exports,
    components: [...new Set(components)].sort(),
    classes: [...classes].sort(),
    primitives,
    total_primitives: Object.values(primitives).reduce(
      (total, value) => total + value,
      0,
    ),
    layer: base === webSource ? "web" : "mobile",
  };
}

const files = await Promise.all([
  ...webFiles.map((path) => inventoryFile(path, webSource)),
  ...mobileFiles.map((path) => inventoryFile(path, mobileSource)),
]);

const mobileRoutes = mobileFiles
  .filter((path) => !path.endsWith("_layout.tsx"))
  .map((path) => {
    const routePath = relative(mobileSource, path)
      .replaceAll("\\", "/")
      .replace(/\.(?:ts|tsx)$/, "")
      .replace(/^\(tabs\)\//, "")
      .replace(/\/index$/, "")
      .replace(/^index$/, "");
    return routePath ? `/${routePath}` : "/";
  })
  .sort();

const reusableComponents = files
  .flatMap((file) =>
    file.exports.map((name) => ({ name, file: file.file, layer: file.layer })),
  )
  .sort((left, right) => left.name.localeCompare(right.name));

const primitiveTotals = Object.fromEntries(
  Object.keys(elementPatterns).map((name) => [
    name,
    files.reduce((total, file) => total + file.primitives[name], 0),
  ]),
);

const inventory = {
  schema_version: 1,
  source_of_truth: {
    web_routes: "apps/web/src/App.tsx",
    web_components: "apps/web/src/**/*.tsx",
    mobile_routes: "apps/mobile/app/**/*.tsx",
  },
  summary: {
    web_route_count: routes.length,
    web_screen_count: routes.filter((route) => route.kind === "screen").length,
    web_dynamic_route_count: routes.filter((route) => route.kind === "dynamic")
      .length,
    web_redirect_count: routes.filter((route) => route.kind === "redirect")
      .length,
    mobile_route_count: mobileRoutes.length,
    exported_component_count: reusableComponents.length,
    component_definition_count: files.reduce(
      (total, file) => total + file.components.length,
      0,
    ),
    files_with_visual_primitives: files.filter(
      (file) => file.total_primitives > 0,
    ).length,
    primitive_totals: primitiveTotals,
  },
  web_routes: routes,
  mobile_routes: mobileRoutes,
  reusable_components: reusableComponents,
  files,
};

await writeFile(outputPath, `${JSON.stringify(inventory, null, 2)}\n`, "utf8");
console.log(
  `Visual inventory written: ${relative(projectRoot, outputPath)} (${routes.length} web routes, ${mobileRoutes.length} mobile routes, ${reusableComponents.length} exports).`,
);

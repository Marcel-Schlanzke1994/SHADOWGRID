import assert from "node:assert/strict";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve } from "node:path";
import test from "node:test";

import {
  checkDocumentationLinks,
  markdownLinkTargets,
} from "./verify-release-materials.mjs";

test("markdownLinkTargets ignores fenced and inline code", () => {
  const markdown = [
    "[valid](docs/guide.md)",
    "![image](images/map.png)",
    "`[ignored](missing.md)`",
    "```text",
    "[ignored too](missing.md)",
    "```",
    "[reference]: docs/reference.md",
  ].join("\n");
  assert.deepEqual(markdownLinkTargets(markdown), [
    "docs/guide.md",
    "images/map.png",
    "docs/reference.md",
  ]);
});

test("documentation check reports only missing local targets", async () => {
  const root = await mkdtemp(resolve(tmpdir(), "shadowgrid-doc-check-"));
  try {
    await mkdir(resolve(root, "docs"));
    await writeFile(
      resolve(root, "README.md"),
      [
        "[guide](docs/guide.md)",
        "[missing](docs/missing.md)",
        "[external](https://example.com/docs)",
      ].join("\n"),
    );
    await writeFile(resolve(root, "docs/guide.md"), "# Guide\n");
    const report = await checkDocumentationLinks(root);
    assert.equal(report.markdown_files, 2);
    assert.equal(report.checked_local_links, 2);
    assert.equal(report.syntactically_checked_external_links, 1);
    assert.deepEqual(report.broken, [
      {
        source: "README.md",
        target: "docs/missing.md",
        reason: "missing_local_target",
      },
    ]);
  } finally {
    await rm(root, { recursive: true, force: true });
  }
});

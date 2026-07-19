import { existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { resolve } from "node:path";
import process from "node:process";

const projectRoot = resolve(import.meta.dirname, "..");
const windowsPython = resolve(projectRoot, ".venv", "Scripts", "python.exe");
const unixPython = resolve(projectRoot, ".venv", "bin", "python");
const python = existsSync(windowsPython)
  ? windowsPython
  : existsSync(unixPython)
    ? unixPython
    : process.platform === "win32"
      ? "python"
      : "python3";

const args = process.argv.slice(2);
let cwd = projectRoot;
if (args[0] === "--cwd") {
  if (!args[1]) throw new Error("--cwd requires a project-relative directory");
  cwd = resolve(projectRoot, args[1]);
  args.splice(0, 2);
}

const result = spawnSync(python, args, {
  cwd,
  env: process.env,
  stdio: "inherit",
  shell: false,
});

if (result.error) throw result.error;
process.exit(result.status ?? 1);

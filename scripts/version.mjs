// Mantiene la misma versión en todos los lugares donde vive.
//
//   pnpm version:set 0.2.0   escribe esa versión en todos los archivos
//   pnpm version:check       falla si los archivos no coinciden entre sí
//
// Las reglas de cuándo subir la versión están en CONTRIBUTING.md.
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

// Cada entrada: archivo y expresión cuyo grupo 2 es la versión.
const JSON_VERSION = /^(\s*"version":\s*")([^"]+)(")/m;
const TOML_VERSION = /^(version\s*=\s*")([^"]+)(")/m;
const lockEntry = (name) => new RegExp(`(name = "${name}"\\r?\\nversion = ")([^"]+)(")`);

const TARGETS = [
  ["package.json", JSON_VERSION],
  ["apps/desktop/package.json", JSON_VERSION],
  ["apps/desktop/src-tauri/tauri.conf.json", JSON_VERSION],
  ["apps/desktop/src-tauri/Cargo.toml", TOML_VERSION],
  ["apps/desktop/src-tauri/Cargo.lock", lockEntry("kronos-desktop")],
  ["engine/pyproject.toml", TOML_VERSION],
  ["engine/uv.lock", lockEntry("kronos-engine")],
  ["engine/src/kronos_engine/__init__.py", /^(__version__\s*=\s*")([^"]+)(")/m],
];

function read(file, pattern) {
  const text = readFileSync(join(root, file), "utf8");
  const match = text.match(pattern);
  if (!match) throw new Error(`No se encontró la versión en ${file}`);
  return { text, version: match[2] };
}

const arg = process.argv[2];

if (arg === "--check") {
  const found = TARGETS.map(([file, pattern]) => [file, read(file, pattern).version]);
  const versions = new Set(found.map(([, version]) => version));
  if (versions.size > 1) {
    console.error("Las versiones no coinciden:");
    for (const [file, version] of found) console.error(`  ${version}  ${file}`);
    process.exit(1);
  }
  console.log(`Versión ${[...versions][0]} en los ${found.length} archivos.`);
} else if (/^\d+\.\d+\.\d+$/.test(arg ?? "")) {
  for (const [file, pattern] of TARGETS) {
    const { text, version } = read(file, pattern);
    if (version === arg) continue;
    writeFileSync(join(root, file), text.replace(pattern, `$1${arg}$3`));
    console.log(`${version} -> ${arg}  ${file}`);
  }
} else {
  console.error("Uso: pnpm version:set X.Y.Z   |   pnpm version:check");
  process.exit(1);
}

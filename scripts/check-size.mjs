// Controla el tamaño de los archivos de código.
//
//   pnpm size:check   falla si algún archivo supera el tope
//
// El objetivo y el tope están explicados en docs/CODIGO.md.
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");

const GOAL = 150; // Por encima se avisa: conviene pensar si el archivo hace dos cosas.
const LIMIT = 300; // Por encima falla.

const CODE = /\.(py|rs|ts|tsx|mjs)$/;
// Fuera del control: tests, tipos declarados y código generado.
const EXEMPT = [/(^|\/)tests\//, /\.test\.tsx?$/, /\.d\.ts$/, /(^|\/)gen\//];

const tracked = execFileSync("git", ["ls-files"], { cwd: root, encoding: "utf8" }).split("\n");
const sizes = tracked
  .filter((file) => CODE.test(file) && !EXEMPT.some((pattern) => pattern.test(file)))
  .map((file) => [file, readFileSync(join(root, file), "utf8").trimEnd().split("\n").length])
  .sort(([, a], [, b]) => b - a);

const tooLong = sizes.filter(([, lines]) => lines > LIMIT);
const aboveGoal = sizes.filter(([, lines]) => lines > GOAL && lines <= LIMIT);

const list = (files) => files.map(([file, lines]) => `  ${String(lines).padStart(4)}  ${file}`).join("\n");

if (aboveGoal.length) console.log(`Por encima del objetivo de ${GOAL} líneas (no falla):\n${list(aboveGoal)}`);
if (tooLong.length) {
  console.error(`Superan el tope de ${LIMIT} líneas:\n${list(tooLong)}`);
  process.exit(1);
}
console.log(`${sizes.length} archivos de código, ninguno supera las ${LIMIT} líneas.`);

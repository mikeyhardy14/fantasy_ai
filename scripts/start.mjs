import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const win = process.platform === "win32";
const backend = path.join(root, "backend");
const frontend = path.join(root, "frontend");
const python = path.join(backend, ".venv", win ? "Scripts/python.exe" : "bin/python");
const nextBin = path.join(frontend, "node_modules", "next", "dist", "bin", "next");

function fail(message) {
  console.error(message);
  process.exit(1);
}

if (!existsSync(python)) {
  fail(`Backend venv missing at ${python}\nFrom backend/: python -m venv .venv && .venv/${win ? "Scripts" : "bin"}/pip install -e ".[dev]"`);
}
if (!existsSync(nextBin)) {
  fail("Frontend deps missing. Run npm install from the repo root.");
}

const sqliteUrl = "sqlite+aiosqlite:///./dev.db";
const databaseUrl = process.env.DATABASE_URL || sqliteUrl;
const jwtSecret = process.env.JWT_SECRET?.trim() || "local-dev-jwt-secret-not-for-production";
if (!process.env.DATABASE_URL) {
  console.log("No DATABASE_URL in the shell; using SQLite at backend/dev.db (Postgres is not required).");
}
if (!process.env.JWT_SECRET?.trim()) {
  console.log("No JWT_SECRET in the shell; using a local development secret.");
}

const env = {
  ...process.env,
  DATABASE_URL: databaseUrl,
  JWT_SECRET: jwtSecret,
  NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
};

function run(command, args, cwd) {
  return new Promise((resolve, reject) => {
    const child = spawn(command, args, { cwd, env, stdio: "inherit", windowsHide: true });
    child.on("error", reject);
    child.on("exit", (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${path.basename(command)} ${args.join(" ")} exited ${code}`));
    });
  });
}

const children = [];
let shuttingDown = false;

function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) {
    if (!child.killed) child.kill();
  }
  process.exit(code);
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

await run(python, ["-m", "alembic", "upgrade", "head"], backend);

console.log("\nAPI  http://localhost:8000\nApp  http://localhost:3000\n");

const api = spawn(python, ["-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"], {
  cwd: backend,
  env,
  stdio: "inherit",
  windowsHide: true,
});
const web = spawn(process.execPath, [nextBin, "dev", "-p", "3000"], {
  cwd: frontend,
  env,
  stdio: "inherit",
  windowsHide: true,
});
children.push(api, web);

api.on("exit", (code) => {
  if (!shuttingDown && code) shutdown(code);
});
web.on("exit", (code) => {
  if (!shuttingDown && code) shutdown(code);
});

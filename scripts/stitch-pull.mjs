#!/usr/bin/env node
/**
 * Download HTML + screenshots for a Stitch project (requires STITCH_API_KEY).
 * Loads STITCH_* from repo root .env when present.
 */
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outDir = path.join(repoRoot, "web-stitch", "stitch-export");

async function loadEnvFile() {
  const envPath = path.join(repoRoot, ".env");
  try {
    const text = await (await import("node:fs/promises")).readFile(envPath, "utf8");
    for (const line of text.split("\n")) {
      const t = line.trim();
      if (!t || t.startsWith("#")) continue;
      const i = t.indexOf("=");
      if (i <= 0) continue;
      const key = t.slice(0, i).trim();
      let val = t.slice(i + 1).trim();
      if ((val.startsWith('"') && val.endsWith('"')) || (val.startsWith("'") && val.endsWith("'"))) {
        val = val.slice(1, -1);
      }
      if (process.env[key] === undefined) process.env[key] = val;
    }
  } catch {
    /* no .env */
  }
}

async function download(url, dest) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`GET ${url} → ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  await writeFile(dest, buf);
}

async function main() {
  await loadEnvFile();
  const apiKey = process.env.STITCH_API_KEY;
  const projectId = process.env.STITCH_PROJECT_ID || "13160455557984658905";
  if (!apiKey) {
    console.error("Set STITCH_API_KEY in .env (see web-stitch/README.md).");
    process.exit(1);
  }

  process.env.STITCH_API_KEY = apiKey;

  const sdkEntry = path.join(repoRoot, "web-stitch", "node_modules", "@google", "stitch-sdk", "dist", "src", "index.js");
  const { stitch } = await import(pathToFileURL(sdkEntry).href);
  const project = stitch.project(projectId);
  const screens = await project.screens();
  if (!screens.length) {
    console.error(`No screens in project ${projectId}.`);
    process.exit(1);
  }

  await mkdir(outDir, { recursive: true });
  const manifest = [];

  for (const screen of screens) {
    const id = screen.id || screen.screenId || "screen";
    const safe = String(id).replace(/[^\w-]+/g, "_");
    try {
      const htmlUrl = await screen.getHtml();
      const imageUrl = await screen.getImage?.().catch(() => null);
      const htmlPath = path.join(outDir, `${safe}.html`);
      await download(htmlUrl, htmlPath);
      let pngPath = null;
      if (imageUrl) {
        pngPath = path.join(outDir, `${safe}.png`);
        await download(imageUrl, pngPath);
      }
      manifest.push({ id, html: htmlPath, png: pngPath });
      console.log("Saved", safe);
    } catch (err) {
      console.warn("Skip", safe, err instanceof Error ? err.message : err);
      manifest.push({ id, error: String(err) });
    }
  }

  await writeFile(path.join(outDir, "manifest.json"), JSON.stringify({ projectId, screens: manifest }, null, 2));
  console.log(`Done — ${screens.length} screen(s) in ${outDir}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

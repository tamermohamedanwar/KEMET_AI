import fs from "node:fs";
import path from "node:path";
import { google } from "googleapis";

const ROOT = path.resolve(new URL("../..", import.meta.url).pathname);
const STATE = path.join(ROOT, "ops/youtube_state");
const CLIENT = path.join(STATE, "client_secret.json");
const TOKEN = path.join(STATE, "token.json");
const manifest = process.argv[2] ? path.resolve(process.argv[2]) : null;

const checks = [];
checks.push(["node", Number(process.versions.node.split(".")[0]) >= 18]);
checks.push(["googleapis", !!google.youtube]);
checks.push(["oauth_client", fs.existsSync(CLIENT)]);
checks.push(["oauth_token", fs.existsSync(TOKEN)]);
if (manifest) checks.push(["manifest", fs.existsSync(manifest)]);

for (const [name, ok] of checks) console.log(`${ok ? "OK" : "BLOCKED"} ${name}`);
const blocked = checks.filter(([, ok]) => !ok);
if (blocked.length) {
  console.log("YouTube production connection is blocked until the listed local prerequisites are satisfied.");
  process.exitCode = 2;
} else {
  console.log("YouTube worker prerequisites are ready.");
}

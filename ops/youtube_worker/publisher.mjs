import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import http from "node:http";
import { execFile } from "node:child_process";

const ROOT = path.resolve(new URL("../..", import.meta.url).pathname);
const STATE = path.join(ROOT, "ops/youtube_state");
const CLIENT = path.join(STATE, "client_secret.json");
const TOKEN = path.join(STATE, "token.json");
const uploads = path.join(STATE, "uploads.json");
const scopes = ["https://www.googleapis.com/auth/youtube.upload"];
const GOVERNED_ACTION = "youtube_publish";

function loadJson(file, fallback = {}) {
  return fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : fallback;
}
function saveJson(file, value) {
  const temp = `${file}.tmp-${process.pid}`;
  fs.writeFileSync(temp, JSON.stringify(value, null, 2), { mode: 0o600 });
  fs.renameSync(temp, file);
}
function openUrl(url) {
  try { execFile("termux-open-url", [url]); } catch { console.log(url); }
}
function readExecutionSecret() {
  if (process.env.KEMET_EXECUTION_SECRET) return process.env.KEMET_EXECUTION_SECRET;
  const envFile = path.join(ROOT, ".env.agent");
  if (!fs.existsSync(envFile)) return "";
  const line = fs.readFileSync(envFile, "utf8").split(/\r?\n/).find(x => /^KEMET_EXECUTION_SECRET=/.test(x));
  return line ? line.slice("KEMET_EXECUTION_SECRET=".length).replace(/^['\"]|['\"]$/g, "") : "";
}
function parseArgs() {
  const args = process.argv.slice(2);
  const manifest = args.find(x => !x.startsWith("--"));
  const authIndex = args.indexOf("--authorization-file");
  return { manifest, authorizationFile: authIndex >= 0 ? args[authIndex + 1] : null, simulate: args.includes("--simulate") };
}
function verifyAuthorization(auth) {
  if (!auth || typeof auth !== "object") throw new Error("execution_authorization_required");
  const secret = readExecutionSecret();
  if (!secret) throw new Error("execution_secret_not_configured");
  const expiresAt = Number(auth.expires_at || 0);
  if (!auth.token || !auth.plan_id || !auth.plan_hash || auth.action !== GOVERNED_ACTION) throw new Error("execution_authorization_invalid");
  if (!Number.isFinite(expiresAt) || expiresAt <= Math.floor(Date.now() / 1000)) throw new Error("execution_authorization_expired");
  const approver = auth.approver_id == null ? "None" : String(auth.approver_id);
  const payload = `${auth.plan_id}:${auth.plan_hash}:${auth.action}:${approver}:${expiresAt}`;
  const expected = crypto.createHmac("sha256", secret).update(payload).digest("hex");
  const provided = Buffer.from(String(auth.token));
  const expectedBuffer = Buffer.from(expected);
  if (provided.length !== expectedBuffer.length || !crypto.timingSafeEqual(provided, expectedBuffer)) throw new Error("execution_authorization_invalid");
}
async function auth() {
  if (!fs.existsSync(CLIENT)) throw new Error(`Missing OAuth client file: ${CLIENT}`);
  const config = loadJson(CLIENT);
  const c = config.installed || config.web;
  const oauth = new google.auth.OAuth2(c.client_id, c.client_secret, c.redirect_uris?.[0] || "http://127.0.0.1:0/oauth2callback");
  if (fs.existsSync(TOKEN)) {
    const saved = loadJson(TOKEN);
    const scope = String(saved.scope || "");
    if (scope.split(/\\s+/).includes(scopes[0])) {
      oauth.setCredentials(saved);
      try { await oauth.getAccessToken(); return oauth; } catch {}
    }
  }
  const server = http.createServer();
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;
  const redirect = `http://127.0.0.1:${port}/oauth2callback`;
  oauth.redirectUri = redirect;
  const url = oauth.generateAuthUrl({ access_type: "offline", scope: scopes, prompt: "consent" });
  console.log(`Authorize YouTube access: ${url}`);
  openUrl(url);
  const code = await new Promise((resolve, reject) => {
    server.on("request", (req, res) => {
      const u = new URL(req.url, redirect);
      if (u.pathname !== "/oauth2callback") return;
      if (u.searchParams.get("error")) return reject(new Error(u.searchParams.get("error")));
      res.end("Authorization complete. Return to Termux.");
      resolve(u.searchParams.get("code"));
    });
  });
  server.close();
  const { tokens } = await oauth.getToken(code);
  oauth.setCredentials(tokens);
  saveJson(TOKEN, tokens);
  fs.chmodSync(TOKEN, 0o600);
  return oauth;
}
function validateManifest(item, manifest) {
  if (!item || typeof item !== "object") throw new Error("manifest_invalid");
  for (const field of ["video", "title"]) if (!String(item[field] || "").trim()) throw new Error(`manifest_${field}_required`);
  const video = path.resolve(item.video);
  if (!fs.existsSync(video)) throw new Error(`Video not found: ${video}`);
  const stat = fs.statSync(video);
  if (!stat.isFile() || stat.size === 0) throw new Error("manifest_video_invalid");
  const privacy = String(item.privacy_status || "private");
  if (!["private", "unlisted", "public"].includes(privacy)) throw new Error("manifest_privacy_status_invalid");
  if (privacy === "public" && !item.publish_at) throw new Error("public_publish_requires_schedule");
  return video;
}

async function main() {
  const { manifest: manifestArg, authorizationFile, simulate } = parseArgs();
  if (!manifestArg) throw new Error("Manifest file required");
  const manifest = path.resolve(manifestArg);
  if (!fs.existsSync(manifest)) throw new Error("Manifest file required");
  const item = loadJson(manifest);
  const video = validateManifest(item, manifest);
  const manifestDigest = crypto.createHash("sha256").update(fs.readFileSync(manifest)).digest("hex");
  const key = String(item.idempotency_key || `manifest:${manifestDigest}`);
  const state = loadJson(uploads);
  if (state[key]) { console.log(JSON.stringify({ ...state[key], idempotent_replay: true })); return; }

  if (simulate) {
    console.log(JSON.stringify({ mode: "simulate", action: GOVERNED_ACTION, idempotency_key: key, video, title: item.title, privacy_status: item.privacy_status || "private" }));
    return;
  }

  if (!authorizationFile || !fs.existsSync(authorizationFile)) throw new Error("governed_execution_authorization_file_required");
  const authorization = loadJson(authorizationFile);
  verifyAuthorization(authorization);

  const { google } = await import("googleapis");
  const authClient = await auth();
  const youtube = google.youtube({ version: "v3", auth: authClient });
  const channelResponse = await youtube.channels.list({ part: ["id", "snippet"], mine: true });
  const channel = channelResponse.data.items?.[0];
  if (!channel?.id) throw new Error("youtube_channel_not_found");

  const status = { privacyStatus: item.privacy_status || "private", selfDeclaredMadeForKids: !!item.made_for_kids };
  if (item.publish_at) { status.privacyStatus = "private"; status.publishAt = item.publish_at; }
  const response = await youtube.videos.insert({
    part: ["snippet", "status"],
    requestBody: { snippet: { title: item.title, description: item.description || "", tags: item.tags || [], categoryId: String(item.category_id || "22") }, status },
    media: { body: fs.createReadStream(video) },
  });
  const result = { video_id: response.data.id, channel_id: channel.id, channel_title: channel.snippet?.title || null, status: response.data.status || {}, uploaded_at: new Date().toISOString(), idempotency_key: key, plan_id: authorization.plan_id };
  state[key] = result;
  saveJson(uploads, state);
  console.log(JSON.stringify(result));
}
main().catch(err => { console.error(err.message); process.exit(1); });

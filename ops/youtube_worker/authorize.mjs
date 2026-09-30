import fs from "node:fs/promises";
import http from "node:http";
import { execFile } from "node:child_process";

const stateDir = new URL("../youtube_state/", import.meta.url);
const clientPath = new URL("client_secret.json", stateDir);
const tokenPath = new URL("token.json", stateDir);
const scopes = [
  "https://www.googleapis.com/auth/youtube.readonly",
  "https://www.googleapis.com/auth/yt-analytics.readonly",
  "https://www.googleapis.com/auth/yt-analytics-monetary.readonly",
];

const openUrl = (url) => new Promise((resolve) => execFile("termux-open-url", [url], () => resolve()));

async function loadClient() {
  const raw = JSON.parse(await fs.readFile(clientPath, "utf8"));
  const cfg = raw.installed ?? raw.web;
  if (!cfg?.client_id || !cfg?.client_secret) throw new Error("invalid_oauth_client");
  return cfg;
}

async function main() {
  const { google } = await import("googleapis");
  await fs.mkdir(stateDir, { recursive: true });
  const cfg = await loadClient();
  const server = http.createServer();
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;
  const redirect = `http://127.0.0.1:${port}`;
  const oauth = new google.auth.OAuth2(cfg.client_id, cfg.client_secret, redirect);
  const authUrl = oauth.generateAuthUrl({ access_type: "offline", prompt: "consent", scope: scopes });
  const code = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("oauth_timeout")), 5 * 60 * 1000);
    server.on("request", (req, res) => {
      const url = new URL(req.url, redirect);
      const error = url.searchParams.get("error");
      const code = url.searchParams.get("code");
      res.writeHead(200, { "content-type": "text/plain; charset=utf-8" });
      res.end(error ? "Authorization cancelled." : "Authorization received.");
      clearTimeout(timer);
      if (error) reject(new Error(`oauth_denied:${error}`));
      else if (code) resolve(code);
      else reject(new Error("oauth_callback_missing_code"));
    });
    console.log(`WAITING http://127.0.0.1:${port}`);
    void openUrl(authUrl);
  });
  console.log(`OPEN ${authUrl}`);
  const { tokens } = await oauth.getToken(code);
  await fs.writeFile(tokenPath, JSON.stringify(tokens, null, 2) + "\n", { mode: 0o600 });
  await fs.chmod(tokenPath, 0o600);
  server.close();
  console.log("OK analytics_oauth_token_stored");
}

main().catch((error) => {
  console.error(`ERROR ${error.message}`);
  process.exitCode = 1;
});





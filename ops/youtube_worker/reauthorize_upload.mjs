import fs from "node:fs";
import path from "node:path";
import http from "node:http";
import { execFile } from "node:child_process";
import { google } from "googleapis";

const state = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../youtube_state");
const client = JSON.parse(fs.readFileSync(path.join(state, "client_secret.json"), "utf8"));
const c = client.installed || client.web;
const oauth = new google.auth.OAuth2(c.client_id, c.client_secret);
const server = http.createServer();
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;
const redirect = `http://127.0.0.1:${port}/oauth2callback`;
oauth.redirectUri = redirect;
const scope = "https://www.googleapis.com/auth/youtube.upload";
const url = oauth.generateAuthUrl({ access_type: "offline", scope: [scope], prompt: "consent" });
console.log("AUTH_URL="+url);
try { execFile("termux-open-url", [url]); } catch {}
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
tokens.scope = tokens.scope || scope;
const tokenPath = path.join(state, "token.json");
const tmp = tokenPath + ".tmp";
fs.writeFileSync(tmp, JSON.stringify(tokens, null, 2), { mode: 0o600 });
fs.renameSync(tmp, tokenPath);
fs.chmodSync(tokenPath, 0o600);
console.log("AUTHORIZATION_COMPLETE");
console.log("UPLOAD_SCOPE_PRESENT="+String(String(tokens.scope).split(/\s+/).includes(scope)));

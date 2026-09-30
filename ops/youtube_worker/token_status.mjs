import fs from "node:fs/promises";

const tokenPath = new URL("../youtube_state/token.json", import.meta.url);

async function main() {
  const token = JSON.parse(await fs.readFile(tokenPath, "utf8"));
  const scopes = typeof token.scope === "string" ? token.scope.split(/\s+/).filter(Boolean) : [];
  const required = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/yt-analytics-monetary.readonly",
  ];
  console.log(JSON.stringify({
    token_present: true,
    access_token_present: Boolean(token.access_token),
    refresh_token_present: Boolean(token.refresh_token),
    required_scopes: Object.fromEntries(required.map((scope) => [scope, scopes.includes(scope)])),
    scope_count: scopes.length,
  }));
}

main().catch((error) => {
  console.log(JSON.stringify({ token_present: false, error: error.message }));
  process.exitCode = 1;
});

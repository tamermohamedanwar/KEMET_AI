import fs from "node:fs/promises";

const stateDir = new URL("../youtube_state/", import.meta.url);
const clientPath = new URL("client_secret.json", stateDir);
const tokenPath = new URL("token.json", stateDir);

async function loadClient() {
  const raw = JSON.parse(await fs.readFile(clientPath, "utf8"));
  const cfg = raw.installed ?? raw.web;
  if (!cfg?.client_id || !cfg?.client_secret) throw new Error("invalid_oauth_client");
  return cfg;
}

async function main() {
  const args = process.argv.slice(2);
  if (args.includes("--simulate")) {
    const start = args[args.indexOf("--start") + 1] ?? "2026-09-01";
    const end = args[args.indexOf("--end") + 1] ?? "2026-09-14";
    console.log(JSON.stringify({
      mode: "simulate",
      read_only: true,
      verified_source: false,
      source: "youtube_analytics_api",
      period: { start, end },
      rows: [[0, 0, 0, 0, 0]],
      headers: [
        { name: "views" }, { name: "estimatedMinutesWatched" },
        { name: "averageViewPercentage" }, { name: "estimatedRevenue" },
        { name: "estimatedAdRevenue" },
      ],
    }));
    return;
  }
  const { google } = await import("googleapis");
  const cfg = await loadClient();
  const tokens = JSON.parse(await fs.readFile(tokenPath, "utf8"));
  const oauth = new google.auth.OAuth2(cfg.client_id, cfg.client_secret);
  oauth.setCredentials(tokens);
  const analytics = google.youtubeAnalytics({ version: "v2", auth: oauth });
  const end = new Date();
  const start = new Date(end.getTime() - 30 * 24 * 60 * 60 * 1000);
  const iso = (date) => date.toISOString().slice(0, 10);
  const response = await analytics.reports.query({
    ids: "channel==MINE",
    startDate: iso(start),
    endDate: iso(end),
    metrics: "views,estimatedMinutesWatched,averageViewPercentage,estimatedRevenue,estimatedAdRevenue",
    currency: "EGP",
  });
  console.log(JSON.stringify({
    read_only: true,
    verified_source: true,
    source: "youtube_analytics_api",
    period: { start: iso(start), end: iso(end) },
    rows: response.data.rows ?? [],
    headers: response.data.columnHeaders ?? [],
  }));
}

main().catch((error) => {
  const status = error?.response?.status ?? error?.code ?? null;
  console.log(JSON.stringify({
    error: "youtube_analytics_failed",
    status,
    message: error?.response?.data?.error?.message ?? error.message,
    verified_source: false,
  }));
  process.exitCode = 1;
});



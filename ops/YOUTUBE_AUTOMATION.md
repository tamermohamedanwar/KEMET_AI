# Kemet Termux YouTube Automation

Kemet can replace an n8n-style YouTube workflow with a local, auditable worker.

Flow:
`Approved content -> manifest -> video -> OAuth -> YouTube upload -> private/scheduled publication -> receipt -> state`

This worker is separate from Kemet production execution. It never bypasses human approval or mutates Kemet business records.

## Setup

Enable YouTube Data API v3 in Google Cloud and create OAuth 2.0 credentials for an installed application. Save the downloaded JSON as `ops/youtube_state/client_secret.json`.

The first run opens Google's consent flow. The refresh token is stored locally as `token.json` with mode 600.

## Manifest

Required: `video`, `title`.

Optional: `description`, `tags`, `category_id`, `privacy_status`, `publish_at`, `made_for_kids`.

Scheduled publication forces `privacyStatus=private` and uses a future ISO-8601 `publish_at` value.

## Run

`node ops/youtube_worker/doctor.mjs ops/youtube_queue/<manifest>.json`

`node ops/youtube_worker/publisher.mjs ops/youtube_queue/<manifest>.json`

The worker is idempotent by an explicit manifest `idempotency_key` when provided, otherwise by the SHA-256 digest of the manifest content. It records the returned YouTube video ID in `ops/youtube_state/uploads.json`.

## Security

Never commit Google OAuth client secrets or tokens. They are ignored by Git. Do not put them in Kemet business tables or application logs.


## Production connection boundary

The only required human step is Google account authorization. Create a YouTube Data API v3 OAuth 2.0 installed-app credential in Google Cloud and place the downloaded client JSON at `ops/youtube_state/client_secret.json` on the Termux device. Do not send the credential or token to ChatGPT and do not commit either file. The worker performs the OAuth consent flow locally and stores the refresh token in `ops/youtube_state/token.json` with restrictive permissions.

Once OAuth is authorized, one worker invocation can upload the video with title, description, category, tags, privacy, and a future scheduled publication time. No n8n server is required.

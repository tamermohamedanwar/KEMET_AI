---
title: Kemet Free Video Worker
emoji: 🎬
colorFrom: blue
colorTo: purple
sdk: gradio
python_version: "3.12.12"
app_file: app.py
---

# Kemet Free Video Worker — ZeroGPU

Kemet-owned worker boundary for a real free GPU execution path. Kemet remains the canonical planner, approval gate, execution authority, evidence fabric, and orchestrator.

## Required Space configuration

- Hardware: ZeroGPU
- Secret: KEMET_WORKER_SECRET
- Optional variable: KEMET_WORKER_ID
- Optional variable: KEMET_VIDEO_MODEL

The worker exposes GET /health and POST /v1/jobs. It never enables MCP and never receives execution authority from the Space itself.

## Model

Default model: Wan-AI/Wan2.1-T2V-1.3B-Diffusers.
The model repository states Apache-2.0 licensing and supports text-to-video generation. Kemet must still verify fresh worker evidence, capacity, and license metadata before admission.

## Free-capacity truth

ZeroGPU is shared and quota-limited. A Space being deployed does not make it production-ready. Kemet admits it only after a fresh /health attestation passes its existing Remote Worker Registry and Worker Health Attestation gates.

## First proof

The intended first execution is a short 480p Golden Shot through the existing Kemet approval → execution boundary. No automatic publication is performed.

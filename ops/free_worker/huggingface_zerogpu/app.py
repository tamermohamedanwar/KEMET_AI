import hashlib
import hmac
import json
import os
import time
from pathlib import Path

import spaces
import torch
from diffusers import UniPCMultistepScheduler, WanPipeline
from diffusers.utils import export_to_video
from fastapi import Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from gradio import Server

MODEL_ID = os.getenv("KEMET_VIDEO_MODEL", "Wan-AI/Wan2.1-T2V-1.3B-Diffusers")
WORKER_ID = os.getenv("KEMET_WORKER_ID", "kemet_hf_zerogpu_001")
PROVIDER_ID = "huggingface_zerogpu"
PUBLIC_BASE_URL = os.getenv("KEMET_PUBLIC_BASE_URL", "").rstrip("/")
SECRET = os.getenv("KEMET_WORKER_SECRET", "")
OUT = Path("/tmp/kemet_worker")
OUT.mkdir(parents=True, exist_ok=True)

pipe = WanPipeline.from_pretrained(MODEL_ID, torch_dtype=torch.bfloat16)
pipe.scheduler = UniPCMultistepScheduler.from_config(pipe.scheduler.config, flow_shift=5.0)
pipe.enable_model_cpu_offload()

def _digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)

def _verify(request: dict, signature: str) -> None:
    if not SECRET or not signature:
        raise HTTPException(status_code=400, detail="worker_request_signature_required")
    expected = hmac.new(SECRET.encode(), _canonical(request).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=400, detail="worker_request_signature_invalid")

def _hardware() -> dict:
    if torch.cuda.is_available():
        try:
            props = torch.cuda.get_device_properties(0)
            return {"gpu": str(props.name), "vram_mb": int(props.total_memory // (1024 * 1024)), "compute_runtime": "CUDA"}
        except Exception:
            pass
    return {"gpu": "CUDA_RUNTIME_UNVERIFIED", "vram_mb": 0, "compute_runtime": "CUDA"}

@spaces.GPU(duration=120)
def generate_video(prompt: str, seed: int = 42) -> Path:
    generator = torch.Generator(device="cuda").manual_seed(int(seed))
    frames = pipe(prompt=str(prompt), height=480, width=832, num_frames=49,
                  guidance_scale=5.0, num_inference_steps=20, generator=generator).frames[0]
    output = OUT / f"{int(time.time())}_{seed}.mp4"
    export_to_video(frames, str(output), fps=16)
    return output

app = Server()

@app.get("/health")
async def health():
    hardware = _hardware()
    return {
        "worker_id": WORKER_ID,
        "provider_id": PROVIDER_ID,
        "reported_at": int(time.time()),
        "status": "READY",
        "capabilities": ["VIDEO_GENERATION"],
        "capacity": {"attestation": {"ready": True}, "in_flight": 0, "max_concurrency": 1,
                     "queue_depth": 0, "max_queue_depth": 1},
        "hardware": hardware,
        "pricing": {"free": True},
        "license": {"commercial_use": True, "model": MODEL_ID, "basis": "Apache-2.0 model license"},
    }

@app.get("/v1/artifacts/{filename}")
async def artifact(filename: str):
    path = (OUT / Path(filename).name).resolve()
    if not path.is_file() or path.parent != OUT.resolve():
        raise HTTPException(status_code=404, detail="artifact_not_found")
    return FileResponse(path, media_type="video/mp4", filename=path.name)

@app.post("/v1/jobs")
async def create_job(request: dict, x_kemet_worker_signature: str | None = Header(default=None)):
    _verify(request, x_kemet_worker_signature or "")
    job = dict(request.get("job") or {})
    if not job.get("digest") or not job.get("canonical_shot_digest") or not job.get("shot_id"):
        raise HTTPException(status_code=400, detail="canonical_job_binding_required")
    prompt = str(job.get("prompt") or "").strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="prompt_required")
    output = await _run_generation(prompt, int(job.get("seed", 42)))
    if not PUBLIC_BASE_URL:
        raise HTTPException(status_code=503, detail="worker_public_base_url_not_configured")
    artifact = {"uri": f"{PUBLIC_BASE_URL}/v1/artifacts/{output.name}",
                "sha256": _digest_file(output), "mime_type": "video/mp4"}
    body = {"schema": "kemet.media.remote_worker_response.v1", "version": 1,
            "organization_id": int(request["organization_id"]), "request_id": request["request_id"],
            "idempotency_key": request["idempotency_key"],
            "canonical_shot_digest": job["canonical_shot_digest"], "status": "COMPLETED",
            "artifact": artifact, "provenance": {"worker_id": WORKER_ID, "model_id": MODEL_ID, "trust": "untrusted"}}
    signature = hmac.new(SECRET.encode(), _canonical(body).encode(), hashlib.sha256).hexdigest()
    return JSONResponse(content=body, headers={"X-Kemet-Worker-Signature": signature})

async def _run_generation(prompt: str, seed: int) -> Path:
    import asyncio
    return await asyncio.to_thread(generate_video, prompt, seed)

if __name__ == "__main__":
    app.launch(server_name="0.0.0.0", server_port=int(os.getenv("PORT", "7860")), mcp_server=False)

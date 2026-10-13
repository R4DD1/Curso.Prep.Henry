"""
Video Workflow - Mini app para generación de video IA
Soporta Siray (Wan 3.0, Seedance, Kling) y escalado via fal.ai
"""

import asyncio
import json
import os
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Video Workflow")

UPLOADS_DIR = Path("uploads")
OUTPUTS_DIR = Path("outputs")
HISTORY_FILE = Path("history.json")

UPLOADS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)

if not HISTORY_FILE.exists():
    HISTORY_FILE.write_text("[]")

# ─── Modelos disponibles ────────────────────────────────────────────────────

MODELS = {
    # ── Wan 3.0 ──────────────────────────────────────────────────────────────
    "wan3": {
        "id": "alibaba/wan-3.0-i2v",
        "name": "Wan 3.0",
        "badge": "RECOMENDADO",
        "description": "Movimientos naturales, expresiones, danza.",
        "max_duration": 15,
        "price_per_sec": 0.040,
        "resolution": ["480p", "720p"],
        "needs_image": True,
    },
    "wan3-spicy": {
        "id": "alibaba/wan-3.0-i2v-spicy",
        "name": "Wan 3.0 Spicy",
        "badge": "SIN CENSURA",
        "description": "Igual que Wan 3.0 pero sin restricciones de contenido. Hasta 1080p.",
        "max_duration": 15,
        "price_per_sec": 0.045,
        "resolution": ["480p", "720p", "1080p"],
        "needs_image": True,
    },
    "wan3-ref": {
        "id": "alibaba/wan-3.0-ref2v",
        "name": "Wan 3.0 Ref2V",
        "badge": "VIDEO REF",
        "description": "Cloná movimientos desde un video de referencia.",
        "max_duration": 15,
        "price_per_sec": 0.040,
        "resolution": ["480p", "720p"],
        "needs_image": True,
        "needs_ref_video": True,
    },
    # ── Kling ────────────────────────────────────────────────────────────────
    "kling": {
        "id": "kuaishou/kling-3-motion-control",
        "name": "Kling 3 Motion Control",
        "badge": "",
        "description": "Coreografías, cámara fija, bailes limpios.",
        "max_duration": 10,
        "price_per_sec": 0.126,
        "resolution": ["720p"],
        "needs_image": True,
    },
    "kling-spicy": {
        "id": "kuaishou/kling-3-motion-control",
        "name": "Kling 3 Motion Control",
        "badge": "",
        "description": "Kling 3 Motion Control, bailes y movimientos corporales.",
        "max_duration": 10,
        "price_per_sec": 0.126,
        "resolution": ["720p"],
        "needs_image": True,
    },
    # ── MiniMax ──────────────────────────────────────────────────────────────
    "minimax-v01": {
        "id": "minimax/minimax-h3-i2v",
        "name": "MiniMax H3",
        "badge": "",
        "description": "Alta calidad de movimiento y expresiones faciales.",
        "max_duration": 6,
        "price_per_sec": 0.130,
        "resolution": ["720p", "1080p"],
        "needs_image": True,
    },
    "minimax-live": {
        "id": "minimax/minimax-h3-i2v",
        "name": "MiniMax H3",
        "badge": "POTENTE",
        "description": "Movimiento hiper-realista, ideal para avatares y UGC.",
        "max_duration": 6,
        "price_per_sec": 0.130,
        "resolution": ["720p", "1080p"],
        "needs_image": True,
    },
    "minimax-live-spicy": {
        "id": "minimax/minimax-h3-i2v-spicy",
        "name": "MiniMax H3 (sin censura)",
        "badge": "SIN CENSURA",
        "description": "MiniMax H3 sin filtros de contenido.",
        "max_duration": 6,
        "price_per_sec": 0.130,
        "resolution": ["720p", "1080p"],
        "needs_image": True,
    },
    # ── Seedance ─────────────────────────────────────────────────────────────
    "seedance": {
        "id": "bytedance/seedance-1.0-lite-i2v",
        "name": "Seedance 1.0 Lite",
        "badge": "",
        "description": "Físicas complejas, movimientos rápidos, manos.",
        "max_duration": 10,
        "price_per_sec": 0.032,
        "resolution": ["480p", "720p"],
        "needs_image": True,
    },
    "seedance-20": {
        "id": "bytedance/seedance-2.0-i2v",
        "name": "Seedance 2.0",
        "badge": "NUEVO",
        "description": "Mayor coherencia temporal y mejor calidad de movimiento que 1.0.",
        "max_duration": 10,
        "price_per_sec": 0.084,
        "resolution": ["480p", "720p"],
        "needs_image": True,
    },
    "seedance-25": {
        "id": "bytedance/seedance-2.5-i2v",
        "name": "Seedance 2.5",
        "badge": "TOP",
        "description": "Última versión, físicas ultra-realistas, ideal para manos con productos.",
        "max_duration": 10,
        "price_per_sec": 0.134,
        "resolution": ["480p", "720p", "1080p"],
        "needs_image": True,
    },
    # ── Veo 3 ────────────────────────────────────────────────────────────────
    "veo3": {
        "id": "google/veo-3",
        "name": "Veo 3",
        "badge": "BETA",
        "description": "Modelo de Google, alta calidad cinematográfica.",
        "max_duration": 8,
        "price_per_sec": 0.240,
        "resolution": ["720p", "1080p"],
        "needs_image": True,
    },
}

IMAGE_MODELS = {
    "flux-schnell":      {"id": "black-forest-labs/flux-1.1-pro-t2i",       "name": "FLUX Schnell"},
    "flux-dev":          {"id": "black-forest-labs/flux-1.1-pro-ultra-t2i",  "name": "FLUX Dev"},
    "sdxl":              {"id": "bytedance/seedream-4.0-t2i",                "name": "SDXL 1.0"},
    "nano-banana-2":     {"id": "google/nano-banana-2-t2i",                  "name": "Nano Banana 2"},
    "nano-banana-21":    {"id": "google/nano-banana-2-lite-t2i",             "name": "Nano Banana 2.1"},
    "grok-aurora":       {"id": "x-ai/grok-imagine-image-t2i",              "name": "Grok Aurora (xAI)"},
    "dalle3":            {"id": "openai/gpt-image-2-t2i",                    "name": "DALL·E 3"},
    "flux-schnell-spicy":{"id": "black-forest-labs/flux-1.1-pro-t2i",       "name": "FLUX Schnell Spicy"},
    "flux-dev-spicy":    {"id": "black-forest-labs/flux-1.1-pro-ultra-t2i",  "name": "FLUX Dev Spicy"},
    "pony-diffusion":    {"id": "bytedance/seedream-4.5-t2i-spicy",          "name": "Pony Diffusion XL"},
}

UPSCALE_PRICE_PER_SEC = 0.0072  # fal.ai ByteDance upscaler 1080p/30fps

RH_BASE = "https://www.runninghub.ai"
RH_UPSCALE_WORKFLOW_NODE = [{"nodeId": "16", "fieldName": "video"}]


# ─── API de RunningHub ──────────────────────────────────────────────────────

async def rh_upload_url(rh_key: str, video_url: str) -> str:
    """Download video from URL and upload to RunningHub. Returns fileName."""
    async with httpx.AsyncClient(timeout=120) as client:
        dl = await client.get(video_url)
        if dl.status_code != 200:
            raise HTTPException(status_code=400, detail="No se pudo descargar el video para escalar")
        video_bytes = dl.content

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{RH_BASE}/task/openapi/upload",
            headers={"apikey": rh_key},
            files={"file": ("video.mp4", video_bytes, "video/mp4")},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=f"RH upload: {resp.text}")
        data = resp.json()
        # API returns {"code":0,"data":{"fileName":"api/..."}}
        file_name = (data.get("data") or {}).get("fileName") or data.get("fileName")
        if not file_name:
            raise HTTPException(status_code=500, detail=f"RH upload sin fileName: {data}")
        return file_name


async def rh_create_task(rh_key: str, workflow_id: str, file_name: str) -> str:
    """Submit workflow task to RunningHub. Returns taskId."""
    payload = {
        "workflowId": workflow_id,
        "nodeInfoList": [
            {"nodeId": "16", "fieldName": "video", "fieldValue": file_name}
        ],
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{RH_BASE}/task/openapi/create",
            headers={"apikey": rh_key, "Content-Type": "application/json"},
            json=payload,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=f"RH create: {resp.text}")
        data = resp.json()
        task_id = (data.get("data") or {}).get("taskId") or data.get("taskId")
        if not task_id:
            raise HTTPException(status_code=500, detail=f"RH create sin taskId: {data}")
        return task_id


async def rh_get_outputs(rh_key: str, task_id: str) -> dict:
    """Poll RunningHub task outputs."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{RH_BASE}/task/openapi/outputs",
            headers={"apikey": rh_key},
            params={"taskId": task_id},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=f"RH outputs: {resp.text}")
        return resp.json()


# ─── API de Siray ───────────────────────────────────────────────────────────

async def siray_generate(api_key: str, model_id: str, image_url: str, prompt: str, duration: int, resolution: str, ref_video_url: Optional[str] = None) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload: dict = {
        "model": model_id,
        "image": image_url,
        "prompt": prompt,
        "duration": duration,
        "size": resolution,
        "aspect_ratio": "adaptive",
    }
    if ref_video_url:
        payload["end_image"] = ref_video_url
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post("https://api.siray.ai/v1/video/generations", headers=headers, json=payload)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


async def siray_status(api_key: str, task_id: str) -> dict:
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"https://api.siray.ai/v1/video/generations/{task_id}", headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


async def siray_generate_image(api_key: str, model_id: str, prompt: str, size: str = "1:1", n: int = 1) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload: dict = {
        "model": model_id,
        "prompt": prompt,
        "size": size,
        "n": n,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post("https://api.siray.ai/v1/images/generations/async", headers=headers, json=payload)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


async def siray_image_status(api_key: str, task_id: str) -> dict:
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"https://api.siray.ai/v1/images/generations/async/{task_id}", headers=headers)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


async def siray_balance(api_key: str) -> float:
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get("https://api.siray.ai/v1/account/balance", headers=headers)
        if resp.status_code != 200:
            return -1.0
        data = resp.json()
        # Try multiple possible field paths
        bal = (
            data.get("balance")
            or (data.get("data") or {}).get("balance")
            or data.get("credits")
            or data.get("available_balance")
            or data.get("available")
        )
        return float(bal) if bal is not None else 0.0


async def rh_balance(api_key: str) -> float:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            f"{RH_BASE}/task/openapi/user/info",
            headers={"apikey": api_key},
        )
        if resp.status_code != 200:
            return -1.0
        data = resp.json()
        if data.get("code") != 0:
            return -1.0
        info = data.get("data") or {}
        bal = info.get("accountBalance") or info.get("balance") or info.get("credits") or info.get("coin")
        return float(bal) if bal is not None else -1.0


# ─── Historial local ────────────────────────────────────────────────────────

def load_history() -> list:
    try:
        return json.loads(HISTORY_FILE.read_text())
    except Exception:
        return []


def save_history(history: list):
    HISTORY_FILE.write_text(json.dumps(history, indent=2, ensure_ascii=False))


def add_to_history(entry: dict):
    history = load_history()
    history.insert(0, entry)
    history = history[:50]  # keep last 50
    save_history(history)


# ─── Endpoints ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse("static/index.html")


@app.get("/api/models")
async def get_models():
    return MODELS


@app.post("/api/balance")
async def check_balance(api_key: str = Form(...)):
    balance = await siray_balance(api_key)
    return {"balance": balance}


@app.post("/api/rh-balance")
async def check_rh_balance(api_key: str = Form(...)):
    balance = await rh_balance(api_key)
    return {"balance": balance}


@app.post("/api/cost-estimate")
async def cost_estimate(
    model_key: str = Form(...),
    duration: int = Form(...),
    upscale: bool = Form(False),
):
    model = MODELS.get(model_key)
    if not model:
        raise HTTPException(status_code=400, detail="Modelo no encontrado")
    gen_cost = model["price_per_sec"] * duration
    upscale_cost = UPSCALE_PRICE_PER_SEC * duration if upscale else 0
    return {
        "generation": round(gen_cost, 4),
        "upscale": round(upscale_cost, 4),
        "total": round(gen_cost + upscale_cost, 4),
    }


@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix or ".jpg"
    filename = f"{uuid.uuid4()}{ext}"
    dest = UPLOADS_DIR / filename
    dest.write_bytes(await file.read())
    return {"path": f"/uploads/{filename}", "filename": filename}


@app.post("/api/upload-video")
async def upload_video(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix or ".mp4"
    filename = f"{uuid.uuid4()}{ext}"
    dest = UPLOADS_DIR / filename
    dest.write_bytes(await file.read())
    return {"path": f"/uploads/{filename}", "filename": filename}


@app.post("/api/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix or ".mp3"
    filename = f"{uuid.uuid4()}{ext}"
    dest = UPLOADS_DIR / filename
    dest.write_bytes(await file.read())
    return {"path": f"/uploads/{filename}", "filename": filename}


@app.post("/api/merge-audio-video")
async def merge_audio_video(
    video_url: str = Form(...),
    audio_filename: str = Form(...),
):
    audio_path = UPLOADS_DIR / audio_filename
    if not audio_path.exists():
        raise HTTPException(status_code=400, detail="Audio no encontrado")

    merged_filename = f"merged_{uuid.uuid4()}.mp4"
    merged_path = OUTPUTS_DIR / merged_filename

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.get(video_url)
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="No se pudo descargar el video de Siray")
        tmp_video_path = UPLOADS_DIR / f"tmp_{uuid.uuid4()}.mp4"
        tmp_video_path.write_bytes(resp.content)

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(tmp_video_path),
                "-i", str(audio_path),
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                str(merged_path),
            ],
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail="ffmpeg error: " + result.stderr.decode()[:300])
    finally:
        tmp_video_path.unlink(missing_ok=True)

    return {"merged_url": f"/outputs/{merged_filename}", "filename": merged_filename}


@app.get("/outputs/{filename}")
async def serve_output(filename: str):
    path = OUTPUTS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path)


@app.post("/api/generate")
async def generate(
    api_key: str = Form(...),
    model_key: str = Form(...),
    image_filename: str = Form(...),
    prompt: str = Form(...),
    duration: int = Form(10),
    resolution: str = Form("480p"),
    ref_video_filename: str = Form(""),
):
    import base64

    model = MODELS.get(model_key)
    if not model:
        raise HTTPException(status_code=400, detail="Modelo no encontrado")

    image_path = UPLOADS_DIR / image_filename
    if not image_path.exists():
        raise HTTPException(status_code=400, detail="Imagen no encontrada")

    img_bytes = image_path.read_bytes()
    suffix = image_path.suffix.lstrip(".")
    mime = f"image/{suffix}" if suffix in ("jpg", "jpeg", "png", "webp") else "image/jpeg"
    image_data_url = f"data:{mime};base64,{base64.b64encode(img_bytes).decode()}"

    ref_video_data_url: Optional[str] = None
    if ref_video_filename and model.get("needs_ref_video"):
        ref_path = UPLOADS_DIR / ref_video_filename
        if ref_path.exists():
            vid_bytes = ref_path.read_bytes()
            vid_suffix = ref_path.suffix.lstrip(".")
            vid_mime = f"video/{vid_suffix}" if vid_suffix in ("mp4", "webm", "mov") else "video/mp4"
            ref_video_data_url = f"data:{vid_mime};base64,{base64.b64encode(vid_bytes).decode()}"

    try:
        result = await siray_generate(api_key, model["id"], image_data_url, prompt, duration, resolution, ref_video_data_url)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    task_id = (result.get("data") or {}).get("task_id") or result.get("task_id") or result.get("id", "")
    gen_cost = model["price_per_sec"] * duration
    job = {
        "id": str(uuid.uuid4()),
        "task_id": task_id,
        "model": model["name"],
        "model_key": model_key,
        "prompt": prompt,
        "duration": duration,
        "resolution": resolution,
        "cost_estimate": round(gen_cost, 4),
        "status": "processing",
        "created_at": datetime.now().isoformat(),
        "video_url": None,
    }
    add_to_history(job)
    return {"job_id": job["id"], "task_id": task_id, "status": "processing"}


@app.get("/api/status/{task_id}")
async def task_status(task_id: str, api_key: str):
    try:
        result = await siray_status(api_key, task_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    data = result.get("data") or {}
    status = data.get("status", result.get("status", "unknown"))
    outputs = data.get("outputs") or []
    video_url = outputs[0] if outputs else (result.get("output", {}).get("video_url") or result.get("video_url"))

    if video_url and status.lower() in ("completed", "success"):
        history = load_history()
        for job in history:
            if job.get("task_id") == task_id:
                job["status"] = "completed"
                job["video_url"] = video_url
                break
        save_history(history)

    return {"status": status, "video_url": video_url, "raw": result}


@app.get("/api/history")
async def get_history():
    return load_history()


@app.post("/api/upscale")
async def upscale_video(
    rh_api_key: str = Form(...),
    rh_workflow_id: str = Form(...),
    video_url: str = Form(...),
):
    try:
        file_name = await rh_upload_url(rh_api_key, video_url)
        task_id = await rh_create_task(rh_api_key, rh_workflow_id, file_name)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"task_id": task_id, "status": "processing"}


@app.get("/api/upscale-status/{task_id}")
async def upscale_status(task_id: str, rh_api_key: str):
    try:
        result = await rh_get_outputs(rh_api_key, task_id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    data = result.get("data") or {}
    status = data.get("status") or result.get("status", "unknown")
    outputs = data.get("outputs") or result.get("outputs") or []
    video_url = None
    if outputs:
        item = outputs[0]
        video_url = item.get("fileUrl") or item.get("url") or item.get("videoUrl")
    return {"status": status, "video_url": video_url, "raw": result}


@app.get("/uploads/{filename}")
async def serve_upload(filename: str):
    path = UPLOADS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path)


ELEVENLABS_VOICE_IDS = {
    "Rachel": "21m00Tcm4TlvDq8ikWAM",
    "Adam":   "pNInz6obpgDQGcFmaJgB",
    "Bella":  "EXAVITQu4vr4xnSDxMaL",
    "Antoni": "ErXwobaYiN019PkySvjV",
    "Elli":   "MF3mGyEYCl7XYWbV9V6O",
    "Josh":   "TxGEqnHWrfWFTfGW9XjX",
}


@app.post("/api/tts")
async def text_to_speech(
    api_key: str = Form(...),
    text: str = Form(...),
    voice_name: str = Form("Rachel"),
    stability: float = Form(0.5),
    similarity_boost: float = Form(0.75),
):
    voice_id = ELEVENLABS_VOICE_IDS.get(voice_name, "21m00Tcm4TlvDq8ikWAM")
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
        },
    }
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers=headers,
            json=payload,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        audio_bytes = resp.content

    filename = f"tts_{uuid.uuid4()}.mp3"
    dest = OUTPUTS_DIR / filename
    dest.write_bytes(audio_bytes)
    return {"audio_url": f"/outputs/{filename}", "filename": filename}


@app.post("/api/generate-image")
async def generate_image(
    api_key: str = Form(...),
    model_key: str = Form(...),
    prompt: str = Form(...),
    size: str = Form("1:1"),
    n: int = Form(1),
):
    model = IMAGE_MODELS.get(model_key)
    if not model:
        raise HTTPException(status_code=400, detail="Modelo de imagen no encontrado")
    try:
        result = await siray_generate_image(api_key, model["id"], prompt, size, n)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    task_id = (result.get("data") or {}).get("task_id") or result.get("task_id") or result.get("id", "")
    return {"task_id": task_id, "status": "processing"}


@app.get("/api/image-status/{task_id}")
async def image_task_status(task_id: str, api_key: str):
    try:
        result = await siray_image_status(api_key, task_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    data = result.get("data") or {}
    status = data.get("status", result.get("status", "unknown"))
    outputs = data.get("outputs") or []
    image_url = outputs[0] if outputs else None

    return {"status": status, "image_url": image_url, "outputs": outputs, "raw": result}


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

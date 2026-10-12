"""
Video Workflow - Mini app para generación de video IA
Soporta Siray (Wan 3.0, Seedance, Kling) y escalado via fal.ai
"""

import asyncio
import json
import os
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
    "wan3-i2v": {
        "id": "alibaba/wan-3.0-i2v",
        "name": "Wan 3.0",
        "badge": "RECOMENDADO",
        "description": "Cámara compleja, diálogo, manos, varias personas. Calidad top.",
        "max_duration": 15,
        "price_per_sec": 0.040,
        "resolution": ["480p", "720p"],
        "needs_image": True,
    },
    "wan3-i2v-spicy": {
        "id": "alibaba/wan-3.0-i2v-spicy",
        "name": "Wan 3.0 Spicy",
        "badge": "",
        "description": "Igual que Wan 3.0 pero sin restricciones de contenido.",
        "max_duration": 15,
        "price_per_sec": 0.045,
        "resolution": ["480p", "720p", "1080p"],
        "needs_image": True,
    },
    "seedance-i2v": {
        "id": "bytedance/seedance-1-0-lite-i2v-250528",
        "name": "Seedance Edit",
        "badge": "",
        "description": "Movimientos de cámara complejos y físicas difíciles.",
        "max_duration": 10,
        "price_per_sec": 0.134,
        "resolution": ["480p", "720p"],
        "needs_image": True,
    },
    "kling-i2v": {
        "id": "kling/kling-v2-0-master-i2v",
        "name": "Kling Motion Control",
        "badge": "",
        "description": "Bailes, cámara fija y movimiento corporal limpio.",
        "max_duration": 10,
        "price_per_sec": 0.090,
        "resolution": ["720p"],
        "needs_image": True,
    },
    "wan3-ref2v": {
        "id": "alibaba/wan-3.0-ref2v",
        "name": "Wan 3.0 Ref2V",
        "badge": "VIDEO REF",
        "description": "Generá video animando desde un video de referencia. Ideal para clonar movimientos.",
        "max_duration": 15,
        "price_per_sec": 0.040,
        "resolution": ["480p", "720p"],
        "needs_image": True,
        "needs_ref_video": True,
    },
}

UPSCALE_PRICE_PER_SEC = 0.0072  # fal.ai ByteDance upscaler 1080p/30fps


# ─── API de Siray ───────────────────────────────────────────────────────────

async def siray_generate(api_key: str, model_id: str, image_url: str, prompt: str, duration: int, resolution: str, ref_video_url: Optional[str] = None) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    input_payload: dict = {
        "image": image_url,
        "prompt": prompt,
        "duration": duration,
        "resolution": resolution,
    }
    if ref_video_url:
        input_payload["reference_video"] = ref_video_url
    payload = {"model": model_id, "input": input_payload}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post("https://api.siray.ai/v1/video/generate", headers=headers, json=payload)
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=resp.text)
        return resp.json()


async def siray_status(api_key: str, task_id: str) -> dict:
    headers = {"Authorization": f"Bearer {api_key}"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"https://api.siray.ai/v1/tasks/{task_id}", headers=headers)
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
        return data.get("balance", 0.0)


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

    task_id = result.get("task_id") or result.get("id", "")
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

    status = result.get("status", "unknown")
    video_url = result.get("output", {}).get("video_url") or result.get("video_url")

    if video_url and status == "completed":
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


@app.get("/uploads/{filename}")
async def serve_upload(filename: str):
    path = UPLOADS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(path)


# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

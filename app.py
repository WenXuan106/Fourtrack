"""
Fourtrack server backend.

A small FastAPI service that runs the real, official Demucs model
(https://github.com/facebookresearch/demucs) on the server and returns
four separated stems (drums, bass, other, vocals) as base64-encoded WAV
audio in a JSON response.

This exists for one reason: some devices (notably iPad/iPhone Safari)
can't reliably run the ~170MB neural network in-browser without risking
a tab crash from hitting the OS memory ceiling. Running it here instead
trades that risk for the one thing the in-browser AI mode was built to
avoid — your audio leaves the device and is sent to wherever you deploy
this. It is only ever sent to *your own* deployment of this file, not to
any service run by Anthropic or a third party.

Deployment: see README.md for step-by-step Hugging Face Spaces instructions.
"""

import base64
import io
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(title="Fourtrack Server Backend")

# Wide open by default so your Fourtrack page (hosted anywhere, including
# as a local file) can call this. Tighten allow_origins to your own
# domain if you deploy Fourtrack somewhere fixed and want to lock it down.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

MAX_UPLOAD_BYTES = 60 * 1024 * 1024  # 60MB — generous for a compressed song, keeps memory sane
_separator = None  # lazy-loaded on first request, then reused


def get_separator():
    """Load the Demucs model once and reuse it across requests.

    Segment length and worker count are tunable via env vars so this can be
    squeezed onto low-RAM free-tier hosts (e.g. Render's 512MB free plan) by
    processing shorter chunks at a time — slower, but a smaller peak memory
    footprint. Leave unset to use Demucs's own defaults.
    """
    global _separator
    if _separator is None:
        import torch
        from demucs.api import Separator

        device = "cuda" if torch.cuda.is_available() else "cpu"
        segment = os.environ.get("DEMUCS_SEGMENT")
        jobs = int(os.environ.get("DEMUCS_JOBS", "0"))
        _separator = Separator(
            model="htdemucs",
            device=device,
            progress=False,
            segment=int(segment) if segment else None,
            jobs=jobs,
        )
    return _separator


def tensor_to_wav_base64(wav_tensor, samplerate: int) -> str:
    """Encode a Demucs output tensor as a WAV file, base64-encoded for JSON transport."""
    from demucs.api import save_audio

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        save_audio(wav_tensor, tmp_path, samplerate=samplerate)
        data = Path(tmp_path).read_bytes()
        return base64.b64encode(data).decode("ascii")
    finally:
        os.unlink(tmp_path)


@app.get("/")
def health():
    return {
        "status": "ok",
        "message": "Fourtrack server backend is running. POST an audio file to /separate.",
    }


@app.post("/separate")
async def separate(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "No file provided.")

    suffix = Path(file.filename).suffix or ".mp3"
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File too large — limit is {MAX_UPLOAD_BYTES // (1024*1024)}MB.")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        try:
            separator = get_separator()
        except Exception as e:
            raise HTTPException(500, f"Could not load the Demucs model: {e}")

        try:
            _original, separated = separator.separate_audio_file(tmp_path)
        except Exception as e:
            raise HTTPException(422, f"Could not process this audio file: {e}")

        samplerate = separator.samplerate
        stems = {
            name: tensor_to_wav_base64(tensor, samplerate)
            for name, tensor in separated.items()
        }
        return JSONResponse({"stems": stems, "sample_rate": samplerate})
    finally:
        os.unlink(tmp_path)

---
title: Fourtrack Server Backend
emoji: 🎚️
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# Fourtrack server backend

A small server that runs the real, official [Demucs](https://github.com/facebookresearch/demucs)
model (Meta's htdemucs) and returns four separated stems — drums, bass,
other, vocals — as WAV audio.

**Why this exists:** the in-browser "Demucs AI" mode in Fourtrack can crash
on memory-constrained devices like iPad/iPhone Safari, because it has to
hold the ~170MB model plus four full-length stems in the tab's memory at
once. Running the model here instead avoids that entirely — your device
just uploads a file and downloads a result. The tradeoff, stated plainly:
your audio *does* leave your device and gets sent to wherever you run
this. It only goes to your own deployment, not to Anthropic or anyone
else — but it is a real upload, unlike Fourtrack's other two modes.

## Option A: Render (free, always-online — real, but RAM is tight)

Render currently offers a genuine free tier for Docker web services — no
credit card, stays deployed indefinitely (with cold-start sleep after
15 minutes idle). This is the closest thing to "free and online" that
exists right now.

**The honest catch:** Render's free tier gives 512MB of RAM. PyTorch +
Demucs is a heavy stack, and I can't test against Render's actual
infrastructure from where I'm building this — so I can't promise it fits.
I've done what I can to give it the best shot (the Dockerfile installs
the small CPU-only build of PyTorch instead of the multi-GB GPU build,
and `app.py` supports a `DEMUCS_SEGMENT` environment variable that
processes shorter audio chunks at a time to reduce peak memory, at some
cost to speed). If it still runs out of memory, Option B is the
guaranteed-to-fit fallback.

1. Create a free account at [render.com](https://render.com) — no card needed.
2. **New → Web Service**, connect this folder as a repo (push it to a new GitHub repo first — Render deploys from Git, not a direct file upload).
3. Render should auto-detect the `Dockerfile`. Confirm **Instance Type: Free**.
4. Under **Environment**, optionally add `DEMUCS_SEGMENT` = `8` from the start — worth trying preemptively given the RAM ceiling.
5. Deploy. First build takes a few minutes (installing PyTorch).
6. Once live, your URL is `https://<your-service-name>.onrender.com`. Paste that into Fourtrack's "Server backend" field.
7. If the first real request fails or the deploy log shows it being OOM-killed, that's the 512MB limit — move to Option B.

## Option B: Hugging Face Spaces (paid, but reliably fits — $9/mo)

Hugging Face Spaces used to have a free Docker tier; as of this writing
they require a **PRO plan ($9/month)** to create a Docker Space at all,
even on their free CPU hardware. More RAM than Render's free tier, so
this is the "just make it work, I don't want to fight memory limits"
option.

1. Subscribe to [Hugging Face PRO](https://huggingface.co/pricing).
2. Profile picture → **New Space** → **Docker** SDK → **CPU basic** hardware.
3. Upload `app.py`, `requirements.txt`, `Dockerfile`, this `README.md`.
4. Wait for the build (**Logs** tab), then your URL is `https://<username>-<space-name>.hf.space`.
5. Free-tier CPU is slow (minutes per song) and sleeps after inactivity — normal, not broken.

## Option C: run it on your own computer (free, but only on your home network)

No hosting account at all — your iPad talks directly to your computer
over WiFi. Doesn't work away from home, but nothing ever leaves your own
devices, and there's no RAM ceiling to worry about beyond your computer's.

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

Find your computer's local IP (Mac: System Settings → Wi-Fi → Details;
Windows: `ipconfig`), then on your iPad (same WiFi) point Fourtrack's
"Server backend" field at `http://<that-ip>:8000`. Leave the terminal
running while you use it.

## Notes

- `allow_origins=["*"]` in `app.py` means anyone with your server's
  address can use it. Fine for personal use; lock it down if you deploy
  somewhere publicly discoverable.
- The Demucs model downloads on first request and is cached in memory
  after that — only the very first song after a cold start is slow to begin.
- This landscape (free tiers, pricing) changes often — I verified what's
  written here via search rather than assuming, but check current pricing
  before committing time to any option.

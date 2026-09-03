FROM python:3.11-slim

# ffmpeg is needed as a fallback audio decoder for formats demucs's
# primary reader (sphn) doesn't handle.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Run as non-root — required by Hugging Face Spaces, good practice everywhere else.
RUN useradd -m -u 1000 appuser

WORKDIR /app
RUN chown appuser:appuser /app

USER appuser
ENV HOME=/home/appuser \
    PATH=/home/appuser/.local/bin:$PATH

# Install the CPU-only PyTorch build explicitly, before demucs pulls in its
# own torch dependency. The default PyPI build of torch targets GPUs and is
# several times larger and heavier at runtime — not what a free-tier
# container with limited RAM (Render's free tier: 512MB) needs.
RUN pip install --no-cache-dir --user torch --index-url https://download.pytorch.org/whl/cpu

COPY --chown=appuser requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

COPY --chown=appuser app.py .

# Hugging Face Spaces expects port 7860. Render (and most other hosts) set
# a $PORT environment variable and expect the app to listen on it. This
# supports both: falls back to 7860 if $PORT isn't set.
EXPOSE 7860
CMD ["sh", "-c", "python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-7860}"]

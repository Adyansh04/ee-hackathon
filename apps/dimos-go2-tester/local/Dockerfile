FROM python:3.12-slim-bookworm

SHELL ["/bin/bash", "-lc"]

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy \
    DATA_DIR=/data/dimos \
    DIMOS_MODE=basic \
    DIMOS_PORT=7779

RUN apt-get update && apt-get install -y --no-install-recommends \
      bash \
      build-essential \
      ca-certificates \
      curl \
      ffmpeg \
      git \
      git-lfs \
      iproute2 \
      iputils-ping \
      libegl1 \
      libgl1 \
      libglib2.0-0 \
      libgomp1 \
      net-tools \
      portaudio19-dev \
      procps \
      tini \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --upgrade pip uv \
    && uv pip install --system "dimos[base,unitree]" \
    && uv pip install --system --upgrade "unitree-webrtc-connect==2.1.2"

WORKDIR /app

COPY dimos/patch_dimos_runtime.py /tmp/patch_dimos_runtime.py
COPY dimos/entrypoint.sh /app/entrypoint.sh
COPY dimos/healthcheck.sh /app/healthcheck.sh

RUN python /tmp/patch_dimos_runtime.py \
    && rm /tmp/patch_dimos_runtime.py \
    && chmod +x /app/entrypoint.sh /app/healthcheck.sh \
    && mkdir -p /data/dimos /root/.cache

EXPOSE 7779

ENTRYPOINT ["/usr/bin/tini", "--", "/app/entrypoint.sh"]

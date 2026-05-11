ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base-python:latest
FROM ${BUILD_FROM}

# ---------------------------------------------------------------------------
# System dependencies for dlib / OpenCV / face_recognition
# Alpine-based HA base images use apk
# ---------------------------------------------------------------------------
RUN apk add --no-cache \
    cmake \
    g++ \
    make \
    python3-dev \
    py3-pip \
    libffi-dev \
    openblas-dev \
    lapack-dev \
    libpng-dev \
    libjpeg-turbo-dev \
    libstdc++ \
    curl \
    bash

# ---------------------------------------------------------------------------
# Python dependencies – install heavy ML libs FIRST (better layer caching)
# ---------------------------------------------------------------------------
WORKDIR /app
COPY app/requirements.txt /app/requirements.txt

RUN pip3 install --no-cache-dir \
    --extra-index-url https://www.piwheels.org/simple \
    -r requirements.txt

# ---------------------------------------------------------------------------
# Application code
# ---------------------------------------------------------------------------
COPY app/ /app/

# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]

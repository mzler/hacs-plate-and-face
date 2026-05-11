ARG BUILD_FROM=ghcr.io/home-assistant/aarch64-base-debian:bookworm
FROM ${BUILD_FROM}

# Install pre-compiled system packages to avoid building from source
RUN apt-get update && apt-get install -y --no-install-recommends \
    cmake \
    g++ \
    make \
    python3-pip \
    python3-setuptools \
    python3-wheel \
    python3-dev \
    python3-numpy \
    python3-opencv \
    python3-pillow \
    libopenblas-dev \
    liblapack-dev \
    libjpeg-dev \
    libpng-dev \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY addons/plate_face_recognition/app/requirements.txt /app/requirements.txt

# Install remaining python packages
# We use --break-system-packages for Debian Bookworm compliance
RUN pip3 install --no-cache-dir --break-system-packages \
    fastapi \
    uvicorn[standard] \
    python-multipart \
    dlib \
    face_recognition \
    easyocr

COPY addons/plate_face_recognition/app/ /app/
COPY addons/plate_face_recognition/run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]

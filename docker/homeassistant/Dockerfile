FROM ghcr.io/home-assistant/home-assistant:stable

# Build-Tools und Python-Dependencies vorinstallieren
# damit face_recognition (dlib) und easyocr beim ersten Start direkt verfügbar sind
RUN apk add --no-cache \
    cmake \
    make \
    g++ \
    gcc \
    musl-dev \
    python3-dev \
    openblas-dev \
    libstdc++ \
    jpeg-dev \
    zlib-dev \
    libffi-dev \
    openssl-dev \
    && pip install --no-cache-dir \
        "dlib==19.24.4" \
        "face_recognition==1.3.0" \
        "opencv-python-headless==4.9.0.80" \
        "easyocr==1.7.1" \
        "numpy>=1.21.0"

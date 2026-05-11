FROM ghcr.io/home-assistant/aarch64-base-debian:bookworm

# System dependencies for dlib / OpenCV / face_recognition
RUN apt-get update && apt-get install -y --no-install-recommends     cmake     g++     make     python3-dev     python3-pip     python3-setuptools     libffi-dev     libopenblas-dev     liblapack-dev     libpng-dev     libjpeg-dev     libssl-dev     curl     && apt-get clean     && rm -rf /var/lib/apt/lists/*

# Upgrade build tools to avoid 'BackendUnavailable' errors
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel

WORKDIR /app
COPY app/requirements.txt /app/requirements.txt

# Install dependencies - prefer binaries to save time/RAM on HA Yellow
RUN pip3 install --no-cache-dir --prefer-binary -r requirements.txt

COPY app/ /app/
COPY run.sh /run.sh
RUN chmod a+x /run.sh

CMD ["/run.sh"]

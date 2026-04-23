FROM python:3.11-slim

RUN pip install --no-cache-dir Pillow

WORKDIR /app
COPY mjpeg_server.py .

EXPOSE 8554

CMD ["python", "mjpeg_server.py"]

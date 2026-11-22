FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FK_DATA_DIR=/data \
    FK_REFERENCE_DIR=/app/reference

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

RUN mkdir -p /opt/models \
    && for m in face_detection_yunet/face_detection_yunet_2023mar.onnx \
                face_recognition_sface/face_recognition_sface_2021dec.onnx; do \
         curl -fsSL --retry 5 --retry-delay 3 --retry-all-errors -o /opt/models/$(basename $m) \
           https://github.com/opencv/opencv_zoo/raw/main/models/$m \
         || { echo "WARN: could not download $m"; rm -f /opt/models/$(basename $m); }; \
       done \
    && python -c "from rapidocr_onnxruntime import RapidOCR; RapidOCR()"

COPY app ./app
COPY reference ./reference
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

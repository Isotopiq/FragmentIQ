FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends openjdk-21-jre-headless curl git && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-engines.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-engines.txt
# onnxruntime wheels up to 1.15.x ship with an executable-stack bit that glibc 2.41+ refuses to load.
# patchelf clears the bit so ms2query can import inside the container.
RUN apt-get update && apt-get install -y --no-install-recommends patchelf && \
    find /usr/local/lib/python*/site-packages/onnxruntime/capi -name "*.so" -exec patchelf --clear-execstack {} + && \
    rm -rf /var/lib/apt/lists/*
COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

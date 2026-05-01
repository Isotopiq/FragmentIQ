FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends default-jre-headless curl && rm -rf /var/lib/apt/lists/*
CMD ["python", "-c", "print('MZmine worker image ready. Mount MZmine and set MZMINE_BINARY for real execution.')"]

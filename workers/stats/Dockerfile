FROM python:3.11-slim

WORKDIR /app
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
CMD ["python", "-c", "print('FragmentIQ stats/reporting worker placeholder - use backend job service in MVP')"]

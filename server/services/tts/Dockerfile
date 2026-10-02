FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY tts_service ./tts_service
ENV PYTHONPATH=/app
EXPOSE 8102
CMD ["python", "-m", "tts_service.main"]

FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY asr_service ./asr_service
ENV PYTHONPATH=/app
EXPOSE 8101
CMD ["python", "-m", "asr_service.main"]

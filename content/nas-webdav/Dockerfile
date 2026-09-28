FROM python:3.12-slim
WORKDIR /app
COPY bridge.py webdav_client.py source.json ./
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
EXPOSE 8766
CMD ["python", "bridge.py", "--bind", "0.0.0.0"]

FROM python:3.12-alpine

WORKDIR /app

COPY backend/tests/trajectory_builder/server.py .
COPY backend/tests/trajectory_builder/ui ./ui

EXPOSE 80

CMD ["python", "server.py"]

FROM python:3.12-alpine

WORKDIR /app

COPY backend/tests/trajectory_builder/server.py .
COPY backend/tests/trajectory_builder/ui ./ui

ENV PORT=8080

USER 1000:1000

EXPOSE 8080

CMD ["python", "server.py"]

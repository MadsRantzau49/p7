FROM python:3.12-alpine

WORKDIR /app

COPY backend/tests/trajectory_builder ./trajectory_builder

EXPOSE 80

CMD ["python", "-m", "trajectory_builder.server"]

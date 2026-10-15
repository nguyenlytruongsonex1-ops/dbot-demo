FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt requirements-worker.txt ./
ARG WITH_CREWAI=0
RUN pip install --no-cache-dir -r requirements.txt && \
    if [ "$WITH_CREWAI" = "1" ]; then pip install --no-cache-dir -r requirements-worker.txt; fi
COPY app ./app
COPY knowledge ./knowledge
ENV PYTHONUNBUFFERED=1

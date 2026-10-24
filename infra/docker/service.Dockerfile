# Imagem única para todos os serviços Python. Build a partir da raiz do repo:
#   docker build -f infra/docker/service.Dockerfile --build-arg SERVICE=query -t morbidus-query .
FROM python:3.12-slim

ARG SERVICE
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PACKAGE=${SERVICE}_svc

RUN useradd --create-home --uid 10001 morbidus
WORKDIR /app

COPY libs/morbidus-common /libs/morbidus-common
RUN pip install /libs/morbidus-common

COPY services/${SERVICE}/requirements.txt ./requirements.txt
RUN pip install -r requirements.txt

COPY services/${SERVICE}/${SERVICE}_svc ./${SERVICE}_svc

USER morbidus
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"
CMD uvicorn --factory ${PACKAGE}.main:build_app --host 0.0.0.0 --port 8000

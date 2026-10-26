FROM python:3.11-slim@sha256:b7a9e5f6a93d6d4a31f129bbd4bdee69efccb6ded0fb230d78aafaf37af98377
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt
RUN useradd --uid 10001 --create-home laus && mkdir /state && chown laus:laus /state
COPY --chown=laus:laus . .
USER laus
CMD ["python", "-m", "core_jarvis.worker"]

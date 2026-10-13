FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock.txt requirements.lock.txt
RUN pip install --no-cache-dir -r requirements.lock.txt gunicorn==23.0.0
COPY . .
RUN useradd --create-home app && mkdir -p private-media && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]

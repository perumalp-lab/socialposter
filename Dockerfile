FROM python:3.12-slim

RUN groupadd --system app && useradd --system --gid app --home /data app

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .

RUN mkdir -p /data/.socialposter && chown -R app:app /data

USER app
ENV HOME=/data

EXPOSE 5000

CMD ["gunicorn", "socialposter.web.app:create_app()", "--bind", "0.0.0.0:5000", "--workers", "2"]

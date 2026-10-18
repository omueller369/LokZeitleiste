FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core && rm -rf /var/lib/apt/lists/*
ENV LOKZEITLEISTE_FILES_ROOT=/user-files
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY lokzeitleiste ./lokzeitleiste
RUN useradd --system --uid 10001 appuser && chown -R appuser:appuser /srv \
    && mkdir -p /user-files/TF /user-files/VW \
    && chown -R appuser:appuser /user-files && chmod 700 /user-files /user-files/TF /user-files/VW
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "python -m lokzeitleiste.init_db && uvicorn lokzeitleiste.main:app --host 0.0.0.0 --port 8000"]

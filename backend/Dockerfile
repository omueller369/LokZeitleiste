FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY lokzeitleiste ./lokzeitleiste
RUN useradd --system --uid 10001 appuser && chown -R appuser:appuser /srv
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "python -m lokzeitleiste.init_db && uvicorn lokzeitleiste.main:app --host 0.0.0.0 --port 8000"]

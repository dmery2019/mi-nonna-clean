FROM python:3.11-slim

# Railway deployment - environment variables set via Railway dashboard
# Cache buster: 2026-09-19 0238
WORKDIR /app

# Copiar archivos
COPY requirements.txt .
COPY run_bot.py .
COPY src/ src/
COPY data/ data/
COPY scripts/ scripts/

# Instalar dependencias
RUN pip uninstall -y openpyxl 2>/dev/null || true && \
    pip install --no-cache-dir -r requirements.txt && \
    pip uninstall -y openpyxl 2>/dev/null || true

# Ejecutar bot
CMD ["python", "run_bot.py"]

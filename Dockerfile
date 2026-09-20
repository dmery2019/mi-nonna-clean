FROM python:3.11-slim

WORKDIR /app

# Copiar archivos
COPY requirements.txt .
COPY run_bot.py .
COPY src/ src/
COPY data/ data/
COPY scripts/ scripts/

# Crear directorio de logs
RUN mkdir -p /app/logs

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Ejecutar bot
CMD ["python", "run_bot.py"]

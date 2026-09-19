"""
Script para ejecutar el bot de manera sencilla
"""
import sys
import os
from pathlib import Path

# Agregar el directorio src al path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Crear carpeta de datos si no existe
data_dir = Path(__file__).parent / 'data'
data_dir.mkdir(exist_ok=True)

from bot import main

if __name__ == "__main__":
    try:
        print("🍕 Iniciando Bot de Ventas Nonna...")
        print("Presiona Ctrl+C para detener\n")
        main()
    except KeyboardInterrupt:
        print("\n\nBot detenido por el usuario")


#!/usr/bin/env python3
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

BACKUP_DIR = r"C:\Users\dougl\projects\mi-nonna\data\backups"
backup_dir_path = Path(BACKUP_DIR)

# Ensure directory exists
backup_dir_path.mkdir(parents=True, exist_ok=True)

# List current backups
print("=== Backups actuales ===")
backup_files = sorted(backup_dir_path.glob("ventas_backup_*.db"))
for bf in backup_files:
    size_kb = bf.stat().st_size / 1024
    print(f"{bf.name} - {size_kb:.1f} KB")

# Calculate deletion threshold (older than 5 days)
five_days_ago = datetime.now() - timedelta(days=5)
deleted_count = 0
deleted_files = []

print("\n=== Eliminando backups > 5 días ===")
for bf in backup_files:
    mtime = datetime.fromtimestamp(bf.stat().st_mtime)
    if mtime < five_days_ago:
        deleted_files.append(bf.name)
        bf.unlink()
        deleted_count += 1
        print(f"Eliminado: {bf.name}")

if deleted_count == 0:
    print("(Sin archivos para eliminar)")

# Get final stats
remaining_files = sorted(backup_dir_path.glob("ventas_backup_*.db"))
total_size_bytes = sum(f.stat().st_size for f in remaining_files)
total_size_mb = total_size_bytes / (1024 * 1024)

print(f"\n=== Resultado final ===")
print(f"Archivos en backup: {len(remaining_files)}")
print(f"Tamaño total: {total_size_mb:.2f} MB")
print(f"Archivos eliminados: {deleted_count}")

# Show remaining backups
print(f"\n=== Backups restantes ===")
for bf in remaining_files:
    size_kb = bf.stat().st_size / 1024
    mtime = datetime.fromtimestamp(bf.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    print(f"{bf.name} - {size_kb:.1f} KB - {mtime}")

# Export values for final report
print(f"\n[REPORT]")
exec_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
print(f"EXEC_TIME={exec_time}")
print(f"TOTAL_FILES={len(remaining_files)}")
print(f"TOTAL_SIZE_MB={total_size_mb:.2f}")
print(f"DELETED_COUNT={deleted_count}")

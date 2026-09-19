"""
Script de inicialización de base de datos
Crea las tablas y los productos iniciales
"""
import logging
from database import Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def main():
    """Inicializa la base de datos con productos"""
    logger.info("Iniciando base de datos...")
    
    db = Database()
    
    # Productos iniciales
    productos_iniciales = [
        ("Empanada de Pino", "empanada", 1500),
        ("Empanada de Mechada", "empanada", 1500),
        ("Empanada de Champiñón", "empanada", 1800),
        ("Pan de Masa Madre", "pan", 3000),
    ]
    
    logger.info("Creando productos iniciales...")
    
    # Verificar si ya existen productos
    productos_existentes = db.obtener_productos()
    
    if productos_existentes:
        logger.info(f"Ya existen {len(productos_existentes)} productos en la BD")
        print("\n📦 Productos existentes:")
        for p in productos_existentes:
            print(f"  • {p.nombre} ({p.tipo}) - ${p.precio_base:,}")
    else:
        for nombre, tipo, precio in productos_iniciales:
            db.crear_producto(nombre, tipo, precio)
        
        logger.info("✅ Base de datos inicializada correctamente")
        print("\n✅ Base de datos creada con productos:")
        for nombre, tipo, precio in productos_iniciales:
            print(f"  • {nombre} ({tipo}) - ${precio:,}")
    
    print(f"\n📍 Base de datos ubicada en: {db.db_path.absolute()}")


if __name__ == "__main__":
    main()

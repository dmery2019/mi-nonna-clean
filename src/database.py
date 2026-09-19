"""
Gestión de base de datos SQLite para ventas Nonna
"""
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional
from contextlib import contextmanager

from models import Cliente, Producto, Pedido, DetallePedido

logger = logging.getLogger(__name__)


class Database:
    """Clase para manejar la base de datos SQLite"""
    
    def __init__(self, db_path: str = "data/ventas.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    @contextmanager
    def get_connection(self):
        """Context manager para conexiones a la base de datos"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Error en transacción BD: {e}")
            raise
        finally:
            conn.close()
    
    def _init_db(self):
        """Inicializa las tablas de la base de datos"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Tabla de clientes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    telefono TEXT,
                    telegram_user_id INTEGER UNIQUE NOT NULL,
                    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Tabla de productos
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS productos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    tipo TEXT NOT NULL,
                    precio_base INTEGER NOT NULL
                )
            """)
            
            # Tabla de pedidos
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pedidos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    numero_pedido TEXT UNIQUE NOT NULL,
                    cliente_id INTEGER NOT NULL,
                    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    subtotal INTEGER NOT NULL,
                    iva INTEGER DEFAULT 0,
                    recargo INTEGER DEFAULT 0,
                    total INTEGER NOT NULL,
                    aplica_iva BOOLEAN DEFAULT 0,
                    nota_recargo TEXT,
                    estado_entregado BOOLEAN DEFAULT 0,
                    fecha_entregado TIMESTAMP,
                    estado_pagado BOOLEAN DEFAULT 0,
                    fecha_pagado TIMESTAMP,
                    FOREIGN KEY (cliente_id) REFERENCES clientes(id)
                )
            """)
            
            # Agregar columnas si no existen (para BDs existentes)
            try:
                cursor.execute("ALTER TABLE pedidos ADD COLUMN estado_entregado BOOLEAN DEFAULT 0")
            except sqlite3.OperationalError:
                pass  # Columna ya existe
            
            try:
                cursor.execute("ALTER TABLE pedidos ADD COLUMN fecha_entregado TIMESTAMP")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE pedidos ADD COLUMN estado_pagado BOOLEAN DEFAULT 0")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE pedidos ADD COLUMN fecha_pagado TIMESTAMP")
            except sqlite3.OperationalError:
                pass
            
            # Tabla de detalle de pedidos
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS detalle_pedidos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pedido_id INTEGER NOT NULL,
                    producto_id INTEGER NOT NULL,
                    cantidad INTEGER NOT NULL,
                    precio_unitario INTEGER NOT NULL,
                    subtotal INTEGER NOT NULL,
                    FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
                    FOREIGN KEY (producto_id) REFERENCES productos(id)
                )
            """)
            
            # Índices para mejorar rendimiento
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pedidos_fecha ON pedidos(fecha)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_pedidos_cliente ON pedidos(cliente_id)")
            
            logger.info("Base de datos inicializada correctamente")
    
    # === CLIENTES ===
    
    def crear_cliente(self, nombre: str, telefono: str, telegram_user_id: int) -> Optional[int]:
        """Crea un nuevo cliente"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO clientes (nombre, telefono, telegram_user_id) VALUES (?, ?, ?)",
                    (nombre, telefono, telegram_user_id)
                )
                logger.info(f"Cliente creado: {nombre} (ID: {cursor.lastrowid})")
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            logger.warning(f"Cliente ya existe con telegram_user_id: {telegram_user_id}")
            return None
    
    def obtener_cliente_por_telegram(self, telegram_user_id: int) -> Optional[Cliente]:
        """Obtiene un cliente por su ID de Telegram"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clientes WHERE telegram_user_id = ?", (telegram_user_id,))
            row = cursor.fetchone()
            if row:
                return Cliente(
                    id=row['id'],
                    nombre=row['nombre'],
                    telefono=row['telefono'],
                    telegram_user_id=row['telegram_user_id'],
                    fecha_registro=datetime.fromisoformat(row['fecha_registro'])
                )
            return None
    
    def obtener_cliente_por_id(self, cliente_id: int) -> Optional[Cliente]:
        """Obtiene un cliente por su ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,))
            row = cursor.fetchone()
            if row:
                return Cliente(
                    id=row['id'],
                    nombre=row['nombre'],
                    telefono=row['telefono'],
                    telegram_user_id=row['telegram_user_id'],
                    fecha_registro=datetime.fromisoformat(row['fecha_registro'])
                )
            return None

    def obtener_cliente_por_id(self, cliente_id: int) -> Optional[Cliente]:
        """Obtiene un cliente por su ID interno"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,))
            row = cursor.fetchone()
            if row:
                return Cliente(
                    id=row['id'],
                    nombre=row['nombre'],
                    telefono=row['telefono'],
                    telegram_user_id=row['telegram_user_id'],
                    fecha_registro=datetime.fromisoformat(row['fecha_registro'])
                )
            return None

    def buscar_clientes(self, texto: str) -> List[Cliente]:
        """Busca clientes por nombre o telefono (parcial)"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            like = f"%{texto}%"
            cursor.execute(
                "SELECT * FROM clientes WHERE nombre LIKE ? OR telefono LIKE ? ORDER BY nombre",
                (like, like)
            )
            rows = cursor.fetchall()
            return [
                Cliente(
                    id=row['id'],
                    nombre=row['nombre'],
                    telefono=row['telefono'],
                    telegram_user_id=row['telegram_user_id'],
                    fecha_registro=datetime.fromisoformat(row['fecha_registro'])
                )
                for row in rows
            ]

    def listar_clientes(self) -> List[Cliente]:
        """Lista todos los clientes ordenados por nombre"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clientes ORDER BY nombre")
            rows = cursor.fetchall()
            return [
                Cliente(
                    id=row['id'],
                    nombre=row['nombre'],
                    telefono=row['telefono'],
                    telegram_user_id=row['telegram_user_id'],
                    fecha_registro=datetime.fromisoformat(row['fecha_registro'])
                )
                for row in rows
            ]

    def actualizar_cliente(self, cliente_id: int, nombre: str, telefono: str) -> bool:
        """Actualiza nombre y telefono de un cliente"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE clientes SET nombre = ?, telefono = ? WHERE id = ?",
                    (nombre, telefono, cliente_id)
                )
                logger.info(f"Cliente actualizado ID={cliente_id}: {nombre}")
                return True
        except Exception as e:
            logger.error(f"Error al actualizar cliente: {e}")
            return False
    
    # === PRODUCTOS ===
    
    def crear_producto(self, nombre: str, tipo: str, precio_base: int) -> int:
        """Crea un nuevo producto"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO productos (nombre, tipo, precio_base) VALUES (?, ?, ?)",
                (nombre, tipo, precio_base)
            )
            logger.info(f"Producto creado: {nombre} (${precio_base})")
            return cursor.lastrowid
    
    def obtener_productos(self) -> List[Producto]:
        """Obtiene todos los productos"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM productos ORDER BY tipo, nombre")
            rows = cursor.fetchall()
            return [
                Producto(
                    id=row['id'],
                    nombre=row['nombre'],
                    tipo=row['tipo'],
                    precio_base=row['precio_base']
                )
                for row in rows
            ]
    
    def obtener_producto(self, producto_id: int) -> Optional[Producto]:
        """Obtiene un producto por ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM productos WHERE id = ?", (producto_id,))
            row = cursor.fetchone()
            if row:
                return Producto(
                    id=row['id'],
                    nombre=row['nombre'],
                    tipo=row['tipo'],
                    precio_base=row['precio_base']
                )
            return None
    
    # === PEDIDOS ===
    
    def generar_numero_pedido(self) -> str:
        """Genera un número de pedido único"""
        fecha_str = datetime.now().strftime("%Y%m%d")
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) as total FROM pedidos WHERE numero_pedido LIKE ?",
                (f"{fecha_str}-%",)
            )
            count = cursor.fetchone()['total']
            return f"{fecha_str}-{count + 1:04d}"
    
    def crear_pedido(
        self,
        cliente_id: int,
        items: List[dict],
        aplica_iva: bool = False,
        recargo: int = 0,
        nota_recargo: str = ""
    ) -> Optional[int]:
        """
        Crea un nuevo pedido con sus detalles
        items: [{'producto_id': int, 'cantidad': int, 'precio_unitario': int}, ...]
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Calcular totales
                subtotal = sum(item['cantidad'] * item['precio_unitario'] for item in items)
                iva_monto = int(subtotal * 0.19) if aplica_iva else 0
                total = subtotal + iva_monto + recargo
                
                # Generar número de pedido
                numero_pedido = self.generar_numero_pedido()
                
                # Insertar pedido
                cursor.execute("""
                    INSERT INTO pedidos 
                    (numero_pedido, cliente_id, subtotal, iva, recargo, total, aplica_iva, nota_recargo)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (numero_pedido, cliente_id, subtotal, iva_monto, recargo, total, aplica_iva, nota_recargo))
                
                pedido_id = cursor.lastrowid
                
                # Insertar detalles del pedido
                for item in items:
                    item_subtotal = item['cantidad'] * item['precio_unitario']
                    cursor.execute("""
                        INSERT INTO detalle_pedidos 
                        (pedido_id, producto_id, cantidad, precio_unitario, subtotal)
                        VALUES (?, ?, ?, ?, ?)
                    """, (pedido_id, item['producto_id'], item['cantidad'], item['precio_unitario'], item_subtotal))
                
                logger.info(f"Pedido creado: {numero_pedido} - Total: ${total:,}")
                return pedido_id
                
        except Exception as e:
            logger.error(f"Error al crear pedido: {e}")
            return None
    
    def obtener_pedidos_cliente(self, cliente_id: int, limit: int = 10) -> List[dict]:
        """Obtiene los últimos pedidos de un cliente"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM pedidos 
                WHERE cliente_id = ? 
                ORDER BY fecha DESC 
                LIMIT ?
            """, (cliente_id, limit))
            
            pedidos = []
            for row in cursor.fetchall():
                pedidos.append({
                    'id': row['id'],
                    'numero_pedido': row['numero_pedido'],
                    'fecha': row['fecha'],
                    'total': row['total']
                })
            return pedidos
    
    def obtener_detalle_pedido(self, pedido_id: int) -> dict:
        """Obtiene el detalle completo de un pedido"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Información del pedido
            cursor.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,))
            pedido_row = cursor.fetchone()
            
            if not pedido_row:
                return None
            
            # Detalles del pedido con productos
            cursor.execute("""
                SELECT dp.*, p.nombre as producto_nombre
                FROM detalle_pedidos dp
                JOIN productos p ON dp.producto_id = p.id
                WHERE dp.pedido_id = ?
            """, (pedido_id,))
            
            items = []
            for row in cursor.fetchall():
                items.append({
                    'producto': row['producto_nombre'],
                    'cantidad': row['cantidad'],
                    'precio_unitario': row['precio_unitario'],
                    'subtotal': row['subtotal']
                })
            
            return {
                'numero_pedido': pedido_row['numero_pedido'],
                'fecha': pedido_row['fecha'],
                'subtotal': pedido_row['subtotal'],
                'iva': pedido_row['iva'],
                'recargo': pedido_row['recargo'],
                'total': pedido_row['total'],
                'nota_recargo': pedido_row['nota_recargo'],
                'estado_entregado': pedido_row['estado_entregado'],
                'fecha_entregado': pedido_row['fecha_entregado'],
                'estado_pagado': pedido_row['estado_pagado'],
                'fecha_pagado': pedido_row['fecha_pagado'],
                'items': items
            }
    
    def obtener_pedidos_recientes(self, cliente_id: int, dias: int = 30) -> List[dict]:
        """Obtiene pedidos de un cliente de los últimos N días"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    id, 
                    numero_pedido, 
                    fecha, 
                    total,
                    estado_entregado,
                    fecha_entregado,
                    estado_pagado,
                    fecha_pagado
                FROM pedidos 
                WHERE cliente_id = ? 
                AND fecha >= datetime('now', '-' || ? || ' days')
                ORDER BY fecha DESC
            """, (cliente_id, dias))
            
            pedidos = []
            for row in cursor.fetchall():
                pedidos.append({
                    'id': row['id'],
                    'numero_pedido': row['numero_pedido'],
                    'fecha': row['fecha'],
                    'total': row['total'],
                    'estado_entregado': bool(row['estado_entregado']),
                    'fecha_entregado': row['fecha_entregado'],
                    'estado_pagado': bool(row['estado_pagado']),
                    'fecha_pagado': row['fecha_pagado']
                })
            return pedidos
    
    def actualizar_estado_entregado(self, pedido_id: int, estado: bool) -> bool:
        """Actualiza el estado de entrega de un pedido"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if estado:
                    # Marcar como entregado con fecha actual
                    cursor.execute("""
                        UPDATE pedidos 
                        SET estado_entregado = 1, fecha_entregado = CURRENT_TIMESTAMP 
                        WHERE id = ?
                    """, (pedido_id,))
                else:
                    # Desmarcar entrega
                    cursor.execute("""
                        UPDATE pedidos 
                        SET estado_entregado = 0, fecha_entregado = NULL 
                        WHERE id = ?
                    """, (pedido_id,))
                logger.info(f"Estado entregado actualizado para pedido {pedido_id}: {estado}")
                return True
        except Exception as e:
            logger.error(f"Error al actualizar estado entregado: {e}")
            return False
    
    def actualizar_estado_pagado(self, pedido_id: int, estado: bool) -> bool:
        """Actualiza el estado de pago de un pedido"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                if estado:
                    # Marcar como pagado con fecha actual
                    cursor.execute("""
                        UPDATE pedidos 
                        SET estado_pagado = 1, fecha_pagado = CURRENT_TIMESTAMP 
                        WHERE id = ?
                    """, (pedido_id,))
                else:
                    # Desmarcar pago
                    cursor.execute("""
                        UPDATE pedidos 
                        SET estado_pagado = 0, fecha_pagado = NULL 
                        WHERE id = ?
                    """, (pedido_id,))
                logger.info(f"Estado pagado actualizado para pedido {pedido_id}: {estado}")
                return True
        except Exception as e:
            logger.error(f"Error al actualizar estado pagado: {e}")
            return False
    
    def obtener_pedido_por_numero(self, numero_pedido: str) -> Optional[dict]:
        """Obtiene un pedido por su número"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pedidos WHERE numero_pedido = ?", (numero_pedido,))
            row = cursor.fetchone()
            if row:
                return {
                    'id': row['id'],
                    'numero_pedido': row['numero_pedido'],
                    'cliente_id': row['cliente_id'],
                    'fecha': row['fecha'],
                    'total': row['total'],
                    'estado_entregado': bool(row['estado_entregado']),
                    'fecha_entregado': row['fecha_entregado'],
                    'estado_pagado': bool(row['estado_pagado']),
                    'fecha_pagado': row['fecha_pagado']
                }
            return None

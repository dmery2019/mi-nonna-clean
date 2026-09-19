"""
Modelos de datos para el sistema de ventas Nonna
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Cliente:
    """Modelo de cliente"""
    id: Optional[int] = None
    nombre: str = ""
    telefono: str = ""
    telegram_user_id: int = 0
    fecha_registro: Optional[datetime] = None


@dataclass
class Producto:
    """Modelo de producto"""
    id: Optional[int] = None
    nombre: str = ""
    tipo: str = ""  # 'empanada' o 'pan'
    precio_base: int = 0  # En pesos chilenos


@dataclass
class Pedido:
    """Modelo de pedido"""
    id: Optional[int] = None
    numero_pedido: str = ""
    cliente_id: int = 0
    fecha: Optional[datetime] = None
    subtotal: int = 0
    iva: int = 0
    recargo: int = 0
    total: int = 0
    aplica_iva: bool = False
    nota_recargo: str = ""
    estado_entregado: bool = False
    fecha_entregado: Optional[datetime] = None
    estado_pagado: bool = False
    fecha_pagado: Optional[datetime] = None


@dataclass
class DetallePedido:
    """Modelo de detalle de pedido"""
    id: Optional[int] = None
    pedido_id: int = 0
    producto_id: int = 0
    cantidad: int = 0
    precio_unitario: int = 0
    subtotal: int = 0

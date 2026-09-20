"""
Generación de reportes para ventas Nonna
"""
import sqlite3
import io
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text


class Reportes:
    """Clase para generar reportes de ventas"""
    
    def __init__(self, db_path: str = "data/ventas.db"):
        self.db_path = Path(db_path)
        self.console = Console()
    
    def _get_connection(self):
        """Obtiene conexión a la base de datos"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _formatear_precio(self, precio: int) -> str:
        """Formatea un precio en CLP"""
        return f"${precio:,}".replace(",", ".")
    
    def reporte_diario(self, solo_datos: bool = False) -> Dict:
        """Genera reporte diario"""
        hoy = datetime.now()
        inicio = hoy.replace(hour=0, minute=0, second=0, microsecond=0)
        fin = hoy.replace(hour=23, minute=59, second=59, microsecond=999999)
        return self.reporte_periodo(inicio, fin)
    
    def reporte_semanal(self, solo_datos: bool = False) -> Dict:
        """Genera reporte semanal"""
        hoy = datetime.now()
        inicio = hoy - timedelta(days=hoy.weekday())
        inicio = inicio.replace(hour=0, minute=0, second=0, microsecond=0)
        fin = hoy.replace(hour=23, minute=59, second=59, microsecond=999999)
        return self.reporte_periodo(inicio, fin)
    
    def reporte_mensual(self, solo_datos: bool = False) -> Dict:
        """Genera reporte mensual"""
        hoy = datetime.now()
        inicio = hoy.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if hoy.month == 12:
            fin = hoy.replace(year=hoy.year+1, month=1, day=1) - timedelta(days=1)
        else:
            fin = hoy.replace(month=hoy.month+1, day=1) - timedelta(days=1)
        fin = fin.replace(hour=23, minute=59, second=59, microsecond=999999)
        return self.reporte_periodo(inicio, fin)
    
    def reporte_periodo(self, fecha_inicio: datetime, fecha_fin: datetime) -> Dict:
        """Genera reporte de ventas para un periodo"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Obtener pedidos del periodo
        cursor.execute("""
            SELECT 
                p.numero_pedido,
                p.fecha,
                c.nombre as cliente,
                p.subtotal,
                p.iva,
                p.recargo,
                p.total,
                p.estado_entregado,
                p.estado_pagado,
                p.fecha_pagado
            FROM pedidos p
            LEFT JOIN clientes c ON p.cliente_id = c.id
            WHERE datetime(p.fecha) BETWEEN ? AND ?
            ORDER BY p.fecha DESC
        """, (fecha_inicio.isoformat(), fecha_fin.isoformat()))
        
        pedidos = [dict(row) for row in cursor.fetchall()]
        
        # Calcular totales
        total_ventas = sum(p['total'] or 0 for p in pedidos)
        total_iva = sum(p['iva'] or 0 for p in pedidos)
        
        # Resumen por cliente
        resumen_clientes = {}
        for p in pedidos:
            cliente = p['cliente'] or 'Sin cliente'
            if cliente not in resumen_clientes:
                resumen_clientes[cliente] = {'num_pedidos': 0, 'total_vendido': 0}
            resumen_clientes[cliente]['num_pedidos'] += 1
            resumen_clientes[cliente]['total_vendido'] += p['total'] or 0
        
        resumen_clientes_list = [
            {'cliente': k, **v} for k, v in resumen_clientes.items()
        ]
        
        # Productos vendidos
        cursor.execute("""
            SELECT 
                dp.producto,
                SUM(dp.cantidad) as cantidad_vendida,
                SUM(dp.cantidad * dp.precio_unitario) as total_vendido
            FROM detalle_pedidos dp
            JOIN pedidos p ON dp.id_pedido = p.id
            WHERE datetime(p.fecha) BETWEEN ? AND ?
            GROUP BY dp.producto
            ORDER BY total_vendido DESC
        """, (fecha_inicio.isoformat(), fecha_fin.isoformat()))
        
        productos_vendidos = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        
        return {
            'fecha_inicio': fecha_inicio.strftime('%d/%m/%Y'),
            'fecha_fin': fecha_fin.strftime('%d/%m/%Y'),
            'fecha_inicio_obj': fecha_inicio,
            'fecha_fin_obj': fecha_fin,
            'pedidos': pedidos,
            'total_ventas': total_ventas,
            'total_iva': total_iva,
            'resumen_clientes': resumen_clientes_list,
            'productos_vendidos': productos_vendidos
        }
    
    def reporte_texto(self, datos: Dict) -> str:
        """Genera reporte en texto plano"""
        lineas = []
        lineas.append(f"╔═══════════════════════════════════════╗")
        lineas.append(f"║  REPORTE DE VENTAS NONNA             ║")
        lineas.append(f"║  {datos['fecha_inicio']} a {datos['fecha_fin']}        ║")
        lineas.append(f"╚═══════════════════════════════════════╝")
        lineas.append("")
        
        lineas.append("*RESUMEN*")
        lineas.append(f"  Total ventas: {self._formatear_precio(datos['total_ventas'])}")
        lineas.append(f"  Total IVA: {self._formatear_precio(datos['total_iva'])}")
        lineas.append(f"  N° Pedidos: {len(datos['pedidos'])}")
        lineas.append("")
        
        lineas.append("*CLIENTES CON MÁS COMPRAS*")
        for cliente in datos['resumen_clientes'][:5]:
            lineas.append(f"  • {cliente['cliente']}: {cliente['num_pedidos']} pedidos → {self._formatear_precio(cliente['total_vendido'])}")
        lineas.append("")
        
        lineas.append("*PRODUCTOS MÁS VENDIDOS*")
        for prod in datos['productos_vendidos'][:5]:
            lineas.append(f"  • {prod['producto']}: {prod['cantidad_vendida']} unidades → {self._formatear_precio(prod['total_vendido'])}")
        lineas.append("")
        
        return "\n".join(lineas)
    
    def exportar_excel(self, datos: Dict) -> io.BytesIO:
        """Genera un archivo Excel con los datos del reporte y retorna un BytesIO."""
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
        
        wb = openpyxl.Workbook()

        # Estilos
        color_header = "2E7D32"  # verde oscuro
        color_titulo = "1B5E20"  # verde muy oscuro
        font_titulo  = Font(bold=True, color="FFFFFF", size=13)
        font_header  = Font(bold=True, color="FFFFFF", size=11)
        font_normal  = Font(size=10)
        fill_titulo  = PatternFill("solid", fgColor=color_titulo)
        fill_header  = PatternFill("solid", fgColor=color_header)
        fill_alt     = PatternFill("solid", fgColor="E8F5E9")
        align_center = Alignment(horizontal="center", vertical="center")
        align_right  = Alignment(horizontal="right")
        borde = Border(
            left=Side(style="thin"), right=Side(style="thin"),
            top=Side(style="thin"), bottom=Side(style="thin")
        )

        periodo = f"{datos['fecha_inicio']} - {datos['fecha_fin']}"

        # ── Hoja 1: Pedidos ──────────────────────────────────────────────
        ws1 = wb.active
        ws1.title = "Pedidos"

        ws1.merge_cells("A1:I1")
        ws1["A1"] = f"Reporte de Ventas Nonna — {periodo}"
        ws1["A1"].font = font_titulo
        ws1["A1"].fill = fill_titulo
        ws1["A1"].alignment = align_center

        headers = ["N° Pedido", "Fecha", "Cliente", "Subtotal", "IVA", "Recargo", "Total", "Entregado", "Pagado"]
        for col, h in enumerate(headers, 1):
            cell = ws1.cell(row=2, column=col, value=h)
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = align_center
            cell.border = borde

        for i, p in enumerate(datos["pedidos"], 3):
            fecha = datetime.fromisoformat(p["fecha"]).strftime("%d/%m/%Y %H:%M")
            fila = [p["numero_pedido"], fecha, p["cliente"],
                    p["subtotal"], p["iva"], p["recargo"], p["total"],
                    "✅ Sí" if p["estado_entregado"] else "⏳ No",
                    "✅ Sí" if p["estado_pagado"] else "⏳ No"]
            fill = fill_alt if i % 2 == 0 else PatternFill()
            for col, val in enumerate(fila, 1):
                cell = ws1.cell(row=i, column=col, value=val)
                cell.font = font_normal
                cell.fill = fill
                cell.border = borde
                if 4 <= col <= 7:
                    cell.number_format = '"$"#,##0'
                    cell.alignment = align_right
                elif col >= 8:
                    cell.alignment = align_center

        # Fila de totales
        fila_total = len(datos["pedidos"]) + 3
        ws1.cell(row=fila_total, column=1, value="TOTAL").font = Font(bold=True, size=10)
        ws1.cell(row=fila_total, column=6, value="Total:").font = Font(bold=True, size=10)
        cell_total = ws1.cell(row=fila_total, column=7, value=datos["total_ventas"])
        cell_total.font = Font(bold=True, size=10)
        cell_total.number_format = '"$"#,##0'
        cell_total.alignment = align_right

        anchos1 = [18, 16, 24, 12, 12, 12, 12, 12, 12]
        for col, ancho in enumerate(anchos1, 1):
            ws1.column_dimensions[get_column_letter(col)].width = ancho

        # ── Hoja 2: Por Cliente ──────────────────────────────────────────
        ws2 = wb.create_sheet("Por Cliente")
        ws2.merge_cells("A1:C1")
        ws2["A1"] = f"Ventas por Cliente — {periodo}"
        ws2["A1"].font = font_titulo
        ws2["A1"].fill = fill_titulo
        ws2["A1"].alignment = align_center

        for col, h in enumerate(["Cliente", "N° Pedidos", "Total Comprado"], 1):
            cell = ws2.cell(row=2, column=col, value=h)
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = align_center
            cell.border = borde

        for i, c in enumerate(datos["resumen_clientes"], 3):
            fill = fill_alt if i % 2 == 0 else PatternFill()
            for col, val in enumerate([c["cliente"], c["num_pedidos"], c["total_vendido"]], 1):
                cell = ws2.cell(row=i, column=col, value=val)
                cell.font = font_normal
                cell.fill = fill
                cell.border = borde
                if col == 3:
                    cell.number_format = '"$"#,##0'
                    cell.alignment = align_right

        for col, ancho in enumerate([30, 14, 18], 1):
            ws2.column_dimensions[get_column_letter(col)].width = ancho

        # ── Hoja 3: Productos ────────────────────────────────────────────
        ws3 = wb.create_sheet("Productos")
        ws3.merge_cells("A1:C1")
        ws3["A1"] = f"Productos Vendidos — {periodo}"
        ws3["A1"].font = font_titulo
        ws3["A1"].fill = fill_titulo
        ws3["A1"].alignment = align_center

        for col, h in enumerate(["Producto", "Cantidad", "Total Vendido"], 1):
            cell = ws3.cell(row=2, column=col, value=h)
            cell.font = font_header
            cell.fill = fill_header
            cell.alignment = align_center
            cell.border = borde

        for i, prod in enumerate(datos["productos_vendidos"], 3):
            fill = fill_alt if i % 2 == 0 else PatternFill()
            for col, val in enumerate([prod["producto"], prod["cantidad_vendida"], prod["total_vendido"]], 1):
                cell = ws3.cell(row=i, column=col, value=val)
                cell.font = font_normal
                cell.fill = fill
                cell.border = borde
                if col == 3:
                    cell.number_format = '"$"#,##0'
                    cell.alignment = align_right

        for col, ancho in enumerate([30, 12, 18], 1):
            ws3.column_dimensions[get_column_letter(col)].width = ancho

        # Guardar en memoria
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer


if __name__ == "__main__":
    reportes = Reportes()
    print("\n=== REPORTE DIARIO ===")
    reportes.reporte_diario()

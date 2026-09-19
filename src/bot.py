"""
Bot de Telegram para sistema de ventas Nonna
"""
import os
import sys
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from dotenv import load_dotenv
from urllib.parse import quote

from database import Database
# from reportes import Reportes  # Lazy import - only when needed
from gestion_pedidos import (
    gestionar_pedidos_start,
    gestionar_buscar_cliente,
    gestionar_seleccionar_cliente,
    gestionar_seleccionar_pedido,
    gestionar_accion
)


# Cargar variables de entorno
load_dotenv()

# Configurar logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Estados de conversación - pedidos
BUSCAR_CLIENTE, SELECCIONAR_CLIENTE, SELECCIONAR_PRODUCTO, CANTIDAD, EDITAR_PRECIOS, IVA, RECARGO, RECARGO_CONCEPTO, CONFIRMAR = range(9)

# Estados de conversación - clientes
CLIENTE_NOMBRE, CLIENTE_TELEFONO, CLIENTE_EDITAR_CAMPO, CLIENTE_EDITAR_VALOR, CLIENTE_BUSCAR = range(10, 15)

# Estados de conversación - gestión de pedidos
GESTIONAR_BUSCAR_CLIENTE = 25
GESTIONAR_SELECCIONAR_CLIENTE = 26
GESTIONAR_SELECCIONAR_PEDIDO, GESTIONAR_ELEGIR_ACCION = range(20, 22)

# Base de datos
db = Database()
reportes = None  # Lazy loaded when needed

# Almacenamiento temporal de pedidos en progreso
pedidos_temp: Dict[int, Dict] = {}


def formatear_precio(precio: int) -> str:
    """Formatea un precio en CLP"""
    return f"${precio:,}".replace(",", ".")


def generar_mensaje_whatsapp(detalle: dict, cliente) -> str:
    """Genera un mensaje formateado para WhatsApp"""
    mensaje = "🍕 *PEDIDO NONNA* 🍕\n\n"
    mensaje += f"📋 Pedido: *{detalle['numero_pedido']}*\n"
    mensaje += f"👤 Cliente: {cliente.nombre}\n"
    if cliente.telefono:
        mensaje += f"📞 {cliente.telefono}\n"
    mensaje += "\n🛒 *PRODUCTOS:*\n"
    
    for item in detalle['items']:
        mensaje += f"  • {item['producto']} x{item['cantidad']}\n"
        mensaje += f"    {formatear_precio(item['subtotal'])}\n"
    
    mensaje += f"\n💵 Subtotal: {formatear_precio(detalle['subtotal'])}\n"
    
    if detalle['iva']:
        mensaje += f"📊 IVA (19%): {formatear_precio(detalle['iva'])}\n"
    
    if detalle['recargo']:
        nota = f" ({detalle['nota_recargo']})" if detalle['nota_recargo'] else ''
        mensaje += f"➕ Recargo: {formatear_precio(detalle['recargo'])}{nota}\n"
    
    mensaje += f"\n💰 *TOTAL: {formatear_precio(detalle['total'])}*\n"
    mensaje += "\n¡Gracias por tu compra! 🍕"
    
    return mensaje


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - Registra al usuario"""
    user = update.effective_user
    
    # Verificar si el usuario ya existe
    cliente = db.obtener_cliente_por_telegram(user.id)
    
    if cliente:
        mensaje = (
            f"¡Hola {cliente.nombre}! 👋\n\n"
            "Ya estás registrado en el sistema.\n\n"
            "Usa /pedido para hacer un nuevo pedido\n"
            "Usa /productos para ver nuestro menú\n"
            "Usa /mispedidos para ver tu historial\n"
            "Usa /clientes para gestionar clientes\n"
            "Usa /help para ver todos los comandos"
        )
        
        # Agregar botones de reportes
        keyboard = [
            [InlineKeyboardButton("📊 Reporte Diario", callback_data="rpt_diario")],
            [InlineKeyboardButton("📈 Reporte Semanal", callback_data="rpt_semanal")],
            [InlineKeyboardButton("📉 Reporte Mensual", callback_data="rpt_mensual")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(mensaje, reply_markup=reply_markup, parse_mode=None)
    else:
        # Registrar nuevo cliente
        nombre = user.full_name
        telefono = ""  # Se puede pedir después si es necesario
        
        cliente_id = db.crear_cliente(nombre, telefono, user.id)
        
        if cliente_id:
            await update.message.reply_text(
                f"¡Bienvenido {nombre}! 🍕\n\n"
                "Te has registrado exitosamente en Nonna.\n\n"
                "📋 Comandos disponibles:\n"
                "/pedido - Hacer un nuevo pedido\n"
                "/productos - Ver nuestro menú\n"
                "/mispedidos - Ver tus pedidos\n"
                "/clientes - Gestionar clientes\n"
                "/help - Ayuda\n\n"
                "¡Comencemos! Usa /pedido para tu primer pedido 😊"
            )
        else:
            await update.message.reply_text(
                "Hubo un error al registrarte. Por favor intenta de nuevo."
            )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help - Muestra ayuda"""
    help_text = """
🍕 *Sistema de Ventas Nonna* 🍕

📋 *Comandos Disponibles:*

/start - Iniciar y registrarse
/pedido - Crear un nuevo pedido
/productos - Ver menú y precios
/mispedidos - Ver historial de pedidos
/help - Mostrar esta ayuda

👑 *Comandos de Administrador:*
/clientes - Maestro de clientes
/gestionar - Gestionar estados de pedidos
/reporte_diario - Reporte del día
/reporte_semanal - Reporte de la semana
/reporte_mensual - Reporte del mes

💡 *Cómo hacer un pedido:*
1. Escribe /pedido
2. Busca al cliente
3. Selecciona los productos
4. Indica las cantidades
5. Confirma si aplica IVA
6. Agrega recargo si es necesario
7. ¡Confirma y listo!

📦 *Gestionar pedidos:*
1. Escribe /gestionar
2. Busca al cliente
3. Selecciona el pedido
4. Actualiza: Entregado ✅ / Pagado 💰

¿Necesitas ayuda? Escríbenos 📱
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')


async def reporte_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los botones de reportes del menú"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "rpt_diario":
        await reporte_diario_command(update, context)
    elif query.data == "rpt_semanal":
        await reporte_semanal_command(update, context)
    elif query.data == "rpt_mensual":
        await reporte_mensual_command(update, context)


async def reporte_diario_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Genera reporte diario en Excel"""
    global reportes
    # Lazy import
    if reportes is None:
        from reportes import Reportes
        reportes = Reportes()
    
    await update.effective_message.reply_text("📊 Generando reporte diario...")
    try:
        datos = reportes.reporte_diario(solo_datos=True)
        archivo_excel = reportes.exportar_excel(datos)
        
        # Generar nombre del archivo con fecha
        fecha_nombre = datos['fecha_inicio_obj'].strftime('%d_%m_%Y')
        nombre_archivo = f"Reporte_Ventas_Nonna_{fecha_nombre}.xlsx"
        
        # Enviar archivo
        await update.effective_message.reply_document(
            document=archivo_excel,
            filename=nombre_archivo,
            caption="📊 Reporte diario de ventas Nonna"
        )
    except Exception as e:
        logger.error(f"Error generando reporte diario: {e}", exc_info=True)
        await update.effective_message.reply_text(f"❌ Error al generar reporte: {str(e)}")


async def reporte_semanal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Genera reporte semanal en Excel"""
    global reportes
    # Lazy import
    if reportes is None:
        from reportes import Reportes
        reportes = Reportes()
    
    await update.effective_message.reply_text("📈 Generando reporte semanal...")
    try:
        datos = reportes.reporte_semanal(solo_datos=True)
        archivo_excel = reportes.exportar_excel(datos)
        
        # Generar nombre del archivo con rango de semana
        fecha_inicio = datos['fecha_inicio_obj'].strftime('%d_%m_%Y')
        fecha_fin = datos['fecha_fin_obj'].strftime('%d_%m_%Y')
        nombre_archivo = f"Reporte_Ventas_Nonna_Semana_{fecha_inicio}_a_{fecha_fin}.xlsx"
        
        # Enviar archivo
        await update.effective_message.reply_document(
            document=archivo_excel,
            filename=nombre_archivo,
            caption="📈 Reporte semanal de ventas Nonna"
        )
    except Exception as e:
        logger.error(f"Error generando reporte semanal: {e}", exc_info=True)
        await update.effective_message.reply_text(f"❌ Error al generar reporte: {str(e)}")


async def reporte_mensual_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Genera reporte mensual en Excel"""
    global reportes
    # Lazy import
    if reportes is None:
        from reportes import Reportes
        reportes = Reportes()
    
    await update.effective_message.reply_text("📉 Generando reporte mensual...")
    try:
        datos = reportes.reporte_mensual(solo_datos=True)
        archivo_excel = reportes.exportar_excel(datos)
        
        # Generar nombre del archivo con mes/año usando el objeto datetime
        fecha_nombre = datos['fecha_inicio_obj'].strftime('%m_%Y')
        nombre_archivo = f"Reporte_Ventas_Nonna_{fecha_nombre}.xlsx"
        
        # Enviar archivo - El BytesIO ya está en posición 0 (seek(0) en exportar_excel)
        await update.effective_message.reply_document(
            document=archivo_excel,
            filename=nombre_archivo,
            caption="📊 Reporte mensual de ventas Nonna"
        )
    except Exception as e:
        logger.error(f"Error generando reporte: {e}", exc_info=True)
        await update.effective_message.reply_text(f"❌ Error al generar reporte: {str(e)}")


async def productos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /productos - Muestra el menú"""
    productos = db.obtener_productos()
    
    if not productos:
        await update.message.reply_text("No hay productos disponibles en este momento.")
        return
    
    mensaje = "🍕 *Menú Nonna* 🍕\n\n"
    
    # Agrupar por tipo
    empanadas = [p for p in productos if p.tipo == 'empanada']
    panes = [p for p in productos if p.tipo == 'pan']
    
    if empanadas:
        mensaje += "*Empanadas:*\n"
        for p in empanadas:
            mensaje += f"  • {p.nombre} - {formatear_precio(p.precio_base)}\n"
        mensaje += "\n"
    
    if panes:
        mensaje += "*Pan de Masa Madre:*\n"
        for p in panes:
            mensaje += f"  • {p.nombre} - {formatear_precio(p.precio_base)}\n"
    
    mensaje += "\n¡Usa /pedido para ordenar! 😊"
    
    await update.message.reply_text(mensaje, parse_mode='Markdown')


async def clima_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /clima - Muestra pronóstico 5 días Santiago"""
    try:
        await update.message.reply_text("🌤️ Obteniendo pronóstico de Santiago...", parse_mode='Markdown')
        
        # Obtener ruta del script
        bot_dir = Path(__file__).parent.parent
        script_path = bot_dir / 'scripts' / 'santiago_weather.py'
        
        if not script_path.exists():
            await update.message.reply_text("❌ Script de pronóstico no encontrado.")
            logger.error(f"Script no encontrado: {script_path}")
            return
        
        # Ejecutar script
        result = subprocess.run(
            ["python", str(script_path)],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(bot_dir)
        )
        
        if result.returncode == 0 and result.stdout.strip():
            await update.message.reply_text(result.stdout, parse_mode='Markdown')
        else:
            error_msg = result.stderr if result.stderr else "Error desconocido"
            await update.message.reply_text(
                f"❌ Error obteniendo pronóstico:\\n{error_msg[:200]}",
                parse_mode='Markdown'
            )
            logger.error(f"Error en script clima: {error_msg}")
    
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏱️ Timeout: El pronóstico tardó demasiado.")
        logger.error("Timeout en script clima")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)[:100]}")
        logger.error(f"Excepción en clima_command: {e}")


async def shutdown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /shutdown - Reinicia la PC con PIN de seguridad"""
    user_id = update.effective_user.id
    
    # Pedir PIN
    await update.message.reply_text(
        "🔐 *Seguridad Requerida*\n\n"
        "Ingresa el PIN de 4 dígitos para autorizar el reinicio:\n\n"
        "_(El PIN es confidencial, solo tú lo conoces)_",
        parse_mode='Markdown'
    )
    
    # Guardar que estamos esperando el PIN
    context.user_data['esperando_shutdown_pin'] = True


async def recibir_shutdown_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe y valida el PIN de shutdown"""
    # Solo procesar si estamos esperando un PIN
    if not context.user_data.get('esperando_shutdown_pin'):
        return  # Dejar que otros handlers procesen
    
    pin_ingresado = update.message.text.strip()
    pin_correcto = "3112"
    
    if pin_ingresado == pin_correcto:
        context.user_data['esperando_shutdown_pin'] = False
        
        # PIN correcto - Mostrar confirmación
        keyboard = [
            [InlineKeyboardButton("✅ Sí, reiniciar ahora", callback_data="shutdown_confirm")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="shutdown_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "✅ *PIN Correcto*\n\n"
            "⚠️ *Advertencia*\n\n"
            "¿Estás seguro de que deseas reiniciar tu PC?\n\n"
            "El PC se reiniciará en 60 segundos.\n"
            "Puedes cancelar presionando el botón Cancelar.",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        # PIN incorrecto
        await update.message.reply_text(
            "❌ *PIN Incorrecto*\n\n"
            "El PIN que ingresaste no es válido.\n"
            "Reinicio cancelado.",
            parse_mode='Markdown'
        )
        context.user_data['esperando_shutdown_pin'] = False


async def shutdown_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los botones de confirmación de shutdown"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "shutdown_confirm":
        await query.edit_message_text(
            "🔄 *Reinicio iniciado*\n\n"
            "Tu PC se reiniciará en 60 segundos...\n"
            "Puedes ejecutar este comando nuevamente para cancelar.",
            parse_mode='Markdown'
        )
        
        # Ejecutar reinicio en 60 segundos (cambié /s por /r para restart)
        import os
        os.system("shutdown /r /t 60")
        logger.info("Reinicio programado en 60 segundos")
        
    elif query.data == "shutdown_cancel":
        await query.edit_message_text(
            "❌ *Reinicio cancelado*\n\n"
            "El reinicio ha sido cancelado."
        )
        os.system("shutdown /a")  # Cancela el reinicio
        logger.info("Reinicio cancelado")


async def pedido_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia el proceso de crear un pedido - primero pide el cliente"""
    await update.message.reply_text(
        "🛒 *Nuevo Pedido*\n\n"
        "Escribe el nombre del cliente:",
        parse_mode='Markdown'
    )
    return BUSCAR_CLIENTE


async def pedido_buscar_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Busca el cliente por nombre"""
    texto = update.message.text.strip()
    clientes = db.buscar_clientes(texto)

    if not clientes:
        await update.message.reply_text(
            f"No se encontro ningun cliente con '{texto}'.\n\n"
            "Usa /clientes para crear el cliente primero, luego vuelve a /pedido."
        )
        return ConversationHandler.END

    if len(clientes) == 1:
        # Cliente unico encontrado, continuar directo
        c = clientes[0]
        user_id = update.effective_user.id
        pedidos_temp[user_id] = {
            'cliente_id': c.id,
            'items': [],
            'aplica_iva': False,
            'recargo': 0,
            'nota_recargo': ''
        }
        return await _mostrar_productos(update, context, c.nombre)

    # Varios clientes: mostrar botones para seleccionar
    keyboard = []
    for c in clientes[:10]:
        tel = f" - {c.telefono}" if c.telefono else ""
        keyboard.append([InlineKeyboardButton(
            f"{c.nombre}{tel}",
            callback_data=f"selcli_{c.id}"
        )])
    await update.message.reply_text(
        f"Se encontraron {len(clientes)} clientes. Selecciona uno:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SELECCIONAR_CLIENTE


async def pedido_seleccionar_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la seleccion de cliente cuando hay varios resultados"""
    query = update.callback_query
    await query.answer()

    cliente_id = int(query.data.split("_")[1])
    cliente = db.obtener_cliente_por_id(cliente_id)

    if not cliente:
        await query.edit_message_text("Cliente no encontrado. Usa /pedido para intentar de nuevo.")
        return ConversationHandler.END

    user_id = query.from_user.id
    pedidos_temp[user_id] = {
        'cliente_id': cliente.id,
        'items': [],
        'aplica_iva': False,
        'recargo': 0,
        'nota_recargo': ''
    }

    productos = db.obtener_productos()
    if not productos:
        await query.edit_message_text("No hay productos disponibles.")
        return ConversationHandler.END

    keyboard = []
    for p in productos:
        keyboard.append([InlineKeyboardButton(
            f"{p.nombre} - {formatear_precio(p.precio_base)}",
            callback_data=f"producto_{p.id}"
        )])
    keyboard.append([InlineKeyboardButton("✅ Finalizar Selección", callback_data="finalizar")])

    await query.edit_message_text(
        f"👤 Cliente: *{cliente.nombre}*\n\n"
        "Selecciona los productos:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return SELECCIONAR_PRODUCTO


async def _mostrar_productos(update: Update, context: ContextTypes.DEFAULT_TYPE, nombre_cliente: str):
    """Muestra el listado de productos para seleccionar"""
    productos = db.obtener_productos()
    if not productos:
        await update.message.reply_text("No hay productos disponibles.")
        return ConversationHandler.END

    keyboard = []
    for p in productos:
        keyboard.append([InlineKeyboardButton(
            f"{p.nombre} - {formatear_precio(p.precio_base)}",
            callback_data=f"producto_{p.id}"
        )])
    keyboard.append([InlineKeyboardButton("✅ Finalizar Selección", callback_data="finalizar")])

    await update.message.reply_text(
        f"👤 Cliente: *{nombre_cliente}*\n\n"
        "Selecciona los productos:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return SELECCIONAR_PRODUCTO


async def seleccionar_producto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la selección de productos"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "finalizar":
        if not pedidos_temp[user_id]['items']:
            await query.edit_message_text("No has seleccionado ningún producto. Usa /pedido para empezar de nuevo.")
            return ConversationHandler.END
        
        # Ir a editar precios de cada ítem
        return await mostrar_edicion_precios(update, context)
    
    # Extraer producto_id
    producto_id = int(query.data.split("_")[1])
    producto = db.obtener_producto(producto_id)
    
    # Guardar producto seleccionado temporalmente
    context.user_data['producto_seleccionado'] = producto_id
    
    await query.edit_message_text(
        f"Has seleccionado: *{producto.nombre}*\n"
        f"Precio: {formatear_precio(producto.precio_base)}\n\n"
        f"¿Cuántas unidades deseas? (Escribe un número)",
        parse_mode='Markdown'
    )
    
    return CANTIDAD


async def recibir_cantidad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe la cantidad del producto"""
    user_id = update.effective_user.id
    
    try:
        cantidad = int(update.message.text)
        if cantidad <= 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("Por favor ingresa un número válido mayor a 0.")
        return CANTIDAD
    
    producto_id = context.user_data['producto_seleccionado']
    producto = db.obtener_producto(producto_id)
    
    subtotal = producto.precio_base * cantidad
    
    # Agregar item al pedido temporal
    pedidos_temp[user_id]['items'].append({
        'producto_id': producto_id,
        'cantidad': cantidad,
        'precio_unitario': producto.precio_base,
        'subtotal': subtotal
    })
    
    # Preguntar si desea agregar más productos
    keyboard = [
        [InlineKeyboardButton("➕ Agregar más productos", callback_data="mas_productos")],
        [InlineKeyboardButton("✅ Finalizar Selección", callback_data="finalizar")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"✅ Agregado: {producto.nombre}\n"
        f"   {formatear_precio(producto.precio_base)} × {cantidad} = {formatear_precio(subtotal)}\n\n"
        "¿Qué deseas hacer?",
        reply_markup=reply_markup
    )
    
    return SELECCIONAR_PRODUCTO


async def mas_productos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Permite agregar más productos"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "mas_productos":
        productos = db.obtener_productos()
        
        keyboard = []
        for p in productos:
            keyboard.append([
                InlineKeyboardButton(
                    f"{p.nombre} - {formatear_precio(p.precio_base)}",
                    callback_data=f"producto_{p.id}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("✅ Finalizar Selección", callback_data="finalizar")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Selecciona otro producto:",
            reply_markup=reply_markup
        )
        
        return SELECCIONAR_PRODUCTO


async def mostrar_edicion_precios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra los precios de cada ítem para editar"""
    # Obtener query si existe (viene de callback) o None (viene de mensaje)
    query = update.callback_query
    user_id = query.from_user.id if query else update.effective_user.id
    pedido = pedidos_temp[user_id]
    
    # Inicializar índice del ítem a editar si no existe
    if 'item_edit_idx' not in context.user_data:
        context.user_data['item_edit_idx'] = 0
    
    idx = context.user_data['item_edit_idx']
    
    # Si ya pasamos todos los items, ir a IVA
    if idx >= len(pedido['items']):
        context.user_data['item_edit_idx'] = 0  # Reset
        
        # Mostrar resumen con edición de recargo y pedir confirmación de IVA
        subtotal = sum(item['subtotal'] for item in pedido['items'])
        
        resumen = "📋 *Resumen del Pedido:*\n\n"
        for i, item in enumerate(pedido['items'], 1):
            producto = db.obtener_producto(item['producto_id'])
            resumen += f"{i}. {producto.nombre}\n"
            resumen += f"   {formatear_precio(item['precio_unitario'])} × {item['cantidad']} = {formatear_precio(item['subtotal'])}\n"
        
        resumen += f"\n*Subtotal:* {formatear_precio(subtotal)}\n\n"
        resumen += "¿Deseas aplicar IVA (19%)?"
        
        keyboard = [
            [InlineKeyboardButton("✅ Sí, con IVA", callback_data="iva_si")],
            [InlineKeyboardButton("❌ No, sin IVA", callback_data="iva_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if query:
            await query.edit_message_text(resumen, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(resumen, reply_markup=reply_markup, parse_mode='Markdown')
        return IVA
    
    # Mostrar el ítem actual para editar precio
    item = pedido['items'][idx]
    producto = db.obtener_producto(item['producto_id'])
    cantidad = item['cantidad']
    precio_actual = item['precio_unitario']
    
    mensaje = f"✏️ *Editar Precio de Ítem {idx + 1} de {len(pedido['items'])}*\n\n"
    mensaje += f"Producto: *{producto.nombre}*\n"
    mensaje += f"Cantidad: {cantidad}\n"
    mensaje += f"Precio actual por unidad: {formatear_precio(precio_actual)}\n"
    mensaje += f"Subtotal actual: {formatear_precio(item['subtotal'])}\n\n"
    mensaje += "Ingresa el nuevo precio por unidad (o presiona 0 para mantener el actual):"
    
    if query:
        await query.edit_message_text(mensaje, parse_mode='Markdown')
    else:
        await update.message.reply_text(mensaje, parse_mode='Markdown')
    return EDITAR_PRECIOS


async def recibir_precio_editado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el nuevo precio unitario editado"""
    user_id = update.effective_user.id
    pedido = pedidos_temp[user_id]
    idx = context.user_data.get('item_edit_idx', 0)
    
    try:
        nuevo_precio = int(update.message.text)
        if nuevo_precio < 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("Por favor ingresa un número válido (0 o mayor).")
        return EDITAR_PRECIOS
    
    item = pedido['items'][idx]
    producto = db.obtener_producto(item['producto_id'])
    precio_anterior = item['precio_unitario']
    
    # Si es 0, mantener el precio actual
    if nuevo_precio > 0:
        item['precio_unitario'] = nuevo_precio
        item['subtotal'] = nuevo_precio * item['cantidad']
        # Mostrar confirmación del cambio
        await update.message.reply_text(
            f"✅ Precio actualizado para *{producto.nombre}*\n"
            f"Anterior: {formatear_precio(precio_anterior)}\n"
            f"Nuevo: {formatear_precio(nuevo_precio)} × {item['cantidad']} = {formatear_precio(item['subtotal'])}"
        )
    else:
        await update.message.reply_text(
            f"✓ Precio mantenido para *{producto.nombre}*: {formatear_precio(precio_anterior)}"
        )
    
    # Pasar al siguiente ítem
    context.user_data['item_edit_idx'] = idx + 1
    
    # Mostrar siguiente ítem o ir a IVA
    return await mostrar_edicion_precios(update, context)


async def aplicar_iva(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la opción de IVA"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    pedido = pedidos_temp[user_id]
    
    if query.data == "iva_si":
        pedido['aplica_iva'] = True
    else:
        pedido['aplica_iva'] = False
    
    # Preguntar por recargo
    await query.edit_message_text(
        "¿Hay algún recargo adicional?\n\n"
        "Escribe el monto en pesos (ejemplo: 1000) o escribe 0 si no hay recargo."
    )
    
    return RECARGO


async def recibir_recargo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el monto de recargo"""
    user_id = update.effective_user.id
    
    try:
        recargo = int(update.message.text)
        if recargo < 0:
            raise ValueError()
    except ValueError:
        await update.message.reply_text("Por favor ingresa un número válido (0 o mayor).")
        return RECARGO
    
    pedidos_temp[user_id]['recargo'] = recargo
    
    if recargo > 0:
        await update.message.reply_text(
            "¿Cuál es el motivo del recargo? (ejemplo: delivery, envase especial)"
        )
        return RECARGO_CONCEPTO
    else:
        # Mostrar confirmación final
        return await mostrar_confirmacion(update, context)


async def recibir_nota_recargo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe la nota del recargo"""
    user_id = update.effective_user.id
    pedidos_temp[user_id]['nota_recargo'] = update.message.text
    
    return await mostrar_confirmacion(update, context)


async def mostrar_confirmacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra confirmación final del pedido"""
    user_id = update.effective_user.id
    pedido = pedidos_temp[user_id]
    
    subtotal = sum(item['subtotal'] for item in pedido['items'])
    iva_monto = int(subtotal * 0.19) if pedido['aplica_iva'] else 0
    total = subtotal + iva_monto + pedido['recargo']
    
    mensaje = "📝 *Confirmación de Pedido*\n\n"
    mensaje += "*Productos:*\n"
    
    for item in pedido['items']:
        producto = db.obtener_producto(item['producto_id'])
        mensaje += f"• {producto.nombre}\n"
        mensaje += f"  {formatear_precio(item['precio_unitario'])} × {item['cantidad']} = {formatear_precio(item['subtotal'])}\n"
    
    mensaje += f"\n*Subtotal:* {formatear_precio(subtotal)}\n"
    
    if pedido['aplica_iva']:
        mensaje += f"*IVA (19%):* {formatear_precio(iva_monto)}\n"
    
    if pedido['recargo'] > 0:
        mensaje += f"*Recargo:* {formatear_precio(pedido['recargo'])}"
        if pedido['nota_recargo']:
            mensaje += f" ({pedido['nota_recargo']})"
        mensaje += "\n"
    
    mensaje += f"\n*TOTAL:* {formatear_precio(total)}\n\n"
    mensaje += "¿Confirmas el pedido?"
    
    keyboard = [
        [InlineKeyboardButton("✅ Confirmar Pedido", callback_data="confirmar_si")],
        [InlineKeyboardButton("❌ Cancelar", callback_data="confirmar_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Si viene de recargo sin nota
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(mensaje, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(mensaje, reply_markup=reply_markup, parse_mode='Markdown')
    
    return CONFIRMAR


async def confirmar_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirma y guarda el pedido"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "confirmar_no":
        await query.edit_message_text("❌ Pedido cancelado. Usa /pedido para empezar de nuevo.")
        del pedidos_temp[user_id]
        return ConversationHandler.END
    
    # Guardar pedido en la base de datos
    pedido = pedidos_temp[user_id]
    
    pedido_id = db.crear_pedido(
        cliente_id=pedido['cliente_id'],
        items=pedido['items'],
        aplica_iva=pedido['aplica_iva'],
        recargo=pedido['recargo'],
        nota_recargo=pedido['nota_recargo']
    )
    
    if pedido_id:
        # Obtener datos del pedido guardado
        detalle = db.obtener_detalle_pedido(pedido_id)
        cliente = db.obtener_cliente_por_id(pedido['cliente_id'])

        # Mensaje para Telegram
        mensaje = f"✅ *¡Pedido Confirmado!*\n\n"
        mensaje += f"📋 *Número:* {detalle['numero_pedido']}\n"
        mensaje += f"👤 *Cliente:* {cliente.nombre}\n"
        if cliente.telefono:
            mensaje += f"📞 *Teléfono:* {cliente.telefono}\n"
        mensaje += "\n🛒 *Productos:*\n"
        for item in detalle['items']:
            mensaje += f"  • {item['producto']} x{item['cantidad']} = {formatear_precio(item['subtotal'])}\n"
        mensaje += f"\n💵 *Subtotal:* {formatear_precio(detalle['subtotal'])}\n"
        if detalle['iva']:
            mensaje += f"📊 *IVA (19%):* {formatear_precio(detalle['iva'])}\n"
        if detalle['recargo']:
            nota = f" ({detalle['nota_recargo']})" if detalle['nota_recargo'] else ''
            mensaje += f"➕ *Recargo:* {formatear_precio(detalle['recargo'])}{nota}\n"
        mensaje += f"\n💰 *TOTAL: {formatear_precio(detalle['total'])}*\n\n"
        mensaje += "¡Gracias por tu compra! 🍕"

        # Generar mensaje para WhatsApp
        mensaje_wa = generar_mensaje_whatsapp(detalle, cliente)
        mensaje_wa_encoded = quote(mensaje_wa)
        whatsapp_url = f"https://wa.me/?text={mensaje_wa_encoded}"
        
        # Botón para compartir en WhatsApp
        keyboard = [
            [InlineKeyboardButton("📱 Enviar a WhatsApp", url=whatsapp_url)]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(mensaje, reply_markup=reply_markup, parse_mode='Markdown')

        # Limpiar pedido temporal
        del pedidos_temp[user_id]
    else:
        await query.edit_message_text("❌ Hubo un error al guardar el pedido. Por favor intenta de nuevo.")
        del pedidos_temp[user_id]
    
    return ConversationHandler.END


async def mispedidos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra los pedidos del usuario"""
    user = update.effective_user
    cliente = db.obtener_cliente_por_telegram(user.id)
    
    if not cliente:
        await update.message.reply_text("No estás registrado. Usa /start primero.")
        return
    
    pedidos = db.obtener_pedidos_cliente(cliente.id, limit=5)
    
    if not pedidos:
        await update.message.reply_text("Aún no tienes pedidos. ¡Usa /pedido para hacer tu primer pedido!")
        return
    
    mensaje = "📋 *Tus Últimos Pedidos:*\n\n"
    
    for p in pedidos:
        fecha = datetime.fromisoformat(p['fecha']).strftime('%d/%m/%Y %H:%M')
        mensaje += f"• *{p['numero_pedido']}*\n"
        mensaje += f"  Fecha: {fecha}\n"
        mensaje += f"  Total: {formatear_precio(p['total'])}\n\n"
    
    await update.message.reply_text(mensaje, parse_mode='Markdown')


async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela la conversación actual"""
    user_id = update.effective_user.id
    if user_id in pedidos_temp:
        del pedidos_temp[user_id]
    
    await update.message.reply_text("Operación cancelada.")
    return ConversationHandler.END


# Comandos de administrador
async def reporte_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Genera reporte diario (solo admin)"""
    user_id = update.effective_user.id
    admin_id = int(os.getenv('ADMIN_USER_ID', 0))
    
    if user_id != admin_id:
        await update.message.reply_text("No tienes permisos para este comando.")
        return
    
    await update.message.reply_text("📊 Generando reporte diario...")
    
    datos = reportes.reporte_diario(solo_datos=True)
    
    mensaje = f"📊 *Reporte Diario*\n\n"
    mensaje += f"📅 {datos['fecha_inicio'].strftime('%d/%m/%Y')}\n\n"
    mensaje += f"📋 Pedidos: {datos['total_pedidos']}\n"
    mensaje += f"💰 Total: {formatear_precio(datos['total_ventas'])}\n"
    
    # Agregar detalle de productos más vendidos
    if datos['productos_vendidos']:
        mensaje += "\n🏆 *Top Productos:*\n"
        for prod in datos['productos_vendidos'][:3]:  # Top 3
            mensaje += f"  • {prod['producto']}: {prod['cantidad_vendida']} uds.\n"
    
    await update.message.reply_text(mensaje, parse_mode='Markdown')


async def reporte_semanal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Genera reporte semanal (solo admin)"""
    user_id = update.effective_user.id
    admin_id = int(os.getenv('ADMIN_USER_ID', 0))
    
    if user_id != admin_id:
        await update.message.reply_text("No tienes permisos para este comando.")
        return
    
    await update.message.reply_text("📊 Generando reporte semanal...")
    
    datos = reportes.reporte_semanal(solo_datos=True)
    
    mensaje = f"📊 *Reporte Semanal*\n\n"
    mensaje += f"📅 {datos['fecha_inicio'].strftime('%d/%m')} - {datos['fecha_fin'].strftime('%d/%m/%Y')}\n\n"
    mensaje += f"📋 Pedidos: {datos['total_pedidos']}\n"
    mensaje += f"💰 Total: {formatear_precio(datos['total_ventas'])}\n"
    
    # Agregar detalle de productos más vendidos
    if datos['productos_vendidos']:
        mensaje += "\n🏆 *Top Productos:*\n"
        for prod in datos['productos_vendidos'][:3]:  # Top 3
            mensaje += f"  • {prod['producto']}: {prod['cantidad_vendida']} uds.\n"
    
    await update.message.reply_text(mensaje, parse_mode='Markdown')


async def reporte_mensual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Genera reporte mensual (solo admin)"""
    user_id = update.effective_user.id
    admin_id = int(os.getenv('ADMIN_USER_ID', 0))
    
    if user_id != admin_id:
        await update.message.reply_text("No tienes permisos para este comando.")
        return
    
    await update.message.reply_text("📊 Generando reporte mensual...")
    
    datos = reportes.reporte_mensual(solo_datos=True)
    
    # Obtener nombre del mes en español
    meses = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
             'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
    mes_nombre = meses[datos['fecha_inicio'].month - 1]
    
    mensaje = f"📊 *Reporte Mensual*\n\n"
    mensaje += f"📅 {mes_nombre} {datos['fecha_inicio'].year}\n\n"
    mensaje += f"📋 Pedidos: {datos['total_pedidos']}\n"
    mensaje += f"💰 Total: {formatear_precio(datos['total_ventas'])}\n"
    
    # Agregar detalle de productos más vendidos
    if datos['productos_vendidos']:
        mensaje += "\n🏆 *Top Productos:*\n"
        for prod in datos['productos_vendidos'][:3]:  # Top 3
            mensaje += f"  • {prod['producto']}: {prod['cantidad_vendida']} uds.\n"
    
    # Agregar top clientes
    if datos['resumen_clientes']:
        mensaje += "\n👥 *Top Clientes:*\n"
        for cliente in datos['resumen_clientes'][:3]:  # Top 3
            mensaje += f"  • {cliente['cliente']}: {formatear_precio(cliente['total_vendido'])}\n"
    
    await update.message.reply_text(mensaje, parse_mode='Markdown')


# === EXPORTAR EXCEL ===

async def excel_diario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exporta reporte diario a Excel (solo admin)"""
    user_id = update.effective_user.id
    admin_id = int(os.getenv('ADMIN_USER_ID', 0))
    if user_id != admin_id:
        await update.message.reply_text("No tienes permisos para este comando.")
        return
    await update.message.reply_text("📊 Generando Excel diario...")
    datos = reportes.reporte_diario(solo_datos=True)
    if not datos['pedidos']:
        await update.message.reply_text("No hay pedidos hoy.")
        return
    buffer = reportes.exportar_excel(datos)
    nombre = f"reporte_diario_{datos['fecha_inicio'].strftime('%Y%m%d')}.xlsx"
    await update.message.reply_document(document=buffer, filename=nombre, caption="📊 Reporte diario")


async def excel_semanal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exporta reporte semanal a Excel (solo admin)"""
    user_id = update.effective_user.id
    admin_id = int(os.getenv('ADMIN_USER_ID', 0))
    if user_id != admin_id:
        await update.message.reply_text("No tienes permisos para este comando.")
        return
    await update.message.reply_text("📊 Generando Excel semanal...")
    datos = reportes.reporte_semanal(solo_datos=True)
    if not datos['pedidos']:
        await update.message.reply_text("No hay pedidos esta semana.")
        return
    buffer = reportes.exportar_excel(datos)
    nombre = f"reporte_semanal_{datos['fecha_inicio'].strftime('%Y%m%d')}.xlsx"
    await update.message.reply_document(document=buffer, filename=nombre, caption="📊 Reporte semanal")


async def excel_mensual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exporta reporte mensual a Excel (solo admin)"""
    user_id = update.effective_user.id
    admin_id = int(os.getenv('ADMIN_USER_ID', 0))
    if user_id != admin_id:
        await update.message.reply_text("No tienes permisos para este comando.")
        return
    await update.message.reply_text("📊 Generando Excel mensual...")
    datos = reportes.reporte_mensual(solo_datos=True)
    if not datos['pedidos']:
        await update.message.reply_text("No hay pedidos este mes.")
        return
    buffer = reportes.exportar_excel(datos)
    meses = ['enero','febrero','marzo','abril','mayo','junio',
             'julio','agosto','septiembre','octubre','noviembre','diciembre']
    mes = meses[datos['fecha_inicio'].month - 1]
    nombre = f"reporte_{mes}_{datos['fecha_inicio'].year}.xlsx"
    await update.message.reply_document(document=buffer, filename=nombre, caption=f"📊 Reporte {mes} {datos['fecha_inicio'].year}")


# === MAESTRO DE CLIENTES ===

async def clientes_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /clientes - Menu del maestro de clientes (solo admin)"""
    user_id = update.effective_user.id
    admin_id = int(os.getenv('ADMIN_USER_ID', 0))
    if user_id != admin_id:
        await update.message.reply_text("No tienes permisos para este comando.")
        return ConversationHandler.END

    keyboard = [
        [InlineKeyboardButton("🔍 Buscar cliente", callback_data="cli_buscar")],
        [InlineKeyboardButton("📋 Listar todos", callback_data="cli_listar")],
        [InlineKeyboardButton("➕ Nuevo cliente", callback_data="cli_nuevo")],
    ]
    await update.message.reply_text(
        "👥 *Maestro de Clientes*\n\n¿Qué deseas hacer?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return CLIENTE_BUSCAR


async def clientes_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja las opciones del menu de clientes"""
    query = update.callback_query
    await query.answer()

    if query.data == "cli_listar":
        clientes = db.listar_clientes()
        if not clientes:
            await query.edit_message_text("No hay clientes registrados aun.")
            return ConversationHandler.END

        msg = "👥 *Lista de Clientes:*\n\n"
        for c in clientes:
            tel = c.telefono if c.telefono else "sin telefono"
            msg += f"• *{c.nombre}*\n  Tel: {tel}\n  Desde: {c.fecha_registro.strftime('%d/%m/%Y')}\n\n"
        await query.edit_message_text(msg, parse_mode='Markdown')
        return ConversationHandler.END

    elif query.data == "cli_buscar":
        await query.edit_message_text("🔍 Escribe el nombre o telefono a buscar:")
        return CLIENTE_BUSCAR

    elif query.data == "cli_nuevo":
        await query.edit_message_text("➕ *Nuevo Cliente*\n\nEscribe el nombre completo:", parse_mode='Markdown')
        return CLIENTE_NOMBRE

    elif query.data.startswith("cli_ver_"):
        cliente_id = int(query.data.split("_")[2])
        cliente = db.obtener_cliente_por_id(cliente_id)
        if not cliente:
            await query.edit_message_text("Cliente no encontrado.")
            return ConversationHandler.END
        tel = cliente.telefono if cliente.telefono else "sin telefono"
        msg = (
            f"👤 *{cliente.nombre}*\n\n"
            f"📞 Telefono: {tel}\n"
            f"📅 Registrado: {cliente.fecha_registro.strftime('%d/%m/%Y %H:%M')}\n"
            f"🆔 ID Telegram: {cliente.telegram_user_id}\n"
        )
        keyboard = [
            [InlineKeyboardButton("✏️ Editar nombre", callback_data=f"cli_edit_nombre_{cliente_id}")],
            [InlineKeyboardButton("📞 Editar telefono", callback_data=f"cli_edit_telefono_{cliente_id}")],
        ]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return CLIENTE_EDITAR_CAMPO

    elif query.data.startswith("cli_edit_"):
        partes = query.data.split("_")
        campo = partes[2]  # nombre o telefono
        cliente_id = int(partes[3])
        context.user_data['cli_edit_id'] = cliente_id
        context.user_data['cli_edit_campo'] = campo
        await query.edit_message_text(f"✏️ Escribe el nuevo {'nombre' if campo == 'nombre' else 'telefono'}:")
        return CLIENTE_EDITAR_VALOR

    return ConversationHandler.END


async def clientes_buscar_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe texto de busqueda y muestra resultados"""
    texto = update.message.text.strip()
    clientes = db.buscar_clientes(texto)

    if not clientes:
        await update.message.reply_text(f"No se encontraron clientes con '{texto}'.")
        return ConversationHandler.END

    if len(clientes) == 1:
        c = clientes[0]
        tel = c.telefono if c.telefono else "sin telefono"
        msg = (
            f"👤 *{c.nombre}*\n\n"
            f"📞 Telefono: {tel}\n"
            f"📅 Registrado: {c.fecha_registro.strftime('%d/%m/%Y %H:%M')}\n"
        )
        keyboard = [
            [InlineKeyboardButton("✏️ Editar nombre", callback_data=f"cli_edit_nombre_{c.id}")],
            [InlineKeyboardButton("📞 Editar telefono", callback_data=f"cli_edit_telefono_{c.id}")],
        ]
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return CLIENTE_EDITAR_CAMPO

    # Varios resultados: mostrar lista con botones
    keyboard = []
    for c in clientes[:10]:
        keyboard.append([InlineKeyboardButton(
            f"{c.nombre} - {c.telefono or 'sin tel'}",
            callback_data=f"cli_ver_{c.id}"
        )])
    await update.message.reply_text(
        f"Se encontraron {len(clientes)} clientes:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CLIENTE_EDITAR_CAMPO


async def clientes_nuevo_nombre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el nombre del nuevo cliente"""
    context.user_data['cli_nuevo_nombre'] = update.message.text.strip()
    await update.message.reply_text("📞 Ahora escribe su numero de telefono (o escribe 'omitir'):")
    return CLIENTE_TELEFONO


async def clientes_nuevo_telefono(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el telefono y crea el cliente"""
    telefono = update.message.text.strip()
    if telefono.lower() == 'omitir':
        telefono = ''
    nombre = context.user_data.get('cli_nuevo_nombre', '')

    # Usar un telegram_user_id ficticio unico para clientes creados manualmente
    import time
    telegram_id_ficticio = int(f"9{int(time.time())}")

    cliente_id = db.crear_cliente(nombre, telefono, telegram_id_ficticio)
    if cliente_id:
        await update.message.reply_text(
            f"✅ Cliente *{nombre}* creado correctamente.\n"
            f"📞 Telefono: {telefono or 'sin telefono'}",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("❌ Error al crear el cliente. Intenta de nuevo.")
    return ConversationHandler.END


async def clientes_editar_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el nuevo valor y actualiza el cliente"""
    cliente_id = context.user_data.get('cli_edit_id')
    campo = context.user_data.get('cli_edit_campo')
    nuevo_valor = update.message.text.strip()

    cliente = db.obtener_cliente_por_id(cliente_id)
    if not cliente:
        await update.message.reply_text("Cliente no encontrado.")
        return ConversationHandler.END

    if campo == 'nombre':
        ok = db.actualizar_cliente(cliente_id, nuevo_valor, cliente.telefono or '')
    else:
        ok = db.actualizar_cliente(cliente_id, cliente.nombre, nuevo_valor)

    if ok:
        await update.message.reply_text(f"✅ {'Nombre' if campo == 'nombre' else 'Telefono'} actualizado correctamente.")
    else:
        await update.message.reply_text("❌ Error al actualizar. Intenta de nuevo.")
    return ConversationHandler.END


async def clientes_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela operacion de clientes"""
    await update.message.reply_text("Operacion cancelada.")
    return ConversationHandler.END


def main():
    """Función principal del bot"""
    # Verificar que no haya otra instancia corriendo
    import atexit
    pid_file = Path("data/bot.pid")
    
    # Verificar si el archivo PID existe
    if pid_file.exists():
        try:
            with open(pid_file, 'r') as f:
                old_pid = int(f.read().strip())
            
            # Verificar si el proceso está realmente corriendo
            import psutil
            process_exists = False
            try:
                proc = psutil.Process(old_pid)
                # Validación extra: verificar que sea realmente python
                if proc.is_running() and 'python' in proc.name().lower():
                    process_exists = True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
            
            if process_exists:
                logger.error(f"❌ Bot ya está corriendo (PID: {old_pid})")
                print(f"❌ Error: El bot ya está corriendo con PID {old_pid}")
                print("   Para detenerlo: taskkill /F /PID {old_pid}")
                return
            else:
                # El proceso no existe o no es python, limpiar PID
                logger.warning(f"PID anterior {old_pid} no activo, limpiando...")
                pid_file.unlink()
        except Exception as e:
            logger.warning(f"Error verificando PID: {e}")
            pid_file.unlink()
    
    # Crear archivo PID
    pid_file.parent.mkdir(exist_ok=True)
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))
    
    # Registrar limpieza al salir
    def cleanup():
        try:
            if pid_file.exists():
                pid_file.unlink()
                logger.info("Archivo PID eliminado")
        except Exception as e:
            logger.error(f"Error limpiando PID: {e}")
    
    atexit.register(cleanup)
    
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN no configurado en .env")
        return
    
    # Crear aplicación
    app = Application.builder().token(token).build()
    
    # Conversation handler para gestión de pedidos
    gestion_handler = ConversationHandler(
        entry_points=[CommandHandler('gestionar', lambda u, c: gestionar_pedidos_start(u, c, db))],
        states={
            GESTIONAR_BUSCAR_CLIENTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: gestionar_buscar_cliente(u, c, db))
            ],
            GESTIONAR_SELECCIONAR_CLIENTE: [
                CallbackQueryHandler(lambda u, c: gestionar_seleccionar_cliente(u, c, db), pattern="^gest_cliente_")
            ],
            GESTIONAR_SELECCIONAR_PEDIDO: [
                CallbackQueryHandler(lambda u, c: gestionar_seleccionar_pedido(u, c, db), pattern="^gest_pedido_")
            ],
            GESTIONAR_ELEGIR_ACCION: [
                CallbackQueryHandler(lambda u, c: gestionar_accion(u, c, db), pattern="^gest_")
            ]
        },
        fallbacks=[CommandHandler('cancelar', cancelar)]
    )
    
    # Conversation handler para pedidos
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('pedido', pedido_start)],
        states={
            BUSCAR_CLIENTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, pedido_buscar_cliente),
            ],
            SELECCIONAR_CLIENTE: [
                CallbackQueryHandler(pedido_seleccionar_cliente, pattern="^selcli_"),
            ],
            SELECCIONAR_PRODUCTO: [
                CallbackQueryHandler(seleccionar_producto, pattern="^producto_"),
                CallbackQueryHandler(mas_productos, pattern="^mas_productos$"),
                CallbackQueryHandler(seleccionar_producto, pattern="^finalizar$")
            ],
            CANTIDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_cantidad)],
            EDITAR_PRECIOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_precio_editado)],
            IVA: [CallbackQueryHandler(aplicar_iva, pattern="^iva_")],
            RECARGO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_recargo)],
            RECARGO_CONCEPTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nota_recargo)],
            CONFIRMAR: [
                CallbackQueryHandler(confirmar_pedido, pattern="^confirmar_")
            ]
        },
        fallbacks=[CommandHandler('cancelar', cancelar)]
    )
    
    # Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("productos", productos_command))
    app.add_handler(CommandHandler("clima", clima_command))
    app.add_handler(CommandHandler("mispedidos", mispedidos_command))
    app.add_handler(CommandHandler("shutdown", shutdown_command))
    
    # Handler para botones de reportes y shutdown
    app.add_handler(CallbackQueryHandler(reporte_button_handler, pattern="^rpt_"))
    app.add_handler(CallbackQueryHandler(shutdown_callback, pattern="^shutdown_"))
    
    # Conversation handlers (orden importa - más específicos primero)
    # DEBEN ir ANTES de MessageHandlers genéricos
    app.add_handler(gestion_handler)
    app.add_handler(conv_handler)
    
    # Handlers de admin
    app.add_handler(CommandHandler("reporte_diario", reporte_diario))
    app.add_handler(CommandHandler("reporte_semanal", reporte_semanal))
    app.add_handler(CommandHandler("reporte_mensual", reporte_mensual))
    app.add_handler(CommandHandler("excel_diario", excel_diario))
    app.add_handler(CommandHandler("excel_semanal", excel_semanal))
    app.add_handler(CommandHandler("excel_mensual", excel_mensual))

    # Conversation handler para maestro de clientes
    clientes_handler = ConversationHandler(
        entry_points=[CommandHandler('clientes', clientes_command)],
        states={
            CLIENTE_BUSCAR: [
                CallbackQueryHandler(clientes_menu_callback, pattern="^cli_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, clientes_buscar_texto),
            ],
            CLIENTE_NOMBRE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, clientes_nuevo_nombre),
            ],
            CLIENTE_TELEFONO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, clientes_nuevo_telefono),
            ],
            CLIENTE_EDITAR_CAMPO: [
                CallbackQueryHandler(clientes_menu_callback, pattern="^cli_"),
            ],
            CLIENTE_EDITAR_VALOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, clientes_editar_valor),
            ],
        },
        fallbacks=[CommandHandler('cancelar', clientes_cancelar)]
    )
    app.add_handler(clientes_handler)
    
    # Handler para recibir PIN de shutdown (AL FINAL - solo procesa si ningún ConversationHandler lo capturó)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_shutdown_pin))
    
    # Registrar comandos en el menú de Telegram
    commands = [
        BotCommand("start", "Iniciar y registrarse"),
        BotCommand("pedido", "Crear un nuevo pedido"),
        BotCommand("productos", "Ver menú y precios"),
        BotCommand("mispedidos", "Ver historial de pedidos"),
        BotCommand("clientes", "Gestionar clientes"),
        BotCommand("gestionar", "Gestionar estados de pedidos"),
        BotCommand("clima", "Pronóstico 5 días Santiago"),
        BotCommand("reporte_diario", "Reporte del día"),
        BotCommand("reporte_semanal", "Reporte de la semana"),
        BotCommand("reporte_mensual", "Reporte del mes"),
        BotCommand("shutdown", "Reiniciar tu PC"),
        BotCommand("help", "Mostrar ayuda"),
    ]
    
    async def set_commands(app_instance):
        await app_instance.bot.set_my_commands(commands)
    
    # Ejecutar set_commands cuando el bot inicie
    app.post_init = set_commands
    
    # Iniciar bot con manejo de conflictos
    logger.info("🤖 Bot iniciado correctamente")
    try:
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        if "Conflict: terminated by other getUpdates request" in str(e):
            logger.error("❌ CONFLICTO DETECTADO: Otro proceso está usando getUpdates")
            logger.error("   Hay múltiples instancias del bot corriendo")
            logger.error("   Ejecutar: taskkill /F /IM python.exe")
            print("\n❌ ERROR CRÍTICO:")
            print("   El bot detectó otro proceso usando getUpdates")
            print("   Acción: Reiniciar la PC para limpiar procesos huérfanos")
            sys.exit(1)
        else:
            logger.error(f"Error en polling: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    main()

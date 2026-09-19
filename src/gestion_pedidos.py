"""
Funciones para gestionar estados de pedidos
"""
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

# Importar estados (se definen en bot.py pero necesitamos los valores)
# Estos valores deben coincidir con los definidos en bot.py
GESTIONAR_BUSCAR_CLIENTE = 25
GESTIONAR_SELECCIONAR_CLIENTE = 26
GESTIONAR_SELECCIONAR_PEDIDO = 20
GESTIONAR_ELEGIR_ACCION = 21


def formatear_precio(precio: int) -> str:
    """Formatea un precio en CLP"""
    return f"${precio:,}".replace(",", ".")


def formatear_estado_pedido(pedido: dict) -> str:
    """Genera el texto del estado de un pedido"""
    estados = []
    
    if pedido['estado_entregado']:
        fecha_str = datetime.fromisoformat(pedido['fecha_entregado']).strftime('%d/%m %H:%M')
        estados.append(f"✅ Entregado ({fecha_str})")
    else:
        estados.append("⏳ Pendiente entrega")
    
    if pedido['estado_pagado']:
        fecha_str = datetime.fromisoformat(pedido['fecha_pagado']).strftime('%d/%m %H:%M')
        estados.append(f"💰 Pagado ({fecha_str})")
    else:
        estados.append("💳 Pendiente pago")
    
    return " | ".join(estados)


async def gestionar_pedidos_start(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """Inicia el proceso de gestionar pedidos (solo admin)"""
    user_id = update.effective_user.id
    admin_id = int(os.getenv('ADMIN_USER_ID', 0))
    
    if user_id != admin_id:
        await update.message.reply_text("No tienes permisos para este comando.")
        return ConversationHandler.END
    
    await update.message.reply_text(
        "🔧 *Gestionar Pedidos*\n\n"
        "Escribe el nombre del cliente para buscar sus pedidos:",
        parse_mode='Markdown'
    )
    
    return GESTIONAR_BUSCAR_CLIENTE


async def gestionar_buscar_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """Busca un cliente y muestra sus pedidos"""
    texto = update.message.text.strip()
    clientes = db.buscar_clientes(texto)
    
    if not clientes:
        await update.message.reply_text(
            f"No se encontró ningún cliente con '{texto}'.\n\n"
            "Intenta de nuevo o usa /cancelar"
        )
        return GESTIONAR_BUSCAR_CLIENTE
    
    if len(clientes) == 1:
        # Solo un cliente encontrado, mostrar sus pedidos
        cliente = clientes[0]
        return await mostrar_pedidos_cliente(update, context, db, cliente.id)
    
    # Múltiples clientes, mostrar para seleccionar
    keyboard = []
    for c in clientes[:10]:  # Max 10
        keyboard.append([
            InlineKeyboardButton(
                f"{c.nombre} - {c.telefono or 'Sin teléfono'}",
                callback_data=f"gest_cliente_{c.id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="gest_cancelar")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Selecciona el cliente:",
        reply_markup=reply_markup
    )
    
    return GESTIONAR_SELECCIONAR_CLIENTE


async def gestionar_seleccionar_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """Maneja la selección de cliente"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "gest_cancelar":
        await query.edit_message_text("Operación cancelada.")
        return ConversationHandler.END
    
    # Extraer cliente_id
    cliente_id = int(query.data.split("_")[2])
    
    return await mostrar_pedidos_cliente(update, context, db, cliente_id, edit_query=query)


async def mostrar_pedidos_cliente(update: Update, context: ContextTypes.DEFAULT_TYPE, db, cliente_id: int, edit_query=None):
    """Muestra los pedidos recientes de un cliente (últimos 30 días)"""
    cliente = db.obtener_cliente_por_id(cliente_id)
    pedidos = db.obtener_pedidos_recientes(cliente_id, dias=30)
    
    if not pedidos:
        msg = f"El cliente *{cliente.nombre}* no tiene pedidos en los últimos 30 días."
        if edit_query:
            await edit_query.edit_message_text(msg, parse_mode='Markdown')
        else:
            await update.message.reply_text(msg, parse_mode='Markdown')
        return ConversationHandler.END
    
    # Guardar info en contexto
    context.user_data['gest_cliente_id'] = cliente_id
    context.user_data['gest_cliente_nombre'] = cliente.nombre
    
    # Crear botones de pedidos
    keyboard = []
    for p in pedidos:
        fecha = datetime.fromisoformat(p['fecha']).strftime('%d/%m')
        
        # Emojis de estado más cortos
        emoji_entrega = "✅" if p['estado_entregado'] else "⏳"
        emoji_pago = "💰" if p['estado_pagado'] else "💳"
        
        # Texto compacto para el botón
        texto_btn = f"{p['numero_pedido']} ({fecha}) {emoji_entrega}{emoji_pago} - {formatear_precio(p['total'])}"
        
        keyboard.append([
            InlineKeyboardButton(
                texto_btn,
                callback_data=f"gest_pedido_{p['id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("❌ Cancelar", callback_data="gest_cancelar")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    mensaje = f"📋 *Pedidos de {cliente.nombre}* (últimos 30 días)\n\n"
    mensaje += f"Total: {len(pedidos)} pedidos\n\n"
    mensaje += "*Leyenda:*\n"
    mensaje += "✅ Entregado | ⏳ Pendiente entrega\n"
    mensaje += "💰 Pagado | 💳 Pendiente pago\n\n"
    mensaje += "Selecciona un pedido para gestionar:"
    
    if edit_query:
        await edit_query.edit_message_text(mensaje, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(mensaje, reply_markup=reply_markup, parse_mode='Markdown')
    
    return GESTIONAR_SELECCIONAR_PEDIDO


async def gestionar_seleccionar_pedido(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """Maneja la selección de un pedido específico"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "gest_cancelar":
        await query.edit_message_text("Operación cancelada.")
        return ConversationHandler.END
    
    # Extraer pedido_id
    pedido_id = int(query.data.split("_")[2])
    context.user_data['gest_pedido_id'] = pedido_id
    
    # Obtener detalle del pedido
    detalle = db.obtener_detalle_pedido(pedido_id)
    cliente_nombre = context.user_data.get('gest_cliente_nombre', 'Cliente')

    if detalle is None:
        await query.edit_message_text("❌ No se encontró el pedido. Puede haber sido eliminado.")
        return ConversationHandler.END

    # Mostrar detalle y opciones
    mensaje = f"📦 *Pedido {detalle['numero_pedido']}*\n\n"
    mensaje += f"👤 Cliente: {cliente_nombre}\n"
    mensaje += f"📅 Fecha: {datetime.fromisoformat(detalle['fecha']).strftime('%d/%m/%Y %H:%M')}\n"
    mensaje += f"💰 Total: {formatear_precio(detalle['total'])}\n\n"
    
    mensaje += "*Estado actual:*\n"
    if detalle['estado_entregado']:
        fecha_ent = datetime.fromisoformat(detalle['fecha_entregado']).strftime('%d/%m %H:%M')
        mensaje += f"✅ Entregado: {fecha_ent}\n"
    else:
        mensaje += "⏳ Pendiente de entrega\n"
    
    if detalle['estado_pagado']:
        fecha_pag = datetime.fromisoformat(detalle['fecha_pagado']).strftime('%d/%m %H:%M')
        mensaje += f"💰 Pagado: {fecha_pag}\n"
    else:
        mensaje += "💳 Pendiente de pago\n"
    
    # Botones de acciones
    keyboard = []
    
    if detalle['estado_entregado']:
        keyboard.append([InlineKeyboardButton("📦 Marcar como NO entregado", callback_data="gest_entregar_0")])
    else:
        keyboard.append([InlineKeyboardButton("✅ Marcar como entregado", callback_data="gest_entregar_1")])
    
    if detalle['estado_pagado']:
        keyboard.append([InlineKeyboardButton("💳 Marcar como NO pagado", callback_data="gest_pagar_0")])
    else:
        keyboard.append([InlineKeyboardButton("💰 Marcar como pagado", callback_data="gest_pagar_1")])
    
    keyboard.append([InlineKeyboardButton("◀️ Volver a lista", callback_data="gest_volver")])
    keyboard.append([InlineKeyboardButton("❌ Salir", callback_data="gest_cancelar")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(mensaje, reply_markup=reply_markup, parse_mode='Markdown')
    
    return GESTIONAR_ELEGIR_ACCION


async def gestionar_accion(update: Update, context: ContextTypes.DEFAULT_TYPE, db):
    """Ejecuta la acción seleccionada sobre el pedido"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "gest_cancelar":
        await query.edit_message_text("✅ Operación finalizada.")
        return ConversationHandler.END
    
    if query.data == "gest_volver":
        cliente_id = context.user_data.get('gest_cliente_id')
        return await mostrar_pedidos_cliente(update, context, db, cliente_id, edit_query=query)
    
    pedido_id = context.user_data.get('gest_pedido_id')
    
    if query.data.startswith("gest_entregar_"):
        estado = bool(int(query.data.split("_")[2]))
        if db.actualizar_estado_entregado(pedido_id, estado):
            await query.answer(f"✅ Estado de entrega actualizado", show_alert=True)
        else:
            await query.answer("❌ Error al actualizar", show_alert=True)
        
        # Refrescar vista del pedido
        return await gestionar_seleccionar_pedido(update, context, db)
    
    if query.data.startswith("gest_pagar_"):
        estado = bool(int(query.data.split("_")[2]))
        if db.actualizar_estado_pagado(pedido_id, estado):
            await query.answer(f"✅ Estado de pago actualizado", show_alert=True)
        else:
            await query.answer("❌ Error al actualizar", show_alert=True)
        
        # Refrescar vista del pedido
        return await gestionar_seleccionar_pedido(update, context, db)
    
    return GESTIONAR_ELEGIR_ACCION


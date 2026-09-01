import json
import os
import logging
import requests
from telegram import (
    Update, 
    ReplyKeyboardMarkup, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    InputMediaPhoto
)
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler, 
    filters, 
    ContextTypes
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

DB_FILE = "/app_data/dispositivos.json"

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_PIN = os.getenv("ADMIN_PIN", "1234")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")

raw_tokens = os.getenv("API_TOKENS", "")
API_TOKENS = [token.strip() for token in raw_tokens.split(",") if token.strip()]

# -------------------------------------------------------------------
# ENLACES Y RECURSOS DE LA GUÍA (Personaliza con tus URLs/IDs de imagen)
# -------------------------------------------------------------------
URL_APK_ANDROID = "https://apkpure.com/es/search?q=Smarters+Player+Lite"
URL_APP_WINDOWS = "https://apps.microsoft.com/detail/9nrp2lhsh4mf?hl=es-ES&gl=ES"
URL_VIDEO_SMARTTV = "https://www.youtube.com/watch?v=_45J8kBu2CY"

# URLs o File IDs de las 3 imágenes de configuración
IMAGENES_CONFIGURACION = [
    "https://via.placeholder.com/800x600.png?text=Paso+1+Configuracion",
    "https://via.placeholder.com/800x600.png?text=Paso+2+Configuracion",
    "https://via.placeholder.com/800x600.png?text=Paso+3+Configuracion"
]


def load_data():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_data(data):
    dir_name = os.path.dirname(DB_FILE)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)

    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def get_main_keyboard():
    keyboard = [
        ["📲 Solicitar o renovar línea"],
        ["🔄 Refrescar Códigos"],
        ["📖 Guía"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def delete_user_message_safety(update: Update):
    try:
        await update.message.delete()
    except Exception as e:
        logging.warning(f"No se pudo borrar el mensaje del usuario: {e}")


# -------------------------------------------------------------------
# MENÚS INLINE PARA LA SECCIÓN "GUÍA"
# -------------------------------------------------------------------
def menu_guia_principal():
    keyboard = [
        [InlineKeyboardButton("📱 Apps", callback_data="guia_apps")],
        [InlineKeyboardButton("⚙️ Configuración", callback_data="guia_config")]
    ]
    return InlineKeyboardMarkup(keyboard)


def menu_guia_apps():
    keyboard = [
        [InlineKeyboardButton("🤖 Android (APK)", url=URL_APK_ANDROID)],
        [InlineKeyboardButton("💻 Windows", url=URL_APP_WINDOWS)],
        [InlineKeyboardButton("📺 Smart TV (Vídeo)", url=URL_VIDEO_SMARTTV)],
        [InlineKeyboardButton("⬅️ Volver a Guía", callback_data="guia_inicio")]
    ]
    return InlineKeyboardMarkup(keyboard)


def menu_volver_guia():
    keyboard = [
        [InlineKeyboardButton("⬅️ Volver a Guía", callback_data="guia_inicio")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    devices = load_data()
    reply_markup = get_main_keyboard()

    if user_id not in devices:
        await update.message.reply_text(
            "⛔ Este dispositivo no está registrado.\n"
            "Usa `/setid <PIN> <ID_Suscripcion>` para registrarte.",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            f"Bienvenido. Tu ID de suscripción registrado es: `{devices[user_id]}`",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )


async def set_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_user_message_safety(update)

    user_id = str(update.effective_user.id)
    args = context.args

    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ Uso correcto: `/setid <PIN> <ID_Suscripcion>`",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return

    pin, sub_id = args[0], args[1]

    if pin != ADMIN_PIN:
        await update.message.reply_text("❌ PIN incorrecto.", reply_markup=get_main_keyboard())
        return

    devices = load_data()
    devices[user_id] = sub_id
    save_data(devices)

    await update.message.reply_text(
        f"✅ Dispositivo registrado correctamente con la suscripción ID: `{sub_id}`",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )


async def borrar_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await delete_user_message_safety(update)

    user_id = str(update.effective_user.id)
    args = context.args
    devices = load_data()

    if len(args) == 2:
        pin, target_id = args[0], args[1]
        if pin != ADMIN_PIN:
            await update.message.reply_text("❌ PIN incorrecto.", reply_markup=get_main_keyboard())
            return
        if target_id in devices:
            removed = devices.pop(target_id)
            save_data(devices)
            await update.message.reply_text(f"🗑️ Registro ({target_id}) eliminado.", reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text("⚠️ ID no encontrado.", reply_markup=get_main_keyboard())
        return

    if user_id in devices:
        removed = devices.pop(user_id)
        save_data(devices)
        await update.message.reply_text("🗑️ Tu suscripción vinculada ha sido eliminada.", reply_markup=get_main_keyboard())
    else:
        await update.message.reply_text("⚠️ Este dispositivo no está registrado.", reply_markup=get_main_keyboard())


async def fetch_subscription(sub_id: str):
    for idx, token in enumerate(API_TOKENS):
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json"
        }
        
        urls = [
            f"https://megaott.net/api/v1/subscriptions/{sub_id}/",
            f"https://megaott.net/api/v1/subscriptions/{sub_id}"
        ]

        for url in urls:
            try:
                logging.info(f"Probando token índice {idx} en URL: {url}")
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                logging.error(f"Error consultando la API en {url}: {e}")

    return None


async def handle_refrescar_codigos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    devices = load_data()

    if user_id not in devices:
        await update.message.reply_text(
            "⛔ Necesitas estar registrado para solicitar códigos.\n",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return

    sub_id = devices[user_id]
    data = await fetch_subscription(sub_id)

    if data:
        username = data.get("username", "N/A")
        password = data.get("password", "N/A")
        dns_link = data.get("dns_link", "N/A")
        dns_samsung_lg = data.get("dns_link_for_samsung_lg", "N/A")
        expiring_at = data.get("expiring_at", "N/A")

        msg = (
            f"📺 *TUS DATOS DE ACCESO*\n\n"
            f"👤 *Usuario:* `{username}`\n"
            f"🔑 *Contraseña:* `{password}`\n"
            f"🌐 *URL / Server:* `{dns_link}`\n"
            f"📺 *URL Samsung / LG:* `{dns_samsung_lg}`\n"
            f"📅 *Caduca el:* `{expiring_at}`"
        )
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=get_main_keyboard())
    else:
        await update.message.reply_text(
            f"⚠️ No se encontraron datos para el ID (`{sub_id}`) en ninguna de las cuentas vinculadas.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )


async def handle_renovacion_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    devices = load_data()
    username_str = f"@{user.username}" if user.username else "Sin username"

    if user_id in devices:
        sub_id = devices[user_id]
        await update.message.reply_text(
            f"✅ Solicitud enviada para la línea/ID: *{sub_id}*.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        if ADMIN_CHAT_ID:
            admin_msg = (
                f"🔄 *SOLICITUD DE RENOVACIÓN*\n\n"
                f"👤 *Usuario:* {user.first_name} ({username_str})\n"
                f"🏷️ *ID Suscripción:* `{sub_id}`\n"
                f"💬 *Chat Directo:* [Abrir conversación](tg://user?id={user.id})"
            )
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode="Markdown")
    else:
        contact_button = KeyboardButton(text="📱 Compartir mi número de teléfono", request_contact=True)
        reply_markup = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(
            "Para solicitar una nueva línea, comparte tu número de contacto usando el botón inferior:",
            reply_markup=reply_markup
        )


async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    user = update.effective_user
    username_str = f"@{user.username}" if user.username else "Sin username"

    await update.message.reply_text(
        "✅ Solicitud recibida. Nos pondremos en contacto contigo.",
        reply_markup=get_main_keyboard()
    )

    if ADMIN_CHAT_ID:
        admin_msg = (
            f"🆕 *NUEVA SOLICITUD DE LÍNEA*\n\n"
            f"👤 *Usuario:* {user.first_name} ({username_str})\n"
            f"📞 *Teléfono:* `{contact.phone_number}`\n"
            f"💬 *Chat Directo:* [Abrir conversación](tg://user?id={user.id})"
        )
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode="Markdown")


# -------------------------------------------------------------------
# LÓGICA DE MANEJO DE LA GUÍA
# -------------------------------------------------------------------
async def handle_guia_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde al botón del teclado principal '📖 Guía'"""
    await update.message.reply_text(
        "📚 *GUÍA DE INSTALACIÓN Y CONFIGURACIÓN*\n\nSelecciona una opción del menú:",
        parse_mode="Markdown",
        reply_markup=menu_guia_principal()
    )


async def handle_guia_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja los clics en los botones interactivos del menú Guía"""
    query = update.callback_query
    await query.answer()

    if query.data == "guia_inicio":
        await query.edit_message_text(
            "📚 *GUÍA DE INSTALACIÓN Y CONFIGURACIÓN*\n\nSelecciona una opción del menú:",
            parse_mode="Markdown",
            reply_markup=menu_guia_principal()
        )

    elif query.data == "guia_apps":
        await query.edit_message_text(
            "📱 *DESCARGA DE APLICACIONES*\n\nElige la plataforma donde vas a usar el servicio:",
            parse_mode="Markdown",
            reply_markup=menu_guia_apps()
        )

    elif query.data == "guia_config":
        await query.edit_message_text("⏳ Cargando imágenes de configuración...")

        # Preparamos el grupo de imágenes en álbum (MediaGroup)
        media = [
            InputMediaPhoto(media=IMAGENES_CONFIGURACION[0], caption="⚙️ *PASOS DE CONFIGURACIÓN*\n\n1. Sigue las instrucciones de cada captura.", parse_mode="Markdown"),
            InputMediaPhoto(media=IMAGENES_CONFIGURACION[1]),
            InputMediaPhoto(media=IMAGENES_CONFIGURACION[2])
        ]

        # Enviamos las 3 imágenes en un solo mensaje de tipo álbum
        await context.bot.send_media_group(chat_id=query.message.chat_id, media=media)
        
        # Enviamos un mensaje final con botón para poder regresar
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="¿Quieres volver al menú anterior?",
            reply_markup=menu_volver_guia()
        )


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise ValueError("Error: BOT_TOKEN no está definido en las variables de entorno.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers de comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setid", set_id))
    app.add_handler(CommandHandler("borrarid", borrar_id))
    
    # Handlers de mensajes de texto (Botones de pantalla)
    app.add_handler(MessageHandler(filters.Regex("^📲 Solicitar o renovar línea$"), handle_renovacion_request))
    app.add_handler(MessageHandler(filters.Regex("^🔄 Refrescar Códigos$"), handle_refrescar_codigos))
    app.add_handler(MessageHandler(filters.Regex("^📖 Guía$"), handle_guia_button))
    app.add_handler(MessageHandler(filters.CONTACT, receive_contact))

    # Handler para los botones interactivos inline
    app.add_handler(CallbackQueryHandler(handle_guia_callbacks))

    print("🤖 Bot listo...")
    app.run_polling()

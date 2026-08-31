import json
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Ruta de persistencia dentro del contenedor TrueNAS
DB_FILE = "/app_data/dispositivos.json"

# Variables de entorno seguras (configuradas en la app de TrueNAS)
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_PIN = os.getenv("ADMIN_PIN", "1234")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")


def load_data():
    """Carga el registro de dispositivos."""
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_data(data):
    """Guarda los cambios en dispositivos.json."""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start con el menú principal."""
    user_id = str(update.effective_user.id)
    devices = load_data()

    is_registered = user_id in devices
    device_label = devices[user_id] if is_registered else "No registrado"

    # Teclado visible para todos los usuarios
    keyboard = [
        ["📲 Solicitar o renovar línea"],
        ["🔄 Refrescar Códigos"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    if is_registered:
        msg = f"Bienvenido/a *{device_label}*. ¿Qué deseas hacer?"
    else:
        msg = (
            "Bienvenido/a al bot de gestión de líneas.\n\n"
            "Si deseas renovar o solicitar una nueva línea, pulsa el botón de abajo."
        )

    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")


async def set_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para que un administrador registre o vincule un dispositivo."""
    user_id = str(update.effective_user.id)
    args = context.args

    if len(args) < 2:
        await update.message.reply_text("Uso correcto: /setid <PIN> <NombreDispositivo>")
        return

    pin = args[0]
    dev_name = " ".join(args[1:])

    if pin != ADMIN_PIN:
        await update.message.reply_text("❌ PIN incorrecto.")
        return

    devices = load_data()
    devices[user_id] = dev_name
    save_data(devices)

    await update.message.reply_text(f"✅ Dispositivo '{dev_name}' registrado e identificado correctamente.")


async def handle_renovacion_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestiona la solicitud según si el usuario tiene ID guardado o no."""
    user = update.effective_user
    user_id = str(user.id)
    devices = load_data()
    username_str = f"@{user.username}" if user.username else "Sin username"

    # CASO 1: El usuario YA está registrado (tiene línea/dispositivo asignado)
    if user_id in devices:
        device_name = devices[user_id]
        
        await update.message.reply_text(
            f"✅ Gracias {user.first_name}. Hemos notificado al administrador tu solicitud de renovación para la línea/dispositivo: *{device_name}*.",
            parse_mode="Markdown"
        )

        if ADMIN_CHAT_ID:
            admin_msg = (
                f"🔄 *SOLICITUD DE RENOVACIÓN (USUARIO REGISTRADO)*\n\n"
                f"👤 *Usuario:* {user.first_name} ({username_str})\n"
                f"🏷️ *Línea / Dispositivo:* `{device_name}`\n"
                f"🆔 *Telegram ID:* `{user.id}`\n"
                f"💬 *Chat Directo:* [Abrir conversación](tg://user?id={user.id})"
            )
            try:
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode="Markdown")
            except Exception as e:
                print(f"Error enviando aviso al admin: {e}")

    # CASO 2: Usuario NUEVO (No está en el JSON)
    else:
        # Le pedimos compartir su número de teléfono con botón nativo
        contact_button = KeyboardButton(text="📱 Compartir mi número de teléfono", request_contact=True)
        reply_markup = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True, one_time_keyboard=True)

        await update.message.reply_text(
            "Para gestionar tu nueva línea, por favor pulsa el botón de abajo para compartir tu número de teléfono:",
            reply_markup=reply_markup
        )


async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el teléfono de un usuario no registrado y te envía sus datos."""
    contact = update.message.contact
    user = update.effective_user
    username_str = f"@{user.username}" if user.username else "Sin username"

    reply_markup = ReplyKeyboardRemove()
    await update.message.reply_text(
        "✅ Gracias. Tu solicitud ha sido enviada al administrador. Se pondrá en contacto contigo muy pronto.",
        reply_markup=reply_markup
    )

    if ADMIN_CHAT_ID:
        admin_msg = (
            f"🆕 *NUEVA SOLICITUD DE LÍNEA (USUARIO NUEVO)*\n\n"
            f"👤 *Usuario:* {user.first_name} ({username_str})\n"
            f"📞 *Teléfono:* `{contact.phone_number}`\n"
            f"🆔 *Telegram ID:* `{user.id}`\n"
            f"💬 *Chat Directo:* [Abrir conversación](tg://user?id={user.id})"
        )
        try:
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode="Markdown")
        except Exception as e:
            print(f"Error enviando contacto al admin: {e}")


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN no configurado en las variables de entorno.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setid", set_id))
    app.add_handler(MessageHandler(filters.Regex("^📲 Solicitar o renovar línea$"), handle_renovacion_request))
    app.add_handler(MessageHandler(filters.CONTACT, receive_contact))

    print("🤖 Bot listo y escuchando peticiones...")
    app.run_polling()

import json
import os
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Ruta del archivo JSON dentro del volumen montado en TrueNAS
DB_FILE = "/app_data/dispositivos.json"

# Lectura segura de variables de entorno de TrueNAS
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_PIN = os.getenv("ADMIN_PIN", "1234")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")


def load_data():
    """Carga los datos guardados en el archivo JSON."""
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_data(data):
    """Guarda los datos en el archivo JSON."""
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja el comando /start con el menú principal."""
    user = update.effective_user
    user_id = str(user.id)
    devices = load_data()

    is_registered = user_id in devices
    device_label = devices[user_id] if is_registered else "No registrado"

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
            "Si deseas vincular tu dispositivo con un PIN, usa:\n"
            "`/setid <PIN> <Nombre_Opcional>`\n\n"
            "Si deseas renovar o solicitar una nueva línea, pulsa el botón de abajo."
        )

    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")


async def set_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Vincular dispositivo con PIN."""
    user = update.effective_user
    user_id = str(user.id)
    args = context.args

    if not args:
        await update.message.reply_text(
            "⚠️ *Formato incorrecto.*\nEscribe: `/setid <PIN> <Nombre_Opcional>`\nEjemplo: `/setid 1234 MovilMario`",
            parse_mode="Markdown"
        )
        return

    pin = args[0].strip()
    dev_name = " ".join(args[1:]).strip() if len(args) > 1 else (user.first_name or "Usuario")

    if pin != str(ADMIN_PIN).strip():
        await update.message.reply_text("❌ *PIN incorrecto.*", parse_mode="Markdown")
        return

    devices = load_data()
    devices[user_id] = dev_name
    save_data(devices)

    keyboard = [
        ["📲 Solicitar o renovar línea"],
        ["🔄 Refrescar Códigos"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    await update.message.reply_text(
        f"✅ *¡Dispositivo vinculado con éxito!*\n\n"
        f"👤 *Nombre registrado:* {dev_name}\n"
        f"🆔 *ID Telegram:* `{user_id}`\n\n"
        f"Ya puedes solicitar o renovar tus líneas normalmente.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )


async def borrar_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Desvincular dispositivo."""
    user = update.effective_user
    user_id = str(user.id)
    args = context.args
    devices = load_data()

    # Opción Admin: /borrarid <PIN> <ID_TELEGRAM>
    if len(args) >= 2:
        pin = args[0].strip()
        target_id = args[1].strip()
        
        if pin != str(ADMIN_PIN).strip():
            await update.message.reply_text("❌ *PIN incorrecto.*", parse_mode="Markdown")
            return

        if target_id in devices:
            removed_name = devices.pop(target_id)
            save_data(devices)
            await update.message.reply_text(f"🗑️ Se ha borrado el ID `{target_id}` ({removed_name}).", parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ Ese ID no se encuentra en la base de datos.")
        return

    # Opción Usuario: Borra su propia línea
    if user_id in devices:
        removed_name = devices.pop(user_id)
        save_data(devices)
        await update.message.reply_text(f"🗑️ Tu línea/dispositivo *{removed_name}* ha sido eliminada del registro.", parse_mode="Markdown")
    else:
        await update.message.reply_text("⚠️ Este dispositivo no estaba registrado.")


async def handle_renovacion_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestiona la solicitud según si el usuario está en dispositivos.json o no."""
    user = update.effective_user
    user_id = str(user.id)
    devices = load_data()
    username_str = f"@{user.username}" if user.username else "Sin username"

    # CASO 1: El usuario YA está registrado en dispositivos.json
    if user_id in devices:
        device_name = devices[user_id]
        
        await update.message.reply_text(
            f"✅ Gracias {user.first_name}. Hemos notificado al administrador tu solicitud de renovación para la línea/dispositivo: *{device_name}*.",
            parse_mode="Markdown"
        )

        if ADMIN_CHAT_ID:
            admin_msg = (
                f"🔄 *SOLICITUD DE RENOVACIÓN (LÍNEA REGISTRADA)*\n\n"
                f"👤 *Usuario:* {user.first_name} ({username_str})\n"
                f"🏷️ *Línea/Dispositivo:* `{device_name}`\n"
                f"🆔 *Telegram ID:* `{user.id}`\n"
                f"💬 *Chat Directo:* [Abrir conversación](tg://user?id={user.id})"
            )
            try:
                await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode="Markdown")
            except Exception as e:
                print(f"Error enviando aviso al admin: {e}")

    # CASO 2: Usuario NUEVO (No está registrado)
    else:
        contact_button = KeyboardButton(text="📱 Compartir mi número de teléfono", request_contact=True)
        reply_markup = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True, one_time_keyboard=True)

        await update.message.reply_text(
            "Para solicitar una nueva línea, por favor pulsa el botón de abajo para enviar tu teléfono de contacto:",
            reply_markup=reply_markup
        )


async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el teléfono de un usuario no registrado y lo envía al admin."""
    contact = update.message.contact
    user = update.effective_user
    username_str = f"@{user.username}" if user.username else "Sin username"

    reply_markup = ReplyKeyboardRemove()
    await update.message.reply_text(
        "✅ Solicitud enviada correctamente. Te contactaremos en breve.",
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

    # Handlers para comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setid", set_id))
    app.add_handler(CommandHandler("borrarid", borrar_id))

    # Handlers para mensajes de texto y botones de contacto
    app.add_handler(MessageHandler(filters.Regex("^📲 Solicitar o renovar línea$"), handle_renovacion_request))
    app.add_handler(MessageHandler(filters.CONTACT, receive_contact))

    print("🤖 Bot listo y escuchando peticiones...")
    app.run_polling()

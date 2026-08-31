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
    """Comando /start"""
    user_id = str(update.effective_user.id)
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
            "Si ya tienes una línea asignada y deseas vincular este dispositivo, utiliza:\n"
            "`/setid <PIN> <NombreDispositivo>`\n\n"
            "Si eres un nuevo usuario o quieres renovar, pulsa el botón de abajo."
        )

    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")


async def set_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asocia un ID de Telegram a una línea/dispositivo usando el PIN."""
    user_id = str(update.effective_user.id)
    args = context.args

    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ *Uso incorrecto.*\nDebes escribir: `/setid <PIN> <NombreDispositivo>`\n"
            "Ejemplo: `/setid 1234 MovilMario`",
            parse_mode="Markdown"
        )
        return

    pin = args[0]
    dev_name = " ".join(args[1:])

    if pin != ADMIN_PIN:
        await update.message.reply_text("❌ *PIN incorrecto.*", parse_mode="Markdown")
        return

    devices = load_data()
    devices[user_id] = dev_name
    save_data(devices)

    await update.message.reply_text(
        f"✅ *Dispositivo vinculado con éxito.*\n"
        f"🆔 ID de Telegram: `{user_id}`\n"
        f"🏷️ Nombre: *{dev_name}*",
        parse_mode="Markdown"
    )


async def borrar_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Elimina la vinculación del dispositivo actual o de un usuario específico."""
    user_id = str(update.effective_user.id)
    args = context.args
    devices = load_data()

    # Si se pasa un PIN y un ID (Ejemplo: /borrarid <PIN> <ID_TELEGRAM>)
    if len(args) == 2:
        pin, target_id = args[0], args[1]
        if pin != ADMIN_PIN:
            await update.message.reply_text("❌ *PIN incorrecto.*", parse_mode="Markdown")
            return
        
        if target_id in devices:
            removed_name = devices.pop(target_id)
            save_data(devices)
            await update.message.reply_text(
                f"🗑️ *Dispositivo eliminado.*\nSe ha desvinculado a: *{removed_name}* (`{target_id}`).",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text("⚠️ Ese ID de Telegram no está en el registro.")
        return

    # Si el usuario quiere desvincular su propio dispositivo
    if user_id in devices:
        removed_name = devices.pop(user_id)
        save_data(devices)
        await update.message.reply_text(
            f"🗑️ Tu dispositivo *{removed_name}* ha sido desvinculado correctamente.",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text("⚠️ Este dispositivo no estaba registrado.")


async def handle_renovacion_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la solicitud de línea."""
    user = update.effective_user
    user_id = str(user.id)
    devices = load_data()
    username_str = f"@{user.username}" if user.username else "Sin username"

    # Caso A: Dispositivo Registrado
    if user_id in devices:
        device_name = devices[user_id]
        await update.message.reply_text(
            f"✅ Solicitud recibida para tu línea/dispositivo: *{device_name}*.\n"
            f"Un administrador revisará la renovación.",
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
                print(f"Error al avisar al admin: {e}")

    # Caso B: Usuario No Registrado
    else:
        contact_button = KeyboardButton(text="📱 Compartir mi número de teléfono", request_contact=True)
        reply_markup = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True, one_time_keyboard=True)

        await update.message.reply_text(
            "Para solicitar una nueva línea, por favor pulsa el botón de abajo para enviar tu teléfono de contacto:",
            reply_markup=reply_markup
        )


async def receive_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el teléfono enviado por un usuario no registrado."""
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
            print(f"Error al enviar contacto al admin: {e}")


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN no configurado en las variables de entorno.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Handlers para comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setid", set_id))
    app.add_handler(CommandHandler("borrarid", borrar_id))

    # Handlers de mensajes y contactos
    app.add_handler(MessageHandler(filters.Regex("^📲 Solicitar o renovar línea$"), handle_renovacion_request))
    app.add_handler(MessageHandler(filters.CONTACT, receive_contact))

    print("🤖 Bot listo y escuchando peticiones...")
    app.run_polling()

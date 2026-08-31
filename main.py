import json
import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

DB_FILE = "/app_data/dispositivos.json"

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_PIN = os.getenv("ADMIN_PIN", "1234")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")


def load_data():
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_data(data):
    # Asegura que la carpeta contenedora exista antes de escribir el archivo
    dir_name = os.path.dirname(DB_FILE)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)

    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    devices = load_data()

    if user_id not in devices:
        await update.message.reply_text(
            "⛔ Este dispositivo no está autorizado.\n"
            "Usa `/setid <PIN> <Nombre>` para registrarte.",
            parse_mode="Markdown"
        )
        return

    keyboard = [
        ["📲 Solicitar o renovar línea"],
        ["🔄 Refrescar Códigos"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(f"Bienvenido {devices[user_id]}. ¿Qué deseas hacer?", reply_markup=reply_markup)


async def set_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    args = context.args

    if len(args) < 2:
        await update.message.reply_text("Uso correcto: /setid <PIN> <NombreDispositivo>")
        return

    pin, dev_name = args[0], " ".join(args[1:])

    if pin != ADMIN_PIN:
        await update.message.reply_text("❌ PIN incorrecto.")
        return

    devices = load_data()
    devices[user_id] = dev_name
    save_data(devices)
    
    keyboard = [
        ["📲 Solicitar o renovar línea"],
        ["🔄 Refrescar Códigos"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(f"✅ Dispositivo '{dev_name}' registrado correctamente.", reply_markup=reply_markup)


async def borrar_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    args = context.args
    devices = load_data()

    if len(args) == 2:
        pin, target_id = args[0], args[1]
        if pin != ADMIN_PIN:
            await update.message.reply_text("❌ PIN incorrecto.")
            return
        if target_id in devices:
            removed = devices.pop(target_id)
            save_data(devices)
            await update.message.reply_text(f"🗑️ Dispositivo '{removed}' ({target_id}) eliminado.")
        else:
            await update.message.reply_text("⚠️ ID no encontrado.")
        return

    if user_id in devices:
        removed = devices.pop(user_id)
        save_data(devices)
        await update.message.reply_text(f"🗑️ Tu dispositivo '{removed}' ha sido eliminado.", reply_markup=ReplyKeyboardRemove())
    else:
        await update.message.reply_text("⚠️ Este dispositivo no está registrado.")


async def handle_renovacion_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    devices = load_data()
    username_str = f"@{user.username}" if user.username else "Sin username"

    if user_id in devices:
        device_name = devices[user_id]
        await update.message.reply_text(
            f"✅ Solicitud enviada para la línea: *{device_name}*.",
            parse_mode="Markdown"
        )
        if ADMIN_CHAT_ID:
            admin_msg = (
                f"🔄 *SOLICITUD DE RENOVACIÓN*\n\n"
                f"👤 *Usuario:* {user.first_name} ({username_str})\n"
                f"🏷️ *Dispositivo:* `{device_name}`\n"
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

    reply_markup = ReplyKeyboardRemove()
    await update.message.reply_text("✅ Solicitud recibida. Nos pondremos en contacto contigo.", reply_markup=reply_markup)

    if ADMIN_CHAT_ID:
        admin_msg = (
            f"🆕 *NUEVA SOLICITUD DE LÍNEA*\n\n"
            f"👤 *Usuario:* {user.first_name} ({username_str})\n"
            f"📞 *Teléfono:* `{contact.phone_number}`\n"
            f"💬 *Chat Directo:* [Abrir conversación](tg://user?id={user.id})"
        )
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode="Markdown")


if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setid", set_id))
    app.add_handler(CommandHandler("borrarid", borrar_id))
    app.add_handler(MessageHandler(filters.Regex("^📲 Solicitar o renovar línea$"), handle_renovacion_request))
    app.add_handler(MessageHandler(filters.CONTACT, receive_contact))

    print("🤖 Bot listo...")
    app.run_polling()

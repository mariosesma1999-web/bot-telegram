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
    dir_name = os.path.dirname(DB_FILE)
    if dir_name and not os.path.exists(dir_name):
        os.makedirs(dir_name, exist_ok=True)

    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def get_main_keyboard():
    keyboard = [
        ["📲 Solicitar o renovar línea"],
        ["🔄 Refrescar Códigos"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


async def delete_user_message_safety(update: Update):
    """Intenta borrar el mensaje del usuario que contiene credenciales o PIN."""
    try:
        await update.message.delete()
    except Exception as e:
        logging.warning(f"No se pudo borrar el mensaje del usuario: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    devices = load_data()

    # Se muestran las opciones SIEMPRE independientemente de si está registrado
    reply_markup = get_main_keyboard()

    if user_id not in devices:
        await update.message.reply_text(
            "⛔ Este dispositivo no está registrado.\n"
            "Puedes usar `/setid <PIN> <Nombre>` para vincularlo o solicitar/renovar tu línea abajo.",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            f"Bienvenido {devices[user_id]}. ¿Qué deseas hacer?",
            reply_markup=reply_markup
        )


async def set_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Borrar mensaje del usuario por seguridad (PIN expuesto)
    await delete_user_message_safety(update)

    user_id = str(update.effective_user.id)
    args = context.args

    if len(args) < 2:
        await update.message.reply_text(
            "⚠️ Uso correcto: `/setid <PIN> <NombreDispositivo>`",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return

    pin, dev_name = args[0], " ".join(args[1:])

    if pin != ADMIN_PIN:
        await update.message.reply_text(
            "❌ PIN incorrecto.",
            reply_markup=get_main_keyboard()
        )
        return

    devices = load_data()
    devices[user_id] = dev_name
    save_data(devices)

    await update.message.reply_text(
        f"✅ Dispositivo '{dev_name}' registrado correctamente.",
        reply_markup=get_main_keyboard()
    )


async def borrar_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Borrar mensaje del usuario por seguridad si llevaba PIN
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
            await update.message.reply_text(
                f"🗑️ Dispositivo '{removed}' ({target_id}) eliminado.",
                reply_markup=get_main_keyboard()
            )
        else:
            await update.message.reply_text("⚠️ ID no encontrado.", reply_markup=get_main_keyboard())
        return

    if user_id in devices:
        removed = devices.pop(user_id)
        save_data(devices)
        await update.message.reply_text(
            f"🗑️ Tu dispositivo '{removed}' ha sido eliminado.",
            reply_markup=get_main_keyboard()
        )
    else:
        await update.message.reply_text("⚠️ Este dispositivo no está registrado.", reply_markup=get_main_keyboard())


async def handle_refrescar_codigos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    devices = load_data()

    if user_id not in devices:
        await update.message.reply_text(
            "⛔ Necesitas estar registrado para solicitar códigos.\n"
            "Usa `/setid <PIN> <Nombre>` primero.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
        )
        return

    # TODO: Aquí puedes colocar tu código / llamada a API para refrescar o enviar los códigos
    await update.message.reply_text(
        f"🔄 Buscando códigos actualizados para *{devices[user_id]}*...",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )


async def handle_renovacion_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = str(user.id)
    devices = load_data()
    username_str = f"@{user.username}" if user.username else "Sin username"

    if user_id in devices:
        device_name = devices[user_id]
        await update.message.reply_text(
            f"✅ Solicitud enviada para la línea: *{device_name}*.",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard()
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


if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setid", set_id))
    app.add_handler(CommandHandler("borrarid", borrar_id))
    app.add_handler(MessageHandler(filters.Regex("^📲 Solicitar o renovar línea$"), handle_renovacion_request))
    app.add_handler(MessageHandler(filters.Regex("^🔄 Refrescar Códigos$"), handle_refrescar_codigos))
    app.add_handler(MessageHandler(filters.CONTACT, receive_contact))

    print("🤖 Bot listo...")
    app.run_polling()

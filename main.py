import json
import logging
import os
import requests
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ==============================================================================
# CONFIGURACIÓN (REEMPLAZA AQUÍ TUS DATOS)
# ==============================================================================
BOT_TOKEN = os.getenv(
    "BOT_TOKEN", "8861377510:AAEHZDnWElNKk43ee8zpIn5R0V1y4vpMhLU"
)  # Token que te dio BotFather
API_BEARER_TOKEN = os.getenv(
    "API_BEARER_TOKEN", "1670|tCrGynE1Af0SwECk5keF65dGMOBkko7sZCvn5blH60276d2a"
)
ADMIN_PIN = "1234"  # Tu PIN secreto de administrador para vincular/modificar
DB_FILE = "dispositivos.json"
# ==============================================================================

logging.basicConfig(level=logging.INFO)


def cargar_vinculaciones() -> dict:
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def guardar_vinculacion(chat_id: str, sub_id: str):
    datos = cargar_vinculaciones()
    datos[str(chat_id)] = str(sub_id)
    with open(DB_FILE, "w") as f:
        json.dump(datos, f, indent=4)


def eliminar_vinculacion(chat_id: str):
    datos = cargar_vinculaciones()
    if str(chat_id) in datos:
        del datos[str(chat_id)]
        with open(DB_FILE, "w") as f:
            json.dump(datos, f, indent=4)


def consultar_api(sub_id: str) -> str:
    url = f"https://megaott.net/api/v1/subscriptions/{sub_id}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {API_BEARER_TOKEN}",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)

        if response.status_code == 200:
            data = response.json()
            return (
                "=== DATOS DE LA SUSCRIPCIÓN ===\n\n"
                f"👤 *Usuario:* `{data.get('username', 'N/A')}`\n"
                f"🔑 *Contraseña:* `{data.get('password', 'N/A')}`\n"
                f"📅 *Expiración:* `{data.get('expiring_at', 'N/A')}`\n\n"
                f"🌐 *DNS Estándar:* `{data.get('dns_link', 'N/A')}`\n"
                f"📺 *DNS Samsung / LG:* `{data.get('dns_link_for_samsung_lg', 'N/A')}`"
            )
        else:
            return f"❌ Error al consultar la API (Código: {response.status_code})"

    except Exception as e:
        return f"⚠️ Error de conexión: {str(e)}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    vinculaciones = cargar_vinculaciones()

    if chat_id in vinculaciones:
        teclado = [["🔄 Refrescar Códigos"]]
        reply_markup = ReplyKeyboardMarkup(teclado, resize_keyboard=True)
        await update.message.reply_text(
            "👋 Bienvenido. Usa el botón inferior para consultar tus datos.",
            reply_markup=reply_markup,
        )
    else:
        await update.message.reply_text(
            "🔒 *Dispositivo no configurado*\n\nEl instalador debe ingresar el código de activación.",
            parse_mode="Markdown",
        )


async def vincular_o_modificar_id(
    update: Update, context: ContextTypes.DEFAULT_TYPE
):
    chat_id = str(update.effective_chat.id)

    if len(context.args) != 2:
        await update.message.reply_text(
            "⚠️ Formato incorrecto. Uso: `/setid PIN ID`", parse_mode="Markdown"
        )
        return

    pin_ingresado, sub_id_ingresado = context.args[0], context.args[1]

    if pin_ingresado != ADMIN_PIN:
        await update.message.reply_text("❌ PIN de administrador incorrecto.")
        return

    guardar_vinculacion(chat_id, sub_id_ingresado)
    teclado = [["🔄 Refrescar Códigos"]]
    reply_markup = ReplyKeyboardMarkup(teclado, resize_keyboard=True)

    await update.message.reply_text(
        f"✅ *ID de suscripción guardado:* `{sub_id_ingresado}`",
        parse_mode="Markdown",
        reply_markup=reply_markup,
    )


async def desvincular_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)

    if len(context.args) != 1 or context.args[0] != ADMIN_PIN:
        await update.message.reply_text("❌ Sintaxis o PIN incorrecto.")
        return

    eliminar_vinculacion(chat_id)
    await update.message.reply_text("🗑️ Dispositivo desvinculado con éxito.")


async def refrescar_datos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    vinculaciones = cargar_vinculaciones()

    if chat_id not in vinculaciones:
        await update.message.reply_text(
            "🛑 Este dispositivo no está autorizado."
        )
        return

    sub_id = vinculaciones[chat_id]
    await update.message.reply_text("⏳ Consultando servidor...")
    resultado = consultar_api(sub_id)
    await update.message.reply_text(resultado, parse_mode="Markdown")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setid", vincular_o_modificar_id))
    app.add_handler(CommandHandler("borrarid", desvincular_id))
    app.add_handler(
        MessageHandler(
            filters.Regex("^🔄 Refrescar Códigos$"), refrescar_datos
        )
    )

    print("🤖 Bot listo...")
    app.run_polling()


if __name__ == "__main__":
    main()

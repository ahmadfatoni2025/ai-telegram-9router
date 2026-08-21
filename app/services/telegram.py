import os

from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from app.services.fusion import ask_fusion
from app.services.agent import ask_ai


load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)

# Kata kunci yang menandakan perintah aksi file / download
FILE_ACTION_KEYWORDS = [
    "download",
    "unduh",
    "simpan",
    "buat file",
    "tulis file",
    "hapus file",
    "edit file",
    "baca file",
    "list file",
    "daftar file",
    "lihat file",
    "mkdir",
    "write_file",
    "read_file",
    "delete_file",
    "list_files",
    "download_file",
]


def is_file_action(message: str) -> bool:
    """
    Cek apakah pesan berisi perintah yang
    memerlukan akses file atau download.
    """
    lower = message.lower()
    return any(kw in lower for kw in FILE_ACTION_KEYWORDS)


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "Tony AI aktif.\n\n"
        "Saya dapat menjawab pertanyaan, "
        "mengelola file, dan mengunduh file dari internet."
    )


async def chat_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_message = update.message.text

    try:

        await update.message.chat.send_action(
            action="typing"
        )

        # Route: jika perintah file/download, gunakan AI Agent (dengan tools)
        # Jika pertanyaan biasa, gunakan Fusion AI
        if is_file_action(user_message):
            answer = ask_ai(user_message)
        else:
            try:
                answer = ask_fusion(user_message)
            except Exception:
                # Fallback ke ask_ai jika fusion gagal
                answer = ask_ai(user_message)

        await update.message.reply_text(answer)

    except Exception as error:

        import traceback
        traceback.print_exc()

        error_text = f"{type(error).__name__}: {error}"

        # Batasi panjang pesan Telegram
        if len(error_text) > 3500:
            error_text = error_text[:3500]

        await update.message.reply_text(
            "❌ AI error:\n\n" + error_text
        )


def create_bot():

    application = (
        Application
        .builder()
        .token(TELEGRAM_BOT_TOKEN)
        .build()
    )

    application.add_handler(
        CommandHandler(
            "start",
            start_command
        )
    )

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            chat_message
        )
    )

    return application
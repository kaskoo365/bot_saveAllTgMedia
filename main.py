import os
import logging
from pathlib import Path
from dotenv import load_dotenv

from telegram import Update, Message
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    BusinessConnectionHandler,
    ContextTypes,
    filters,
)
from telegram.constants import MessageEntityType

from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN не найден! Проверь файл .env")

SAVE_DIR = Path("saved_media")
SAVE_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот для сохранения одноразовых фото и видео.\n\n"
        "Как пользоваться:\n"
        "1. Подключи меня в настройках Telegram → Профиль → Изменить → Автоматизация чатов\n"
        "2. Когда придёт одноразовое фото/видео — просто ответь на него любым сообщением или поставь реакцию\n"
        "3. Я сразу сохраню копию и пришлю тебе."
    )


async def business_connection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Когда бота подключают/отключают через Автоматизацию чатов"""
    conn = update.business_connection
    if conn.is_enabled:
        logger.info(f"Бот подключён к бизнесу/аккаунту: {conn.user.id}")
    else:
        logger.info(f"Бот отключён от {conn.user.id}")


async def save_media(message: Message, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Скачивает медиа из сообщения и сохраняет на диск + отправляет пользователю"""
    file = None
    file_name = None
    caption = message.caption or ""

    if message.photo:
        file = await message.photo[-1].get_file()
        file_name = f"photo_{message.message_id}.jpg"
    elif message.video:
        file = await message.video.get_file()
        file_name = f"video_{message.message_id}.mp4"
    elif message.video_note:
        file = await message.video_note.get_file()
        file_name = f"videonote_{message.message_id}.mp4"
    elif message.document and message.document.mime_type and message.document.mime_type.startswith(("image/", "video/")):
        file = await message.document.get_file()
        file_name = message.document.file_name or f"doc_{message.message_id}"

    if not file:
        return False

    # Скачиваем
    local_path = SAVE_DIR / file_name
    await file.download_to_drive(local_path)

    try:
        if message.photo:
            await context.bot.send_photo(
                chat_id=message.from_user.id if message.from_user else context._user_id,
                photo=local_path,
                caption=f"Сохранено фото\n{caption}"
            )
        elif message.video or message.video_note:
            await context.bot.send_video(
                chat_id=message.from_user.id if message.from_user else context._user_id,
                video=local_path,
                caption=f"Сохранено видео\n{caption}"
            )
        else:
            await context.bot.send_document(
                chat_id=message.from_user.id if message.from_user else context._user_id,
                document=local_path,
                caption=f"Сохранено\n{caption}"
            )
    except Exception as e:
        logger.error(f"Не удалось отправить сохранённое медиа: {e}")

    return True


async def handle_business_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений, которые приходят через Business Connection"""
    message = update.business_message or update.message
    if not message:
        return

    if message.reply_to_message:
        replied = message.reply_to_message
        if any([replied.photo, replied.video, replied.video_note, replied.document]):
            success = await save_media(replied, context)
            if success:
                await message.reply_text("✅ Сохранил!")
            return

    if message.has_protected_content or getattr(message, "is_view_once", False):
        await save_media(message, context)


async def handle_reaction(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Когда ставят реакцию на сообщение — тоже сохраняем"""
    pass


def main():
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(BusinessConnectionHandler(business_connection))
    app.add_handler(MessageHandler(filters.ALL, handle_business_message))

    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
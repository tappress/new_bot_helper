import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import router as main_router
from bot.voice_handlers import voice_router
from settings import settings

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Створення об'єктів бота і диспетчера
bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())


# Перевірка наявності необхідних папок і моделей
async def check_requirements():
    # Перевірка наявності папки для моделей Vosk
    vosk_models_dir = "vosk-model-uk-v3"
    small_model_dir = "vosk-model-small-uk-v3"
    en_model_dir = "vosk-model-small-en-us-0.15"

    if not os.path.exists(vosk_models_dir) and not os.path.exists(small_model_dir) and not os.path.exists(en_model_dir):
        logger.warning(
            "Моделі Vosk не знайдені. Для повноцінної роботи розпізнавання мовлення необхідно завантажити "
            "одну з моделей (vosk-model-uk-v3, vosk-model-small-uk-v3 або vosk-model-small-en-us-0.15)"
        )
        logger.info(
            "Ви можете завантажити моделі з сайту: https://alphacephei.com/vosk/models"
        )
    else:
        if os.path.exists(vosk_models_dir):
            logger.info(f"Знайдено українську модель Vosk: {vosk_models_dir}")
        elif os.path.exists(small_model_dir):
            logger.info(f"Знайдено малу українську модель Vosk: {small_model_dir}")
        elif os.path.exists(en_model_dir):
            logger.info(f"Знайдено англійську модель Vosk: {en_model_dir}")

    # Перевірка наявності необхідних бібліотек
    try:
        import vosk
        logger.info("Бібліотека Vosk встановлена")
    except ImportError:
        logger.warning("Бібліотека Vosk не встановлена. Розпізнавання мовлення буде недоступним.")
        logger.info("Для встановлення використайте: pip install vosk")

    try:
        from gtts import gTTS
        logger.info("Бібліотека gTTS встановлена")
    except ImportError:
        logger.warning("Бібліотека gTTS не встановлена. Синтез мовлення буде недоступним.")
        logger.info("Для встановлення використайте: pip install gtts")

    try:
        from pydub import AudioSegment
        logger.info("Бібліотека pydub встановлена")
    except ImportError:
        logger.warning("Бібліотека pydub не встановлена. Обробка аудіо буде недоступною.")
        logger.info("Для встановлення використайте: pip install pydub")
        logger.info("Також необхідно встановити ffmpeg: apt-get install ffmpeg (для Linux)")


# Реєстрація роутера і запуск бота
dp.include_router(main_router)
dp.include_router(voice_router)

async def main():
    # Перевірка наявності необхідних компонентів
    await check_requirements()

    # Інформація про запуск
    logger.info("Запуск бота з підтримкою голосових команд...")
    logger.info("Доступні функції:")
    logger.info("- Обробка текстових повідомлень з використанням NLP")
    logger.info("- Розпізнавання мовлення з голосових повідомлень (Vosk)")
    logger.info("- Синтез голосових відповідей (gTTS)")

    # Запуск бота
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
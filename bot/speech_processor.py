"""
Модуль для обробки голосу (STT та TTS)
"""
import asyncio
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Union

from aiogram import Bot
from aiogram.types import BufferedInputFile, Message, Voice
from gtts import gTTS
from pydub import AudioSegment
from vosk import Model, KaldiRecognizer

from settings import settings

logger = logging.getLogger(__name__)

# Шлях до моделі Vosk
MODEL_PATH = "vosk-model-uk-v3"  # Українська модель


class SpeechProcessor:
    """Клас для обробки голосу з методами розпізнавання та синтезу мовлення"""

    def __init__(self):
        """Ініціалізація процесора мовлення"""
        self._model = None
        self._recognizer = None
        self._init_model()
        logger.info("Ініціалізовано процесор мовлення")

    def _init_model(self):
        """Ініціалізація моделі Vosk"""
        try:
            # Перевірка наявності моделі
            if not os.path.exists(MODEL_PATH):
                logger.warning(f"Модель {MODEL_PATH} не знайдена. Використовуємо малу модель.")
                # Якщо основної моделі немає, спробуємо використати маленьку
                small_model_path = "vosk-model-small-uk-v3"

                # Якщо і малої моделі немає, завантажимо англійську
                if not os.path.exists(small_model_path):
                    logger.warning("Мала українська модель не знайдена. Використовуємо англійську.")
                    small_model_path = "vosk-model-small-en-us-0.15"

                    # Якщо і англійської немає, логуємо помилку
                    if not os.path.exists(small_model_path):
                        logger.error("Жодна модель не знайдена. STT буде недоступним.")
                        return

                self._model = Model(small_model_path)
            else:
                # Використовуємо основну українську модель
                self._model = Model(MODEL_PATH)

            # Створюємо розпізнавач з моделлю
            self._recognizer = KaldiRecognizer(self._model, 16000)
            logger.info(f"Успішно ініціалізовано розпізнавач Vosk")

        except Exception as e:
            logger.error(f"Помилка ініціалізації моделі Vosk: {e}")
            self._model = None
            self._recognizer = None

    async def recognize_speech(self, voice_message: Union[Voice, Message]) -> Optional[str]:
        """
        Розпізнавання мовлення з голосового повідомлення
        :param voice_message: Голосове повідомлення або об'єкт Voice
        :return: Розпізнаний текст або None у разі помилки
        """
        if self._recognizer is None:
            logger.error("Розпізнавач не ініціалізований. Неможливо розпізнати мовлення.")
            return None

        temp_voice_path = None
        wav_path = None
        bot = None

        try:
            # Отримання об'єкта Voice з повідомлення, якщо передано Message
            voice = voice_message if isinstance(voice_message, Voice) else voice_message.voice

            if not voice:
                logger.warning("Голосове повідомлення не містить аудіо")
                return None

            # Завантажуємо голосовий файл
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

            # Використовуємо конкретні імена файлів для кращого відстеження помилок
            temp_voice_path = tempfile.mktemp(suffix=".ogg")
            wav_path = tempfile.mktemp(suffix=".wav")

            # Завантажуємо голосовий файл
            logger.info(f"Завантаження голосового повідомлення file_id={voice.file_id}")
            voice_file = await bot.get_file(voice.file_id)
            voice_path = voice_file.file_path

            # Завантажуємо файл
            logger.info(f"Завантаження файлу з шляху {voice_path} до {temp_voice_path}")
            voice_data = await bot.download_file(voice_path)

            with open(temp_voice_path, "wb") as temp_voice:
                temp_voice.write(voice_data.read())

            logger.info(f"Голосове повідомлення збережено до {temp_voice_path}")

            # Перевіряємо розмір завантаженого файлу
            ogg_size = os.path.getsize(temp_voice_path)
            logger.info(f"Розмір OGG файлу: {ogg_size} байт")

            if ogg_size == 0:
                logger.error("Завантажений файл має нульовий розмір")
                return None

            # Використовуємо pydub для конвертації
            logger.info(f"Конвертація OGG в WAV: {temp_voice_path} -> {wav_path}")

            # Встановлюємо детальніші логи для pydub
            pydub_logger = logging.getLogger('pydub.converter')
            pydub_logger.setLevel(logging.DEBUG)
            pydub_logger.addHandler(logging.StreamHandler())

            # Конвертуємо OGG в WAV з явними налаштуваннями
            audio = AudioSegment.from_file(temp_voice_path, format="ogg")

            # Виводимо інформацію про аудіофайл
            logger.info(f"Аудіофайл: тривалість={len(audio)}мс, канали={audio.channels}, частота={audio.frame_rate}Гц")

            # Конвертуємо в 16kHz mono для Vosk
            audio = audio.set_frame_rate(16000).set_channels(1)
            audio.export(wav_path, format="wav")

            # Перевіряємо розмір WAV файлу
            wav_size = os.path.getsize(wav_path)
            logger.info(f"Розмір WAV файлу: {wav_size} байт")

            if wav_size == 0:
                logger.error("Конвертований WAV файл має нульовий розмір")
                return None

            # Зчитуємо WAV файл для розпізнавання
            with open(wav_path, "rb") as wav_file:
                wav_data = wav_file.read()

            # Перевіряємо розмір даних WAV
            logger.info(f"Розмір даних WAV: {len(wav_data)} байт")

            # Скидаємо стан розпізнавача для нового файлу
            self._recognizer.Reset()

            # Розбиваємо аудіо на частини для поступової обробки
            CHUNK_SIZE = 4000  # Розмір частини в байтах
            results = []

            for i in range(0, len(wav_data), CHUNK_SIZE):
                chunk = wav_data[i:i+CHUNK_SIZE]
                if len(chunk) == 0:
                    continue

                if self._recognizer.AcceptWaveform(chunk):
                    part_result = json.loads(self._recognizer.Result())
                    if "text" in part_result and part_result["text"].strip():
                        results.append(part_result["text"])

            # Отримуємо фінальний результат після обробки всіх частин
            final_result = json.loads(self._recognizer.FinalResult())
            if "text" in final_result and final_result["text"].strip():
                results.append(final_result["text"])

            # Об'єднуємо всі результати
            recognized_text = " ".join(results).strip()

            if not recognized_text and len(wav_data) > 0:
                # Пробуємо альтернативний підхід - відправляємо все аудіо одразу
                logger.info("Спроба альтернативного підходу розпізнавання")
                self._recognizer.Reset()
                self._recognizer.AcceptWaveform(wav_data)
                final_result = json.loads(self._recognizer.FinalResult())
                recognized_text = final_result.get("text", "").strip()

            if not recognized_text:
                logger.warning("Не вдалося розпізнати текст з голосового повідомлення")
                return None

            logger.info(f"Успішно розпізнано текст: {recognized_text}")
            return recognized_text

        except Exception as e:
            logger.error(f"Помилка при розпізнаванні мовлення: {str(e)}", exc_info=True)
            return None
        finally:
            # Видаляємо тимчасові файли
            for path in [temp_voice_path, wav_path]:
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                        logger.info(f"Видалено тимчасовий файл: {path}")
                    except Exception as e:
                        logger.warning(f"Не вдалося видалити тимчасовий файл {path}: {e}")

            # Закриваємо бота
            if bot:
                session = getattr(bot, "session", None)
                if session and hasattr(session, "close"):
                    await session.close()
                    logger.info("Закрито сесію бота")

    async def synthesize_speech(self, text: str, lang: str = "uk") -> Optional[Path]:
        """
        Синтез мовлення з тексту
        :param text: Текст для синтезу
        :param lang: Мова (за замовчуванням українська)
        :return: Шлях до аудіофайлу або None у разі помилки
        """
        try:
            # Створюємо тимчасовий файл для аудіо з конкретним ім'ям
            audio_path = Path(tempfile.mktemp(suffix=".mp3"))

            # Використовуємо gTTS для синтезу мовлення
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(str(audio_path))

            # Перевіряємо, що файл був створений і має розмір
            if not audio_path.exists() or audio_path.stat().st_size == 0:
                logger.error(f"Не вдалося створити аудіофайл або файл порожній: {audio_path}")
                return None

            logger.info(f"Успішно синтезовано мовлення та збережено у {audio_path}")
            return audio_path

        except Exception as e:
            logger.error(f"Помилка при синтезі мовлення: {e}", exc_info=True)
            return None

    async def send_voice_reply(self, message: Message, text: str, lang: str = "uk") -> bool:
        """
        Відправка голосової відповіді
        :param message: Повідомлення, на яке відповідаємо
        :param text: Текст для синтезу
        :param lang: Мова синтезу
        :return: True, якщо відправлено успішно, False інакше
        """
        audio_path = None
        try:
            # Синтезуємо мовлення
            audio_path = await self.synthesize_speech(text, lang)
            if not audio_path:
                logger.error("Не вдалося синтезувати мовлення")
                return False

            # Перевіряємо, що аудіофайл існує і має розмір
            if not os.path.exists(audio_path):
                logger.error(f"Аудіофайл не знайдено: {audio_path}")
                return False

            audio_size = os.path.getsize(audio_path)
            logger.info(f"Розмір аудіофайлу: {audio_size} байт")

            if audio_size == 0:
                logger.error("Аудіофайл має нульовий розмір")
                return False

            # Читаємо аудіофайл
            with open(audio_path, "rb") as audio_file:
                audio_data = audio_file.read()

            # Відправляємо голосове повідомлення
            audio = BufferedInputFile(audio_data, filename="voice_reply.mp3")

            # Визначаємо, чи додавати підпис
            caption = None
            if len(text) <= 1024:
                caption = text

            await message.answer_voice(audio, caption=caption)
            logger.info("Успішно відправлено голосову відповідь")
            return True

        except Exception as e:
            logger.error(f"Помилка при відправці голосової відповіді: {e}", exc_info=True)
            return False
        finally:
            # Видаляємо тимчасовий файл
            if audio_path and os.path.exists(audio_path):
                try:
                    os.unlink(audio_path)
                    logger.info(f"Видалено тимчасовий аудіофайл: {audio_path}")
                except Exception as e:
                    logger.warning(f"Не вдалося видалити тимчасовий файл {audio_path}: {e}")


# Створення глобального екземпляра процесора мовлення
speech_processor = SpeechProcessor()
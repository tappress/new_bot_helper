"""
Модуль для обробки голосу (STT та TTS)
"""
import asyncio
import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Union

import httpx
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

        try:
            # Отримання об'єкта Voice з повідомлення, якщо передано Message
            voice = voice_message if isinstance(voice_message, Voice) else voice_message.voice

            if not voice:
                logger.warning("Голосове повідомлення не містить аудіо")
                return None

            # Завантажуємо голосовий файл
            bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            voice_file = await bot.get_file(voice.file_id)
            voice_path = voice_file.file_path

            # Створюємо тимчасовий файл для збереження голосового повідомлення
            with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as temp_voice:
                voice_data = await bot.download_file(voice_path)
                temp_voice.write(voice_data.read())
                temp_voice_path = temp_voice.name

            # Конвертуємо голосове повідомлення у формат WAV
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                wav_path = temp_wav.name

            # Використовуємо pydub для конвертації
            audio = AudioSegment.from_ogg(temp_voice_path)
            # Конвертуємо в 16kHz mono для Vosk
            audio = audio.set_frame_rate(16000).set_channels(1)
            audio.export(wav_path, format="wav")

            # Зчитуємо WAV файл для розпізнавання
            with open(wav_path, "rb") as wav_file:
                wav_data = wav_file.read()

            # Скидаємо стан розпізнавача для нового файлу
            self._recognizer.Reset()

            # Відправляємо аудіо на розпізнавання
            self._recognizer.AcceptWaveform(wav_data)
            result = self._recognizer.FinalResult()

            # Видаляємо тимчасові файли
            for path in [temp_voice_path, wav_path]:
                try:
                    os.unlink(path)
                except Exception as e:
                    logger.warning(f"Не вдалося видалити тимчасовий файл {path}: {e}")

            # Парсимо результат
            import json
            result_json = json.loads(result)
            recognized_text = result_json.get("text", "").strip()

            if not recognized_text:
                logger.warning("Не вдалося розпізнати текст з голосового повідомлення")
                return None

            logger.info(f"Успішно розпізнано текст: {recognized_text}")
            return recognized_text

        except Exception as e:
            logger.error(f"Помилка при розпізнаванні мовлення: {e}")
            return None

    async def synthesize_speech(self, text: str, lang: str = "uk") -> Optional[Path]:
        """
        Синтез мовлення з тексту
        :param text: Текст для синтезу
        :param lang: Мова (за замовчуванням українська)
        :return: Шлях до аудіофайлу або None у разі помилки
        """
        try:
            # Створюємо тимчасовий файл для аудіо
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_audio:
                audio_path = Path(temp_audio.name)

            # Використовуємо gTTS для синтезу мовлення
            tts = gTTS(text=text, lang=lang, slow=False)
            tts.save(str(audio_path))

            logger.info(f"Успішно синтезовано мовлення та збережено у {audio_path}")
            return audio_path

        except Exception as e:
            logger.error(f"Помилка при синтезі мовлення: {e}")
            return None

    async def send_voice_reply(self, message: Message, text: str, lang: str = "uk") -> bool:
        """
        Відправка голосової відповіді
        :param message: Повідомлення, на яке відповідаємо
        :param text: Текст для синтезу
        :param lang: Мова синтезу
        :return: True, якщо відправлено успішно, False інакше
        """
        try:
            # Синтезуємо мовлення
            audio_path = await self.synthesize_speech(text, lang)
            if not audio_path:
                logger.error("Не вдалося синтезувати мовлення")
                return False

            # Читаємо аудіофайл
            with open(audio_path, "rb") as audio_file:
                audio_data = audio_file.read()

            # Відправляємо голосове повідомлення
            audio = BufferedInputFile(audio_data, filename="voice_reply.mp3")
            await message.answer_voice(audio, caption=text[:1024] if len(text) <= 1024 else None)

            # Видаляємо тимчасовий файл
            try:
                os.unlink(audio_path)
            except Exception as e:
                logger.warning(f"Не вдалося видалити тимчасовий файл {audio_path}: {e}")

            logger.info("Успішно відправлено голосову відповідь")
            return True

        except Exception as e:
            logger.error(f"Помилка при відправці голосової відповіді: {e}")
            return False


# Створення глобального екземпляра процесора мовлення
speech_processor = SpeechProcessor()
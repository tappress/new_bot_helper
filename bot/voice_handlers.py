"""
Обробники голосових повідомлень для бота
"""
import logging
from typing import Optional, Dict, Any, Union

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.nlp_processor import process_nlp_request
from bot.speech_processor import speech_processor
from bot.utils import (
    process_weather_request,
    process_currency_request,
    process_news_request,
    has_weather_keywords,
    extract_city_from_text,
    has_currency_keywords,
    extract_currency_from_text,
    has_news_keywords,
)

logger = logging.getLogger(__name__)

# Створюємо роутер для голосових повідомлень
voice_router = Router()


@voice_router.message(F.voice)
async def handle_voice_message(message: Message, state: FSMContext):
    """
    Обробка голосових повідомлень
    :param message: Повідомлення з голосовим вкладенням
    :param state: FSM контекст
    """
    # Надсилаємо статус "друкує" під час обробки
    await message.bot.send_chat_action(message.chat.id, "typing")

    # Повідомлення про початок обробки
    processing_message = await message.answer("🎤 Розпізнаю голосове повідомлення...")

    try:
        # Розпізнаємо мовлення
        recognized_text = await speech_processor.recognize_speech(message)

        if not recognized_text:
            await message.answer(
                "⚠️ Не вдалося розпізнати мовлення. Будь ласка, спробуйте ще раз або надішліть текстове повідомлення."
            )
            return

        # Логуємо розпізнаний текст і повідомляємо користувача
        logger.info(f"Розпізнано текст з голосового повідомлення: {recognized_text}")
        await message.answer(f"🎯 Розпізнано: \"{recognized_text}\"")

        # Видаляємо повідомлення про обробку
        await processing_message.delete()

        # Обробляємо розпізнаний текст так само, як і текстові повідомлення
        # Спочатку спробуємо через NLP
        nlp_processed = await process_nlp_request(message, state, recognized_text)

        # Якщо NLP не зміг обробити, використовуємо простіший метод ключових слів
        if not nlp_processed:
            logger.info("NLP не зміг обробити голосовий запит, використовуємо метод ключових слів")

            # Визначаємо тип запиту за ключовими словами
            if has_weather_keywords(recognized_text):
                city = extract_city_from_text(recognized_text)
                response_text = await process_weather_request(message, city, state, return_text=True)
                if response_text:
                    await speech_processor.send_voice_reply(message, response_text)

            elif has_currency_keywords(recognized_text):
                base, target = extract_currency_from_text(recognized_text)
                response_text = await process_currency_request(message, base, target, state, return_text=True)
                if response_text:
                    await speech_processor.send_voice_reply(message, response_text)

            elif has_news_keywords(recognized_text):
                response_text = await process_news_request(message, state=state, return_text=True)
                if response_text:
                    await speech_processor.send_voice_reply(message, response_text)

            else:
                response_text = (
                    "Не вдалося розпізнати ваш запит. Спробуйте використати команди:\n"
                    "/weather - Погода\n"
                    "/currency - Курс валют\n"
                    "/news - Новини"
                )
                await message.answer(response_text)

    except Exception as e:
        logger.error(f"Помилка при обробці голосового повідомлення: {e}")
        await message.answer("⚠️ Сталася помилка при обробці голосового повідомлення.")

        # Видаляємо повідомлення про обробку, якщо воно ще існує
        try:
            await processing_message.delete()
        except Exception:
            pass
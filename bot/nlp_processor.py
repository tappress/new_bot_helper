import logging
import re
from typing import Optional, Dict, Any
from typing import Tuple

import spacy
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from spacy.matcher import Matcher
from spacy.tokens import Doc

from bot.utils import process_weather_request, process_currency_request, process_news_request

logger = logging.getLogger(__name__)


class NLPProcessor:
    """Клас для обробки запитів природною мовою"""

    def __init__(self, model="uk_core_news_sm"):
        """
        Ініціалізація процесора NLP
        :param model: Назва моделі spaCy для завантаження
        """
        logger.info(f"Ініціалізація NLP процесора з моделлю {model}")

        try:
            self.nlp = spacy.load(model)
            logger.info("Модель spaCy успішно завантажена")
        except OSError:
            logger.warning(f"Модель {model} не знайдена. Спроба завантаження...")
            try:
                # Спроба встановити модель, якщо вона не встановлена
                import subprocess
                subprocess.check_call(["python", "-m", "spacy", "download", model])
                self.nlp = spacy.load(model)
                logger.info(f"Модель {model} завантажена успішно")
            except Exception as e:
                logger.error(f"Помилка завантаження моделі {model}: {e}")
                # У разі помилки використовуємо маленьку англійську модель
                logger.info("Використання базової англійської моделі en_core_web_sm")
                try:
                    self.nlp = spacy.load("en_core_web_sm")
                except OSError:
                    subprocess.check_call(["python", "-m", "spacy", "download", "en_core_web_sm"])
                    self.nlp = spacy.load("en_core_web_sm")

        # Створюємо Matcher для визначення намірів
        self.matcher = Matcher(self.nlp.vocab)

        # Налаштування шаблонів для розпізнавання намірів
        self._setup_intent_patterns()

        # Регулярні вирази для додаткової обробки запитів
        self.currency_regex = re.compile(r'(USD|EUR|UAH|EUR|долар|євро|гривня|долара|євро|гривні)', re.IGNORECASE)

        logger.info("NLP процесор готовий до роботи")

    def _setup_intent_patterns(self):
        """Налаштування шаблонів для розпізнавання намірів"""

        # Шаблони для погоди
        weather_patterns = [
            # Шаблон 1: "погода в [МІСТО]"
            [{"LEMMA": {"IN": ["погода", "температура", "клімат"]}},
             {"LOWER": "в"},
             {"POS": "PROPN"}],

            # Шаблон 2: "яка погода в [МІСТО]"
            [{"LEMMA": {"IN": ["який", "яка"]}},
             {"LEMMA": {"IN": ["погода", "температура"]}},
             {"LOWER": "в"},
             {"POS": "PROPN"}],

            # Шаблон 3: "[МІСТО] погода"
            [{"POS": "PROPN"},
             {"LEMMA": {"IN": ["погода", "температура"]}}],

            # Шаблон 4: "прогноз погоди"
            [{"LEMMA": "прогноз"},
             {"LEMMA": "погода"}]
        ]

        # Шаблони для валют
        currency_patterns = [
            # Шаблон 1: "курс [ВАЛЮТА]"
            [{"LEMMA": {"IN": ["курс", "ціна", "вартість"]}},
             {"POS": "NOUN"}],

            # Шаблон 2: "обмін валют"
            [{"LEMMA": {"IN": ["обмін", "конвертація"]}},
             {"LEMMA": {"IN": ["валюта", "долар", "євро", "гривня"]}}],

            # Шаблон 3: "долар до гривні"
            [{"LEMMA": {"IN": ["долар", "євро", "валюта"]}},
             {"LOWER": {"IN": ["до", "в", "у"]}},
             {"LEMMA": {"IN": ["гривня", "долар", "євро"]}}],

            # Шаблон 4: "долар сьогодні"
            [{"LEMMA": {"IN": ["долар", "євро", "гривня"]}},
             {"LEMMA": {"IN": ["сьогодні", "зараз", "наразі"]}}]
        ]

        # Шаблони для новин
        news_patterns = [
            # Шаблон 1: "останні новини"
            [{"LEMMA": {"IN": ["останній", "свіжий", "актуальний"]}},
             {"LEMMA": {"IN": ["новина", "новини", "події"]}}],

            # Шаблон 2: "новини [КАТЕГОРІЯ]"
            [{"LEMMA": {"IN": ["новина", "подія", "інформація"]}},
             {"POS": "ADJ"}],

            # Шаблон 3: "що відбувається"
            [{"LEMMA": "що"}, {"LEMMA": {"IN": ["відбуватися", "трапитися", "коїтися"]}}],

            # Шаблон 4: "розкажи про новини"
            [{"LEMMA": {"IN": ["розказати", "розповісти", "повідомити"]}},
             {"LOWER": {"IN": ["про", "щодо"]}},
             {"LEMMA": {"IN": ["новина", "подія", "світ", "країна"]}}]
        ]

        # Додаємо шаблони до загального визначника
        self.matcher.add("WEATHER_INTENT", weather_patterns)
        self.matcher.add("CURRENCY_INTENT", currency_patterns)
        self.matcher.add("NEWS_INTENT", news_patterns)

        logger.info("Шаблони для розпізнавання намірів налаштовані")

    def process_text(self, text: str) -> Dict[str, Any]:
        """
        Обробка тексту та визначення наміру користувача
        :param text: Текст для аналізу
        :return: Словник з даними про намір та витягнуті сутності
        """
        logger.info(f"Обробка тексту: '{text}'")

        # Створюємо документ spaCy
        doc = self.nlp(text)

        # Визначаємо намір
        intent_data = self._detect_intent(doc)
        intent_type = intent_data["intent"]

        # Залежно від наміру, витягуємо додаткові сутності
        if intent_type == "weather":
            city = self._extract_city(doc)
            intent_data["entities"]["city"] = city
            logger.info(f"Виявлено намір погоди для міста: {city}")

        elif intent_type == "currency":
            base, target = self._extract_currency_pair(doc, text)
            intent_data["entities"]["base"] = base
            intent_data["entities"]["target"] = target
            logger.info(f"Виявлено намір валюти: {base} -> {target}")

        elif intent_type == "news":
            category, query = self._extract_news_details(doc)
            intent_data["entities"]["category"] = category
            intent_data["entities"]["query"] = query
            logger.info(f"Виявлено намір новин. Категорія: {category}, Запит: {query}")

        logger.info(f"Результат обробки: {intent_data}")
        return intent_data

    def _detect_intent(self, doc: Doc) -> Dict[str, Any]:
        """
        Визначення наміру користувача з документа
        :param doc: Документ spaCy
        :return: Дані про намір
        """
        # Застосовуємо матчер до документа
        matches = self.matcher(doc)

        # Зберігаємо кількість кожного типу наміру
        intent_counts = {}

        # Результат за замовчуванням
        result = {
            "intent": "unknown",
            "confidence": 0.0,
            "entities": {}
        }

        # Якщо є збіги, рахуємо кількість кожного наміру
        if matches:
            for match_id, start, end in matches:
                intent_name = self.nlp.vocab.strings[match_id].split("_")[0].lower()
                intent_counts[intent_name] = intent_counts.get(intent_name, 0) + 1

            # Визначаємо намір з найбільшою кількістю збігів
            if intent_counts:
                top_intent = max(intent_counts, key=intent_counts.get)
                confidence = min(0.5 + 0.1 * intent_counts[top_intent], 0.95)  # Максимум 0.95

                result["intent"] = top_intent.lower()
                result["confidence"] = confidence

        # Якщо не вдалося визначити намір за шаблонами,
        # використовуємо простий пошук за ключовими словами
        if result["intent"] == "unknown":
            text_lower = doc.text.lower()

            # Ключові слова для різних намірів
            weather_keywords = ["погода", "температура", "градус", "тепло", "холодно", "дощ"]
            currency_keywords = ["курс", "валюта", "долар", "євро", "гривня", "usd", "eur", "uah"]
            news_keywords = ["новини", "новина", "події", "що відбувається", "статті"]

            # Перевіряємо наявність ключових слів
            for word in weather_keywords:
                if word in text_lower:
                    result["intent"] = "weather"
                    result["confidence"] = 0.6
                    break

            if result["intent"] == "unknown":
                for word in currency_keywords:
                    if word in text_lower:
                        result["intent"] = "currency"
                        result["confidence"] = 0.6
                        break

            if result["intent"] == "unknown":
                for word in news_keywords:
                    if word in text_lower:
                        result["intent"] = "news"
                        result["confidence"] = 0.6
                        break

        return result

    def _extract_city(self, doc: Doc) -> str:
        """
        Витягування назви міста з документа
        :param doc: Документ spaCy
        :return: Назва міста або "Київ" за замовчуванням
        """
        # Словник відмінків українських міст
        city_cases = {
            "києві": "Київ",
            "львові": "Львів",
            "одесі": "Одеса",
            "харкові": "Харків",
            "дніпрі": "Дніпро",
            "житомирі": "Житомир",
            "вінниці": "Вінниця",
            "полтаві": "Полтава",
            "чернігові": "Чернігів",
            "херсоні": "Херсон",
            "запоріжжі": "Запоріжжя"
        }

        # Перевіряємо, чи є в тексті міста у відмінках
        text_lower = doc.text.lower()
        for city_case, city_name in city_cases.items():
            if city_case in text_lower:
                return city_name

        # Шукаємо геополітичні сутності (міста, країни)
        for ent in doc.ents:
            if ent.label_ in ["GPE", "LOC"]:  # Геополітична або Локація
                # Перевіряємо, чи це не відмінок міста
                if ent.text.lower() in city_cases:
                    return city_cases[ent.text.lower()]
                return ent.text.strip()

        # Якщо не знайдено, шукаємо власні назви після "в" або "у"
        for i, token in enumerate(doc):
            if token.text.lower() in ["в", "у"] and i < len(doc) - 1:
                if doc[i + 1].pos_ == "PROPN":
                    city_form = doc[i + 1].text.lower()
                    # Перевіряємо, чи це не відмінок міста
                    if city_form in city_cases:
                        return city_cases[city_form]
                    return doc[i + 1].text.strip()

        # Якщо і так не знайдено, шукаємо будь-які власні назви
        for token in doc:
            if token.pos_ == "PROPN":
                city_form = token.text.lower()
                if city_form in city_cases:
                    return city_cases[city_form]
                return token.text.strip()

        # За замовчуванням повертаємо "Київ"
        return "Київ"

    def _extract_currency_pair(self, doc: Doc, text: str) -> Tuple[str, str]:
        """
        Витягування валютної пари з документа
        :param doc: Документ spaCy
        :param text: Оригінальний текст для додаткової перевірки
        :return: Кортеж (базова валюта, цільова валюта)
        """
        # Словник для заміни українських назв на коди валют
        currency_map = {
            "долар": "USD",
            "доларах": "USD",
            "доларів": "USD",
            "долара": "USD",
            "євро": "EUR",
            "гривня": "UAH",
            "гривні": "UAH",
            "гривень": "UAH",
            "гривнях": "UAH",
            "usd": "USD",
            "eur": "EUR",
            "uah": "UAH"
        }

        # Знаходимо всі згадки валют у тексті
        found_currencies = []
        for token in doc:
            if token.text.lower() in currency_map:
                found_currencies.append(currency_map[token.text.lower()])

        # Якщо знайдено дві різні валюти, повертаємо їх як пару
        if len(found_currencies) >= 2 and found_currencies[0] != found_currencies[1]:
            return found_currencies[0], found_currencies[1]

        # Якщо знайдено одну валюту, комбінуємо її з UAH
        if len(found_currencies) == 1:
            if found_currencies[0] == "UAH":
                return "USD", "UAH"  # За замовчуванням, якщо згадано тільки гривню
            else:
                return found_currencies[0], "UAH"  # Інакше використовуємо знайдену валюту і гривню

        # За замовчуванням
        return "USD", "UAH"

    def _extract_news_details(self, doc: Doc) -> Tuple[str, Optional[str]]:
        """
        Витягування деталей новинного запиту
        :param doc: Документ spaCy
        :return: Кортеж (категорія, запит)
        """
        # Базові категорії новин
        categories = {
            "бізнес": "business",
            "технології": "technology",
            "спорт": "sports",
            "наука": "science",
            "здоров'я": "health",
            "політика": "general",
            "економіка": "business",
            "розваги": "entertainment",
            # Додаємо відмінки слів та синоніми
            "спорті": "sports",
            "спортивні": "sports",
            "спортивний": "sports",
            "технологіях": "technology",
            "науці": "science",
            "науковий": "science",
            "наукові": "science",
            "бізнесу": "business",
            "бізнесові": "business",
            "політичні": "general",
            "політичний": "general",
            "політиці": "general",
            "здоров'ї": "health",
            "медичні": "health",
            "медицина": "health"
        }

        # Шукаємо категорію в тексті
        category = "general"  # За замовчуванням
        query = None

        # Пошук категорії в повному тексті
        text_lower = doc.text.lower()
        for cat_word, cat_value in categories.items():
            if cat_word in text_lower:
                category = cat_value
                break

        # Якщо категорія не виявлена, шукаємо в окремих токенах
        if category == "general":
            for token in doc:
                if token.text.lower() in categories:
                    category = categories[token.text.lower()]
                    break

        # Для відладки виводимо у лог
        logger.info(f"Визначена категорія новин: {category} з тексту: '{text_lower}'")

        # Пошук пошукового запиту (іменники і власні назви)
        # Ігноруємо слова, пов'язані з новинами і категоріями
        ignore_words = ["новини", "новина", "події", "новинами", "новинах",
                        "розкажи", "скажи", "покажи", "дізнатися", "дізнатись"] + list(categories.keys())

        nouns = []
        for token in doc:
            if token.pos_ in ["NOUN", "PROPN", "ADJ"] and token.text.lower() not in ignore_words:
                nouns.append(token.text)

        if nouns:
            query = " ".join(nouns)
            logger.info(f"Сформований запит для новин: '{query}'")

        # Якщо запит порожній, але категорія не general, використовуємо категорію як запит
        if not query and category != "general":
            # Отримуємо назву категорії українською
            for cat_word, cat_value in categories.items():
                if cat_value == category:
                    query = cat_word
                    break
            logger.info(f"Використовуємо категорію як запит: '{query}'")

        return category, query


# Створення глобального екземпляра NLP процесора
try:
    nlp_processor = NLPProcessor(model="uk_core_news_sm")
    logger.info("NLP процесор успішно ініціалізовано з українською моделлю")
except Exception as e:
    logger.error(f"Помилка ініціалізації NLP процесора: {e}")
    logger.info("Використання базової моделі")
    nlp_processor = NLPProcessor(model="en_core_web_sm")


async def process_nlp_request(message: Message, state: Optional[FSMContext] = None) -> bool:
    """
    Обробка запиту користувача з використанням NLP
    :param message: Повідомлення користувача
    :param state: FSM контекст (опціонально)
    :return: True, якщо запит успішно оброблено, False у іншому випадку
    """
    if not message.text:
        return False

    try:
        # Виводимо у лог оригінальний текст для відладки
        logger.info(f"Обробляємо запит від користувача: '{message.text}'")

        # Використання NLP процесора для аналізу тексту
        nlp_result = nlp_processor.process_text(message.text)

        intent = nlp_result["intent"]
        confidence = nlp_result["confidence"]
        entities = nlp_result["entities"]

        logger.info(f"NLP результат: намір={intent}, впевненість={confidence}, сутності={entities}")

        # Знизимо мінімальний поріг для кращого результату
        if confidence < 0.4:
            logger.info(f"Низька впевненість ({confidence}) для запиту: {message.text}")

            # Якщо в тексті є явні ключові слова, спробуємо примусово встановити намір
            text_lower = message.text.lower()

            if any(word in text_lower for word in ["погода", "температура", "градус"]):
                intent = "weather"
                logger.info(f"Примусово встановлюємо намір 'weather' на основі ключових слів")
            elif any(word in text_lower for word in ["валюта", "курс", "долар", "євро", "гривня"]):
                intent = "currency"
                logger.info(f"Примусово встановлюємо намір 'currency' на основі ключових слів")
            elif any(word in text_lower for word in ["новини", "новина", "події", "спорт", "політика"]):
                intent = "news"
                logger.info(f"Примусово встановлюємо намір 'news' на основі ключових слів")
            else:
                return False

        # Обробка різних намірів
        if intent == "weather":
            city = entities.get("city", "Київ")
            logger.info(f"Обробляємо запит погоди для міста: {city}")
            await process_weather_request(message, city, state)
            return True

        elif intent == "currency":
            base = entities.get("base", "USD")
            target = entities.get("target", "UAH")
            logger.info(f"Обробляємо запит валюти: {base} -> {target}")
            await process_currency_request(message, base, target)
            return True

        elif intent == "news":
            category = entities.get("category", "general")
            query = entities.get("query")

            # Якщо запит про конкретний тип новин, але запит пустий, використовуємо категорію як запит
            if category != "general" and not query:
                # Створюємо запит на основі категорії
                category_map = {
                    "business": "бізнес",
                    "technology": "технології",
                    "sports": "спорт",
                    "science": "наука",
                    "health": "здоров'я",
                    "general": "загальні",
                    "entertainment": "розваги"
                }
                query = category_map.get(category, category)
                logger.info(f"Використовуємо категорію як запит: {query}")

            logger.info(f"Обробляємо запит новин. Категорія: {category}, Запит: {query}")
            await process_news_request(message, query=query, category=category, state=state)
            return True

        return False

    except Exception as e:
        logger.error(f"Помилка при обробці NLP запиту: {e}")
        return False

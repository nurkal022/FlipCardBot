import json
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
from bot.config import settings


def get_client() -> AsyncOpenAI:
    """Получить клиент OpenAI"""
    return AsyncOpenAI(api_key=settings.openai_api_key)


async def generate_word_card(term: str) -> Dict[str, Any]:
    """
    Генерирует карточку слова через OpenAI.
    Возвращает структурированный JSON с полями карточки.
    """
    prompt = f"""Generate a vocabulary card for the English word/phrase: "{term}"

Return ONLY a valid JSON object with the following structure:
{{
  "term": "{term}",
  "pos": "part of speech (noun/verb/adjective/adverb/phrasal verb/etc.)",
  "ipa": "IPA pronunciation in format /ɪmˈbærəst/",
  "reading_ru": "simplified pronunciation in Russian letters (e.g., им-БЭ-рэст)",
  "translations_ru": ["translation 1", "translation 2", "translation 3"],
  "definition_en": "simple English definition in one sentence",
  "examples": [
    {{"en": "English example sentence 1", "ru": "Russian translation 1"}},
    {{"en": "English example sentence 2", "ru": "Russian translation 2"}}
  ]
}}

Requirements:
- Provide 1-3 Russian translations
- Provide exactly 2 examples with both English and Russian
- Keep definitions simple and clear
- For phrasal verbs, include the full phrase in "term"
- Return ONLY the JSON, no additional text"""

    try:
        client = get_client()
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful English vocabulary assistant. Always return valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.7
        )
        
        content = response.choices[0].message.content
        card_data = json.loads(content)
        
        # Валидация обязательных полей
        required_fields = ["term", "translations_ru", "definition_en", "examples"]
        for field in required_fields:
            if field not in card_data:
                raise ValueError(f"Missing required field: {field}")
        
        return card_data
        
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse AI response as JSON: {e}")
    except Exception as e:
        raise ValueError(f"AI generation failed: {e}")


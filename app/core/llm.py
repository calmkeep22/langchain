from app.core.config import get_settings


class LLMConfigError(Exception):
    pass


def get_llm():
    settings = get_settings()

    if settings.mistral_api_key:
        from langchain_mistralai import ChatMistralAI

        return ChatMistralAI(model="mistral-small-latest", api_key=settings.mistral_api_key)

    if settings.openai_api_key:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="gpt-4o-mini", api_key=settings.openai_api_key)

    raise LLMConfigError("No LLM API key configured.")

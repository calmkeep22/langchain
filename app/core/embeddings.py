from app.core.config import get_settings


class EmbeddingConfigError(Exception):
    pass


def get_embeddings():
    settings = get_settings()

    if settings.mistral_api_key:
        from langchain_mistralai import MistralAIEmbeddings

        return MistralAIEmbeddings(model="mistral-embed", api_key=settings.mistral_api_key)

    if settings.openai_api_key:
        from langchain_openai import OpenAIEmbeddings

        return OpenAIEmbeddings(api_key=settings.openai_api_key)

    raise EmbeddingConfigError("No embedding API key configured.")

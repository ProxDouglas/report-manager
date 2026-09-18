from langchain_openai import ChatOpenAI

from relatorios_service.config import settings


def create_chat_model() -> ChatOpenAI:
    model_kwargs: dict[str, object] = {
        "api_key": settings.openai_api_key,
        "model": settings.llm_model,
        "temperature": 0,
    }

    if settings.openai_base_url:
        model_kwargs["base_url"] = settings.openai_base_url

    return ChatOpenAI(**model_kwargs)

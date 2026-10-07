import anthropic
import structlog

from app.config import settings
from app.exceptions import ChatError

logger = structlog.get_logger()


class AnthropicClient:
    def __init__(self) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        self._model = settings.llm_model

    async def complete(
        self,
        system: str,
        messages: list[dict[str, str]],
        max_tokens: int = 2048,
    ) -> str:
        try:
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,  # type: ignore[arg-type]
            )
            return response.content[0].text  # type: ignore[union-attr]
        except anthropic.APIError as e:
            logger.error('anthropic_api_error', error=str(e))
            raise ChatError(f'Anthropic API error: {e}') from e

    def is_configured(self) -> bool:
        key = settings.anthropic_api_key
        return bool(key and key.startswith('sk-ant-'))


anthropic_client = AnthropicClient()

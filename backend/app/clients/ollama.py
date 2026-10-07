import httpx
import structlog

from app.config import settings
from app.exceptions import EmbeddingError

logger = structlog.get_logger()


class OllamaClient:
    def __init__(self) -> None:
        self._base_url = settings.ollama_url
        self._model = settings.embedding_model

    async def embed(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f'{self._base_url}/api/embeddings',
                    json={'model': self._model, 'prompt': text},
                )
                response.raise_for_status()
                return response.json()['embedding']  # type: ignore[no-any-return]
            except httpx.HTTPError as e:
                logger.error('ollama_embed_failed', error=str(e))
                raise EmbeddingError(f'Failed to generate embedding: {e}') from e

    async def is_available(self) -> bool:
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                response = await client.get(f'{self._base_url}/api/tags')
                return response.status_code == 200
            except httpx.HTTPError:
                return False


ollama_client = OllamaClient()

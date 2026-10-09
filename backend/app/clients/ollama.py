import httpx
import structlog

from app.config import settings
from app.exceptions import EmbeddingError

logger = structlog.get_logger()


class OllamaClient:
    def __init__(self) -> None:
        self._base_url = settings.ollama_url
        self._model = settings.embedding_model
        self._client = httpx.AsyncClient(timeout=30.0)

    async def embed(self, text: str) -> list[float]:
        try:
            response = await self._client.post(
                f"{self._base_url}/api/embeddings",
                json={"model": self._model, "prompt": text},
            )
            response.raise_for_status()
            data = response.json()
            if "embedding" not in data:
                fields = list(data.keys())
                raise EmbeddingError(f"Ollama response missing embedding field: {fields}")
            return data["embedding"]  # type: ignore[no-any-return]
        except httpx.HTTPError as e:
            logger.error("ollama_embed_failed", error=str(e))
            raise EmbeddingError(f"Failed to generate embedding: {e}") from e

    async def is_available(self) -> bool:
        try:
            response = await self._client.get(
                f"{self._base_url}/api/tags",
                timeout=5.0,
            )
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def aclose(self) -> None:
        await self._client.aclose()


ollama_client = OllamaClient()

"""Protocol for LLM interactions (GeminiClient and FakeClient)."""

from typing import Any, Protocol

from app.llm.schemas import Extraction


class LLMClient(Protocol):
    """Protocol defining model calls for extraction, embedding, and cited Q&A."""

    async def extract_heritage(
        self,
        file_bytes: bytes,
        mime: str,
        prompt_version: str = "v1",
    ) -> Extraction:
        """Run multimodal vision/OCR extraction on photo, manuscript scan, or journal."""
        ...

    async def embed_text(
        self,
        text: str,
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> list[float]:
        """Generate 768-dimensional L2-normalized text embedding vector."""
        ...

    async def ask_archive(
        self,
        question: str,
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate cited answer with source references or polite refusal if insufficient."""
        ...


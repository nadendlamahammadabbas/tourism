"""Live Gemini LLM client implementing the LLMClient protocol via google-genai SDK."""

import asyncio
import math
import random
from typing import Any

from google import genai
from google.genai import types

from app.config import settings
from app.llm.base import LLMClient
from app.llm.fake import FakeClient
from app.llm.prompts import HERITAGE_ASK_SYSTEM_PROMPT, HERITAGE_EXTRACTION_SYSTEM_PROMPT
from app.llm.schemas import Extraction
from app.logging import logger
from app.pipeline.images import downscale_image


class GeminiClient(LLMClient):
    """Google Gemini AI client using gemini-3.8-flash and gemini-embedding-2."""

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.fake_client = FakeClient()
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    async def extract_heritage(
        self,
        file_bytes: bytes,
        mime: str,
        prompt_version: str = "v1",
    ) -> Extraction:
        # Fall back to fake client if no live key is configured
        if not self.client or settings.LLM_MODE == "fake":
            return await self.fake_client.extract_heritage(file_bytes, mime, prompt_version)

        # Downscale large images to <= 2048px before transmission
        processed_bytes = downscale_image(file_bytes, max_long_edge=2048) if mime != "application/pdf" else file_bytes
        part = types.Part.from_bytes(data=processed_bytes, mime_type=mime)

        models_to_try = [settings.GEMINI_MODEL, settings.GEMINI_MODEL_FALLBACK]
        last_error: Exception | None = None

        for model_id in models_to_try:
            for attempt in range(3):
                try:
                    logger.info("gemini_extract_attempt", model=model_id, attempt=attempt + 1)
                    config = types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=Extraction,
                        thinking_config=types.ThinkingConfig(thinking_level="low"),
                        system_instruction=HERITAGE_EXTRACTION_SYSTEM_PROMPT,
                    )

                    # google-genai synchronous call run in executor for async compatibility
                    response = await asyncio.to_thread(
                        self.client.models.generate_content,
                        model=model_id,
                        contents=[part, "Please analyse this heritage document/monument photo and extract structured heritage metadata."],
                        config=config,
                    )

                    if response.text:
                        return Extraction.model_validate_json(response.text)

                except Exception as err:
                    last_error = err
                    logger.warning("gemini_extract_error", model=model_id, attempt=attempt + 1, error=str(err))
                    # Exponential backoff with jitter on 429/5xx
                    delay = (2 ** attempt) + random.uniform(0.1, 0.5)
                    await asyncio.sleep(delay)

        logger.error("gemini_extract_failed_all_attempts", error=str(last_error))
        # Graceful fallback to fixture or synthetic result
        return await self.fake_client.extract_heritage(file_bytes, mime, prompt_version)

    async def embed_text(
        self,
        text: str,
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> list[float]:
        if not self.client or settings.LLM_MODE == "fake":
            return await self.fake_client.embed_text(text, task_type)

        models_to_try = [settings.EMBED_MODEL, settings.EMBED_MODEL_FALLBACK]
        last_error: Exception | None = None

        for model_id in models_to_try:
            try:
                config = types.EmbedContentConfig(
                    output_dimensionality=settings.EMBED_DIM,
                    task_type=task_type,
                )
                response = await asyncio.to_thread(
                    self.client.models.embed_content,
                    model=model_id,
                    contents=text,
                    config=config,
                )
                if response.embedding and response.embedding.values:
                    vec = list(response.embedding.values)[:settings.EMBED_DIM]
                    # L2-normalize vector
                    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
                    return [v / norm for v in vec]
            except Exception as err:
                last_error = err
                logger.warning("gemini_embed_error", model=model_id, error=str(err))

        logger.error("gemini_embed_failed_all_models", error=str(last_error))
        return await self.fake_client.embed_text(text, task_type)

    async def ask_archive(
        self,
        question: str,
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.client or settings.LLM_MODE == "fake":
            return await self.fake_client.ask_archive(question, sources)

        if not sources:
            return {
                "answer": "The current archive records do not contain sufficient verified evidence to answer this question.",
                "citations": [],
                "confidence": 0.0,
            }

        context_lines = []
        for idx, src in enumerate(sources, start=1):
            context_lines.append(f"[{idx}] {src.get('text', '')}")
        context_block = "\n\n".join(context_lines)

        user_content = f"SOURCES:\n{context_block}\n\nQUESTION: {question}"

        try:
            config = types.GenerateContentConfig(
                system_instruction=HERITAGE_ASK_SYSTEM_PROMPT,
                thinking_config=types.ThinkingConfig(thinking_level="low"),
            )
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=settings.GEMINI_MODEL,
                contents=user_content,
                config=config,
            )

            citations = [
                {
                    "n": idx,
                    "asset_id": src.get("asset_id"),
                    "site_id": src.get("site_id"),
                    "snippet": src.get("text", "")[:120] + "...",
                }
                for idx, src in enumerate(sources, start=1)
            ]

            return {
                "answer": response.text or "No answer generated.",
                "citations": citations,
                "confidence": 0.9,
            }
        except Exception as e:
            logger.error("gemini_ask_error", error=str(e))
            return await self.fake_client.ask_archive(question, sources)

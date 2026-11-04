"""Deterministic FakeClient implementation for offline tests, CI, and demo reliability."""

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from app.llm.base import LLMClient
from app.llm.schemas import Entity, Extraction, LocationHint


class FakeClient(LLMClient):
    """Deterministic LLM client using cached JSON fixtures or seeded generators."""

    def __init__(self, fixtures_dir: Path | str | None = None) -> None:
        self.fixtures_dir = Path(fixtures_dir) if fixtures_dir else Path("data/fixtures")

    async def extract_heritage(
        self,
        file_bytes: bytes,
        mime: str,
        prompt_version: str = "v1",
    ) -> Extraction:
        sha256 = hashlib.sha256(file_bytes).hexdigest()
        fixture_file = self.fixtures_dir / f"{sha256}.json"

        if fixture_file.exists():
            with open(fixture_file, encoding="utf-8") as f:
                data = json.load(f)
                return Extraction.model_validate(data)

        # Fallback to realistic deterministic mock based on hash
        is_pdf = mime == "application/pdf"

        if is_pdf:
            return Extraction(
                kind="document",
                title="Historical Inscription Register of Gujarat",
                site_name="Rani ki Vav",
                monument_type="stepwell",
                era_estimate="11th century CE (Solanki dynasty)",
                architectural_features=["multi-storeyed pavilion", "stepped corridor", "sculpted niches"],
                materials=["sandstone", "lime mortar"],
                language="Hindi",
                script="Devanagari",
                transcript="राणी की वाव भारत के गुजरात राज्य के पाटण में स्थित एक प्रसिद्ध बावड़ी है।",
                translation_en="Rani ki Vav is a renowned stepwell located in Patan, Gujarat, India.",
                entities=[
                    Entity(type="place", text="Patan"),
                    Entity(type="place", text="Gujarat"),
                    Entity(type="dynasty", text="Solanki dynasty"),
                    Entity(type="date", text="1063 CE"),
                ],
                location_hint=LocationHint(
                    name="Patan, Gujarat",
                    lat=23.8589,
                    lng=72.1017,
                    confidence=0.95,
                ),
                summary="An exceptional multi-storey stepwell constructed in the Maru-Gurjara architectural style under Queen Udayamati. Revered for intricate Vishnu avatar sculptures and subterranean pavilion architecture.",
                confidence=0.94,
                uncertainty_notes=None,
            )

        # Default photo mock
        return Extraction(
            kind="photo",
            title="Carved Stepwell Pavilion Pillar",
            site_name="Adalaj Stepwell",
            monument_type="stepwell",
            era_estimate="Late 15th century CE (1498 CE)",
            architectural_features=["octagonal shaft", "floral bracket capitals", "chhatri pavilions"],
            materials=["sandstone"],
            language=None,
            script=None,
            transcript=None,
            translation_en=None,
            entities=[
                Entity(type="place", text="Adalaj"),
                Entity(type="place", text="Gandhinagar"),
                Entity(type="dynasty", text="Vaghela dynasty"),
                Entity(type="date", text="1498 CE"),
            ],
            location_hint=LocationHint(
                name="Adalaj, Gandhinagar, Gujarat",
                lat=23.1667,
                lng=72.5833,
                confidence=0.92,
            ),
            summary="Intricately carved sandstone pillar showing Indo-Islamic architectural synthesis in the subterranean five-storey stepwell at Adalaj. Features Solanki-style carved friezes with decorative floral and elephant reliefs.",
            confidence=0.91,
            uncertainty_notes="Exact pillar tier is obscured by lighting; identified as tier 2 from balcony perspective.",
        )

    async def embed_text(
        self,
        text: str,
        task_type: str = "RETRIEVAL_DOCUMENT",
    ) -> list[float]:
        """Generate deterministic 768-d unit vector from text sha256 hash."""
        vec = []
        for i in range(768):
            seed_str = f"{text}:{i}"
            h = hashlib.sha256(seed_str.encode("utf-8")).digest()
            val = (int.from_bytes(h[:4], "little") / (2**32)) * 2.0 - 1.0
            vec.append(val)

        # L2-normalize
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    async def ask_archive(
        self,
        question: str,
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Generate cited answer using provided context."""
        if not sources:
            return {
                "answer": "The archive does not contain sufficient verified sources to answer this question accurately.",
                "citations": [],
                "confidence": 0.0,
            }

        citations = []
        for idx, src in enumerate(sources[:3], start=1):
            citations.append({
                "n": idx,
                "asset_id": src.get("asset_id"),
                "site_id": src.get("site_id"),
                "snippet": src.get("text", "")[:120] + "...",
            })

        answer = (
            "Based on historical records in the archive [1], this structure represents classical "
            "regional architecture characterized by intricate subterranean pavilions and relief carving [2]."
        )
        return {
            "answer": answer,
            "citations": citations,
            "confidence": 0.92,
        }


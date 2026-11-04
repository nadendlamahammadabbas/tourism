"""Pydantic schemas for structured LLM extractions conforming to Gemini response_schema."""

from typing import Literal

from pydantic import BaseModel, Field


class Entity(BaseModel):
    """Named entity identified in document or monument description."""

    type: Literal["place", "person", "date", "deity", "dynasty", "craft", "other"]
    text: str


class LocationHint(BaseModel):
    """Inferred or identified geographical reference."""

    name: str | None = None
    lat: float | None = None
    lng: float | None = None
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence in coordinates from 0 to 1")


class Extraction(BaseModel):
    """Complete structured extraction from image or document scan."""

    kind: Literal["photo", "document", "journal"] = "photo"
    title: str = Field(description="Descriptive heritage title")
    site_name: str | None = Field(default=None, description="Recognized monument or site name")
    monument_type: Literal[
        "stepwell",
        "fort",
        "temple",
        "mosque",
        "haveli",
        "palace",
        "craft",
        "manuscript",
        "other",
    ] = "other"
    era_estimate: str | None = Field(default=None, description="Estimated era e.g. '11th century CE'")
    architectural_features: list[str] = Field(default_factory=list)
    materials: list[str] = Field(default_factory=list)
    language: str | None = Field(
        default=None, description="ISO name e.g. 'Hindi', 'Gujarati', 'Sanskrit'"
    )
    script: str | None = Field(default=None, description="Script name e.g. 'Devanagari'")
    transcript: str | None = Field(
        default=None, description="Verbatim transcription in original script"
    )
    translation_en: str | None = Field(
        default=None, description="English translation of transcript"
    )
    entities: list[Entity] = Field(default_factory=list)
    location_hint: LocationHint | None = None
    summary: str = Field(description="2 concise sentences in plain English")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Overall extraction confidence between 0 and 1"
    )
    uncertainty_notes: str | None = Field(
        default=None, description="Honest statement of ambiguities or illegibility"
    )


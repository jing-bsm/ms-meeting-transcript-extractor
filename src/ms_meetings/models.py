from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import Any


@dataclass
class TranscriptSegment:
    speaker: str
    text: str
    timestamp: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TranscriptDocument:
    source_url: str
    title: str
    segments: list[TranscriptSegment] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    extracted_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_url": self.source_url,
            "title": self.title,
            "warnings": self.warnings,
            "extracted_at": self.extracted_at,
            "segments": [segment.to_dict() for segment in self.segments],
        }

    def to_markdown(self) -> str:
        lines = [f"# {self.title}", "", f"Source: {self.source_url}", ""]
        if self.warnings:
            lines.append("Warnings:")
            for warning in self.warnings:
                lines.append(f"- {warning}")
            lines.append("")

        for segment in self.segments:
            heading = segment.speaker or "Unknown speaker"
            if segment.timestamp:
                heading = f"{heading} ({segment.timestamp})"
            lines.append(f"## {heading}")
            lines.append("")
            lines.append(segment.text)
            lines.append("")

        return "\n".join(lines).strip() + "\n"


@dataclass
class ExtractionArtifacts:
    transcript_path: str
    metadata_path: str
    title: str
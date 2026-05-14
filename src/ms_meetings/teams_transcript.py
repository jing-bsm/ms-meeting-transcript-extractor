from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json
import re
import time

from bs4 import BeautifulSoup
from bs4 import Tag
from playwright.sync_api import Page

from ms_meetings.models import ExtractionArtifacts
from ms_meetings.models import TranscriptDocument
from ms_meetings.models import TranscriptSegment


TIMESTAMP_RE = re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?(?:\s?[AP]M)?\b", re.IGNORECASE)
TRANSCRIPT_HINT_RE = re.compile(r"transcript|captions|closed captions", re.IGNORECASE)
NAME_PATTERN = r"(?:[A-Z]{1,4}\s+)?(?:[A-Z][a-z]+,\s+[A-Z][a-z]+|[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})"
SPEAKER_MARKER_RE = re.compile(
    rf"(?P<speaker>{NAME_PATTERN})\s+"
    r"(?P<stamp>\d+\s+minutes?\s+\d+\s+seconds|(?:[01]?\d|2[0-3]):[0-5]\d(?:\s?[AP]M)?)",
)
NAME_CANDIDATE_RE = re.compile(NAME_PATTERN)


@dataclass
class ExtractionResult:
    document: TranscriptDocument
    html_snapshot: str
    body_text: str


class TranscriptExtractionError(RuntimeError):
    pass


def fetch_transcript(page: Page, source_url: str) -> ExtractionResult:
    _wait_for_page_ready(page)
    _expand_transcript_ui(page)
    html = page.content()
    body_text = page.locator("body").inner_text(timeout=10000)
    title = page.title().strip() or "Meeting Transcript"

    document = parse_transcript_text(body_text=body_text, source_url=source_url, title=title)
    if not document.segments:
        fallback_document = parse_transcript_html(html=html, source_url=source_url, title=title)
        fallback_document.warnings.extend(document.warnings)
        document = fallback_document

    if not document.segments:
        raise TranscriptExtractionError(
            "No transcript segments were found. Confirm that the recap page is loaded, transcript is available, "
            "and the account in Chrome can access it."
        )

    document.extracted_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    return ExtractionResult(document=document, html_snapshot=html, body_text=body_text)


def save_artifacts(document: TranscriptDocument, output_dir: Path, slug: str) -> ExtractionArtifacts:
    output_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = output_dir / f"{slug}.transcript.md"
    metadata_path = output_dir / f"{slug}.metadata.json"

    transcript_path.write_text(document.to_markdown(), encoding="utf-8")
    metadata_path.write_text(json.dumps(document.to_dict(), indent=2), encoding="utf-8")
    return ExtractionArtifacts(
        transcript_path=str(transcript_path),
        metadata_path=str(metadata_path),
        title=document.title,
    )


def parse_transcript_html(html: str, source_url: str, title: str) -> TranscriptDocument:
    soup = BeautifulSoup(html, "lxml")
    warnings: list[str] = []
    candidate_nodes = _find_candidate_nodes(soup)
    if not candidate_nodes:
        warnings.append("No transcript-specific container found in HTML; falling back to generic parsing.")
        candidate_nodes = [soup.body or soup]

    segments: list[TranscriptSegment] = []
    for candidate in candidate_nodes:
        segments.extend(_parse_segments_from_candidate(candidate))

    segments = _dedupe_segments(segments)
    return TranscriptDocument(source_url=source_url, title=title, segments=segments, warnings=warnings)


def parse_transcript_text(body_text: str, source_url: str, title: str) -> TranscriptDocument:
    normalized_text = _normalize_body_text(body_text)
    segments = _parse_segments_from_text(normalized_text)
    if not segments:
        segments = _parse_linewise_segments(normalized_text)
    return TranscriptDocument(
        source_url=source_url,
        title=title,
        segments=segments,
        warnings=["Used body text fallback parsing."],
    )


def slugify_title(title: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    return normalized or f"meeting-{int(time.time())}"


def _wait_for_page_ready(page: Page) -> None:
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        page.wait_for_timeout(3000)
    body_text = page.locator("body").inner_text(timeout=10000)
    lowered = body_text.lower()
    if "access denied" in lowered or "sign in" in lowered and "transcript" not in lowered:
        raise TranscriptExtractionError(
            "The page appears unauthenticated or inaccessible. Open the URL in your main Chrome profile and confirm access."
        )


def _expand_transcript_ui(page: Page) -> None:
    labels = [
        "Transcript",
        "View transcript",
        "Open transcript",
        "Show transcript",
        "Captions",
        "Show more",
        "See more",
    ]
    for label in labels:
        locator = page.get_by_text(label, exact=False)
        count = min(locator.count(), 3)
        for index in range(count):
            item = locator.nth(index)
            try:
                if item.is_visible(timeout=1500):
                    item.click(timeout=1500)
                    page.wait_for_timeout(500)
            except Exception:
                continue


def _find_candidate_nodes(soup: BeautifulSoup) -> list[Tag]:
    candidates: list[Tag] = []
    for node in soup.find_all(True):
        attrs = " ".join(
            [
                node.get("id", ""),
                " ".join(node.get("class", [])),
                node.get("data-tid", ""),
                node.get("aria-label", ""),
            ]
        )
        text = node.get_text(" ", strip=True)
        if TRANSCRIPT_HINT_RE.search(attrs) or (len(text) < 300 and TRANSCRIPT_HINT_RE.search(text)):
            candidates.append(node)
    return candidates[:12]


def _parse_segments_from_candidate(candidate: Tag) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    item_nodes = candidate.find_all(["li", "article", "section", "div"], recursive=True)
    for item in item_nodes:
        text = item.get_text("\n", strip=True)
        if not text or len(text) < 8:
            continue
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        segment = _parse_lines(lines)
        if segment is not None:
            segments.append(segment)
    return segments


def _parse_lines(lines: list[str]) -> TranscriptSegment | None:
    if len(lines) < 2:
        return None

    speaker = ""
    timestamp: str | None = None
    payload_lines = lines[:]

    header = lines[0]
    parsed = _parse_line_header(header)
    if parsed is not None:
        speaker, timestamp, remainder = parsed
        payload_lines = [remainder] + lines[1:] if remainder else lines[1:]
    else:
        speaker = header
        maybe_time = TIMESTAMP_RE.search(lines[1])
        if maybe_time and len(lines[1]) <= 32:
            timestamp = maybe_time.group(0)
            payload_lines = lines[2:]
        else:
            payload_lines = lines[1:]

    payload = " ".join([line for line in payload_lines if line]).strip()
    if not speaker or not payload:
        return None
    if len(speaker.split()) > 8:
        return None
    return TranscriptSegment(speaker=speaker, timestamp=timestamp, text=payload)


def _parse_line_header(line: str) -> tuple[str, str | None, str] | None:
    timestamp_match = TIMESTAMP_RE.search(line)
    if timestamp_match:
        before = line[: timestamp_match.start()].strip(" -|")
        after = line[timestamp_match.end() :].strip(" -|")
        if before and len(before.split()) <= 8:
            return before, timestamp_match.group(0), after

    parts = [part.strip() for part in line.split(" - ") if part.strip()]
    if len(parts) >= 2 and len(parts[0].split()) <= 8 and TIMESTAMP_RE.fullmatch(parts[1]):
        remainder = " - ".join(parts[2:]).strip()
        return parts[0], parts[1], remainder
    return None


def _dedupe_segments(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    best_by_key: dict[tuple[str, str | None], TranscriptSegment] = {}
    for segment in segments:
        key = (segment.speaker, segment.timestamp)
        current = best_by_key.get(key)
        if current is None or len(segment.text) > len(current.text):
            best_by_key[key] = segment
    return list(best_by_key.values())


def _normalize_body_text(body_text: str) -> str:
    text = re.sub(r"[\ue000-\uf8ff]", " ", body_text)
    text = text.replace("AI-generated content may be incorrect", " ")
    text = re.sub(r"\s+", " ", text).strip()
    marker = "started transcription"
    marker_index = text.lower().find(marker)
    if marker_index != -1:
        text = text[marker_index + len(marker) :].strip()
    return text


def _parse_segments_from_text(text: str) -> list[TranscriptSegment]:
    matches = list(SPEAKER_MARKER_RE.finditer(text))
    segments: list[TranscriptSegment] = []
    for index, match in enumerate(matches):
        speaker = _clean_speaker(match.group("speaker"))
        timestamp = match.group("stamp")
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        payload = text[start:end].strip(" .")
        payload = _strip_repeated_prefix(payload, speaker, timestamp)
        if not speaker or not payload:
            continue
        segments.append(TranscriptSegment(speaker=speaker, timestamp=timestamp, text=payload))
    return _dedupe_segments(segments)


def _clean_speaker(raw: str) -> str:
    speaker = raw.strip(" -|")
    speaker = re.sub(r"\s+", " ", speaker)
    matches = NAME_CANDIDATE_RE.findall(speaker)
    if matches:
        speaker = matches[-1]
    return speaker


def _strip_repeated_prefix(payload: str, speaker: str, timestamp: str) -> str:
    payload = re.sub(r"^\d{1,2}:\d{2}(?:\s?[AP]M)?\s+", "", payload)
    repeated_prefix = f"{speaker} {timestamp}"
    while payload.startswith(repeated_prefix):
        payload = payload[len(repeated_prefix) :].strip(" .")
    return payload


def _parse_linewise_segments(text: str) -> list[TranscriptSegment]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    segments: list[TranscriptSegment] = []
    current_speaker: str | None = None
    current_timestamp: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_speaker, current_timestamp, current_lines
        if current_speaker and current_lines:
            segments.append(
                TranscriptSegment(
                    speaker=current_speaker,
                    timestamp=current_timestamp,
                    text=" ".join(current_lines).strip(),
                )
            )
        current_speaker = None
        current_timestamp = None
        current_lines = []

    for line in lines:
        parsed = _parse_line_header(line)
        if parsed is not None:
            flush()
            current_speaker, current_timestamp, remainder = parsed
            if remainder:
                current_lines.append(remainder)
            continue
        if current_speaker:
            current_lines.append(line)

    flush()
    return _dedupe_segments(segments)
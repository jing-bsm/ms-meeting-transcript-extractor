# MS Meetings

Python app managed by `uv` that opens a Microsoft Stream or Teams recap page in the main Google Chrome profile, extracts the finalized transcript, and saves a transcript artifact. A workspace Copilot skill then reads that artifact and generates a meeting summary plus key takeaways.

## Requirements

- macOS with Google Chrome installed at `/Applications/Google Chrome.app`
- `uv`
- Existing Microsoft 365 login in the default Chrome profile
- Chrome fully closed before running the extractor, because the real profile may be locked otherwise

## Install

```bash
uv sync
```

## Run

```bash
uv run ms-meetings '<stream-or-recap-url>'
```

Artifacts are written under `output/` by default:

- `*.transcript.md`: cleaned transcript
- `*.metadata.json`: run metadata and captured title

## Test

```bash
uv run pytest
```

## Skill

Invoke the workspace skill from chat after opening this repository:

```text
/teams-meeting-recap
```

The skill asks for the meeting URL, runs the local extractor, reads the transcript file, and writes a Markdown summary with key takeaways.

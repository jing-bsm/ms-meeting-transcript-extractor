# Product Design Document

## Goal

Create a Python app managed by `uv` that uses the real local Google Chrome profile to open a Microsoft Teams or Stream meeting recap URL, extract the finalized transcript from the page, save the transcript to a file, and support a Copilot workspace skill that summarizes the meeting and captures key takeaways.

## Users

- Primary user: a developer or analyst already signed into Microsoft 365 in the main Chrome profile.

## Functional Requirements

1. Accept a Teams recap or Stream URL as input.
2. Launch Google Chrome with the main profile, not a test browser profile.
3. Reuse existing authenticated browser state.
4. Detect inaccessible or unauthenticated pages and fail with actionable errors.
5. Extract transcript segments with speaker, timestamp when available, and spoken text.
6. Save a transcript Markdown file.
7. Save metadata as JSON.
8. Provide a workspace skill that runs the extractor, reads the transcript, and writes a separate summary Markdown file with key takeaways.

## Non-Goals

- Live caption capture during a running meeting
- Microsoft Graph integration
- Python-side LLM API usage

## Architecture

- `browser.py`: Chrome launch and page navigation using Playwright.
- `teams_transcript.py`: page readiness checks, transcript extraction, fallback parsing, and artifact persistence.
- `cli.py`: CLI entrypoint for local execution and skill orchestration.
- `.github/skills/teams-meeting-recap/SKILL.md`: Copilot skill instructions.

## Risks

- The real Chrome profile can be locked if Chrome is already running.
- Teams and Stream page markup can change without notice.
- The provided URL may require organization login and appropriate sharing permissions.

## Mitigations

- Emit a clear “close Chrome and retry” error when the profile is locked.
- Use layered transcript parsing and a text fallback.
- Verify with a real URL and document authentication expectations.
# Troubleshooting

## Chrome profile locked

- Close all Google Chrome windows.
- Retry the extractor.

## Access denied or sign-in page

- Open the URL manually in the main Chrome profile and confirm the page is accessible.
- Ensure the signed-in account has permission to view the Stream recording and transcript.

## Transcript not found

- Confirm the meeting has finished processing its recap.
- Confirm transcript generation was enabled for the recording.
- Retry after the page fully loads.

## Changed page structure

- Capture the page title and note whether transcript text is visible manually.
- Update selectors and fallback parsing in `src/ms_meetings/teams_transcript.py`.
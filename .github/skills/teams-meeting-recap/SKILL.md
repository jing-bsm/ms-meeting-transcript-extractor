---
name: teams-meeting-recap
description: "Use when extracting a finalized Microsoft Teams or Stream meeting transcript with the main Chrome profile, then summarizing the meeting and key takeaways into Markdown. Trigger words: Teams transcript, Stream recording transcript, meeting recap, summarize meeting recording, key takeaways."
argument-hint: "Provide the Teams or Stream URL and optional output directory"
user-invocable: true
---

# Teams Meeting Recap

## When to Use

- Extract the finalized transcript from a Microsoft Teams recap or Microsoft Stream recording page
- Save the transcript to disk from a local Python app using the real Chrome profile
- Summarize the meeting and write key takeaways without calling an external LLM API from Python

## Procedure

1. Ask the user for the Teams or Stream URL if it was not already supplied.
2. Remind the user to close all Chrome windows before extraction so the default profile is not locked.
3. Run the extractor:

   ```bash
   cd $HOME/workplace/pp/ai/ms-meetings && uv run ms-meetings '<URL>'
   ```

4. Read the generated `*.transcript.md` file under `output/`.
5. Produce a concise Markdown summary with these sections:
   - `# Summary`
   - `## Key Takeaways`
   - `## Actions`
   - `## Risks or Open Questions`
6. Save that summary as `output/<slug>.summary.md`.
7. If extraction fails, consult [troubleshooting](./references/troubleshooting.md) and report the precise blocker.

## Notes

- The Python app does not call an LLM API. The summarization step is performed by the chat agent after reading the transcript artifact.
- Use the workspace files instead of creating ad hoc scripts outside the repo.

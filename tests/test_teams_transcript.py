from ms_meetings.teams_transcript import parse_transcript_html
from ms_meetings.teams_transcript import parse_transcript_text
from ms_meetings.teams_transcript import slugify_title


def test_parse_transcript_html_extracts_segments() -> None:
    html = """
    <html>
      <body>
        <section aria-label="Transcript panel">
          <div class="transcript-item">
            <div>Alice Johnson 10:01 AM</div>
            <div>We completed the Jira workflow changes.</div>
          </div>
          <div class="transcript-item">
            <div>Bob Smith</div>
            <div>10:03 AM</div>
            <div>The Dora metric mapping will be reviewed tomorrow.</div>
          </div>
        </section>
      </body>
    </html>
    """

    document = parse_transcript_html(html, "https://example.test", "Jira Changes")

    assert len(document.segments) == 2
    assert document.segments[0].speaker == "Alice Johnson"
    assert document.segments[0].timestamp == "10:01 AM"
    assert "Jira workflow changes" in document.segments[0].text
    assert document.segments[1].speaker == "Bob Smith"
    assert document.segments[1].timestamp == "10:03 AM"


def test_parse_transcript_text_uses_body_fallback() -> None:
    body_text = """
    Transcript
    Alice Johnson 10:01 AM We completed the Jira workflow changes.
    Bob Smith 10:03 AM The Dora metric mapping will be reviewed tomorrow.
    """

    document = parse_transcript_text(body_text, "https://example.test", "Fallback")

    assert len(document.segments) == 2
    assert document.warnings == ["Used body text fallback parsing."]


def test_parse_transcript_text_dedupes_stream_repetition() -> None:
    body_text = """
    AI-generated content may be incorrect
    Wilson, Gillian started transcription
    Wilson, Gillian 0 minutes 3 seconds 0:03 Wilson, Gillian 0 minutes 3 seconds Some changes were made to Jira last week.
    Wilson, Gillian 0 minutes 22 seconds Teams want to track lead time into production.
    Wilson, Gillian 0 minutes 3 seconds Some changes were made to Jira last week.
    """

    document = parse_transcript_text(body_text, "https://example.test", "Fallback")

    assert len(document.segments) == 2
    assert document.segments[0].speaker == "Wilson, Gillian"
    assert document.segments[0].timestamp == "0 minutes 3 seconds"
    assert document.segments[1].timestamp == "0 minutes 22 seconds"


def test_slugify_title_handles_symbols() -> None:
    assert slugify_title("KT - Walk-through Jira changes!") == "kt-walk-through-jira-changes"
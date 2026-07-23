"""Build a self-contained .apkg deck using genanki.

Design decision
----------------
``genanki`` is the standard, well-maintained Python library for producing
Anki-compatible packages without needing Anki itself installed. Media files
referenced by a card (here, the cut video clip) are copied into the .apkg
by genanki as long as we pass their paths in ``Package.media_files`` --
this satisfies the "no external links, fully offline" requirement, since
Anki extracts the media into its collection on import.

Model/template design
----------------------
Front: the video clip (autoplay via an HTML5 <video> tag).
Back: front side + English (CC) subtitles, optional translation, and an
optional native-pronunciation tip.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

import genanki

from app.core.exceptions import AnkiBuildError
from app.logging_config import get_logger

logger = get_logger(__name__)

# Fixed, randomly-chosen-once IDs so re-imports update existing notes/decks
# instead of duplicating them. (Per genanki convention: keep these stable.)
_MODEL_ID = 1_607_392_819
_DECK_ID_SEED = "youtube-to-anki-generator"


def _stable_deck_id(seed: str) -> int:
    rng = random.Random(seed)
    return rng.randrange(1 << 30, 1 << 31)


_CARD_MODEL = genanki.Model(
    _MODEL_ID,
    "YouTube Listening Card",
    fields=[
        {"name": "Video"},
        {"name": "Transcript"},
        {"name": "Translation"},
        {"name": "PronunciationTip"},
        {"name": "Title"},
    ],
    templates=[
        {
            "name": "Listening Card",
            "qfmt": (
                '<div class="title">{{Title}}</div>'
                '<div class="video-wrap">{{Video}}</div>'
            ),
            "afmt": (
                '{{FrontSide}}<hr id="answer">'
                '<div class="transcript">{{Transcript}}</div>'
                '{{#Translation}}<div class="translation">{{Translation}}</div>{{/Translation}}'
                '{{#PronunciationTip}}<div class="tip">💡 {{PronunciationTip}}</div>{{/PronunciationTip}}'
            ),
        },
    ],
    css="""
        .card { font-family: -apple-system, Segoe UI, Roboto, sans-serif; font-size: 18px;
                text-align: center; color: #1a1a1a; background: #fafafa; }
        .title { font-weight: 600; margin-bottom: 8px; color: #555; }
        .video-wrap video { max-width: 100%; border-radius: 8px; }
        .transcript { margin-top: 12px; font-size: 20px; }
        .translation { margin-top: 8px; color: #444; font-style: italic; }
        .tip { margin-top: 10px; padding: 8px 12px; background: #fff3cd;
               border-radius: 6px; display: inline-block; font-size: 15px; }
    """,
)


@dataclass(slots=True)
class CardData:
    title: str
    video_path: Path
    transcript: str
    translation: str | None = None
    pronunciation_tip: str | None = None


def build_deck(deck_name: str, cards: list[CardData], output_path: Path) -> Path:
    if not cards:
        raise AnkiBuildError("No cards to build a deck from")

    deck = genanki.Deck(_stable_deck_id(f"{_DECK_ID_SEED}:{deck_name}"), deck_name)
    media_files: list[str] = []

    for card in cards:
        if not card.video_path.exists():
            raise AnkiBuildError(f"Missing media file for card: {card.video_path}")

        video_filename = card.video_path.name
        note = genanki.Note(
            model=_CARD_MODEL,
            fields=[
                f'<video controls autoplay src="{video_filename}"></video>',
                card.transcript,
                card.translation or "",
                card.pronunciation_tip or "",
                card.title,
            ],
        )
        deck.add_note(note)
        media_files.append(str(card.video_path))

    package = genanki.Package(deck)
    package.media_files = media_files

    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        package.write_to_file(str(output_path))
    except Exception as exc:
        raise AnkiBuildError(f"Failed to write .apkg file: {exc}") from exc

    logger.info("Built deck '%s' with %d cards -> %s", deck_name, len(cards), output_path)
    return output_path

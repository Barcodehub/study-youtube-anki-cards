import pytest

from app.core.exceptions import SegmentationError
from app.services.segmenter import _extract_json_array, _parse_segments


def test_extract_json_array_from_fenced_block() -> None:
    raw = '```json\n[{"title": "A", "start": "00:00:00.000", "end": "00:00:10.000"}]\n```'
    extracted = _extract_json_array(raw)
    assert extracted.startswith("[")
    assert extracted.endswith("]")


def test_extract_json_array_with_surrounding_commentary() -> None:
    raw = 'Sure! Here is the JSON:\n[{"title": "A", "start": "00:00:00.000", "end": "00:00:10.000"}]\nHope that helps.'
    extracted = _extract_json_array(raw)
    assert extracted == '[{"title": "A", "start": "00:00:00.000", "end": "00:00:10.000"}]'


def test_parse_segments_valid() -> None:
    raw = '[{"title": "Greeting", "start": "00:00:00.000", "end": "00:00:36.200"}]'
    segments = _parse_segments(raw)
    assert len(segments) == 1
    assert segments[0].title == "Greeting"
    assert segments[0].duration_seconds == pytest.approx(36.2)


def test_parse_segments_invalid_json_raises() -> None:
    with pytest.raises(SegmentationError):
        _parse_segments("not json at all")


def test_parse_segments_invalid_schema_raises() -> None:
    # Missing "end" field.
    raw = '[{"title": "Greeting", "start": "00:00:00.000"}]'
    with pytest.raises(SegmentationError):
        _parse_segments(raw)

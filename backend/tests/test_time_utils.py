import pytest

from app.utils.time_utils import seconds_to_timestamp, timestamp_to_seconds


@pytest.mark.parametrize(
    "ts, expected",
    [
        ("00:00:00.000", 0.0),
        ("00:00:36.200", 36.2),
        ("00:01:18.900", 78.9),
        ("01:00:00.000", 3600.0),
        ("00:00:05,500", 5.5),  # SRT comma variant
    ],
)
def test_timestamp_to_seconds(ts: str, expected: float) -> None:
    assert timestamp_to_seconds(ts) == pytest.approx(expected)


def test_timestamp_to_seconds_invalid() -> None:
    with pytest.raises(ValueError):
        timestamp_to_seconds("not-a-timestamp")


@pytest.mark.parametrize(
    "seconds, expected",
    [
        (0.0, "00:00:00.000"),
        (36.2, "00:00:36.200"),
        (78.9, "00:01:18.900"),
        (3600.0, "01:00:00.000"),
    ],
)
def test_seconds_to_timestamp(seconds: float, expected: str) -> None:
    assert seconds_to_timestamp(seconds) == expected


def test_roundtrip() -> None:
    original = "00:12:34.567"
    seconds = timestamp_to_seconds(original)
    assert seconds_to_timestamp(seconds) == original

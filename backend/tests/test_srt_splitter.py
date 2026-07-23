from pathlib import Path

from app.services.srt_splitter import read_segment_text, split_srt_for_segment

SAMPLE_SRT = """1
00:00:00,000 --> 00:00:05,000
Hello there, welcome to the video.

2
00:00:05,500 --> 00:00:12,000
Today we are going to order some coffee.

3
00:00:40,000 --> 00:00:45,000
This belongs to a much later segment.
"""


def test_split_srt_for_segment(tmp_path: Path) -> None:
    full_srt = tmp_path / "full.srt"
    full_srt.write_text(SAMPLE_SRT, encoding="utf-8")

    out_path = tmp_path / "segment_1.srt"
    split_srt_for_segment(full_srt, out_path, start_seconds=0.0, end_seconds=13.0)

    content = out_path.read_text(encoding="utf-8")
    assert "Hello there" in content
    assert "order some coffee" in content
    assert "much later segment" not in content
    # Re-timed: first cue should start at (or very near) 00:00:00.
    assert "00:00:00,000" in content


def test_read_segment_text(tmp_path: Path) -> None:
    srt_path = tmp_path / "seg.srt"
    srt_path.write_text(SAMPLE_SRT, encoding="utf-8")
    text = read_segment_text(srt_path)
    assert "Hello there, welcome to the video." in text
    assert "Today we are going to order some coffee." in text

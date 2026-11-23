"""한경코리아마켓 '모닝루틴(한국경제신문 30분 만에 읽기)' 당일 라이브의 유튜브 자막을 MD로 저장한다.

사용법:
  python scripts/fetch_transcript.py              # 오늘(KST) 방송
  python scripts/fetch_transcript.py 2026-11-20   # 특정 날짜 방송

종료 코드:
  0  저장 성공 또는 이미 저장됨
  2  해당 날짜 영상을 찾지 못함(휴일 등)
  3  영상은 찾았지만 자막이 아직 없음
  4  유튜브가 요청을 막음(봇 확인 등)
"""
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone

import yt_dlp

KST = timezone(timedelta(hours=9))
TITLE_PREFIX = "한국경제신문 30분 만에 읽기"
CHANNEL_HINT = "한경"
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "transcripts")

BLOCK_PATTERNS = ("Sign in to confirm you", "not a bot", "HTTP Error 429", "HTTP Error 403")


def log(msg):
    print(msg, flush=True)


def is_block_error(err):
    text = str(err)
    return any(p.lower() in text.lower() for p in BLOCK_PATTERNS)


def base_opts():
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    cookies = os.environ.get("YT_COOKIES_FILE")
    if cookies and os.path.exists(cookies):
        opts["cookiefile"] = cookies
    return opts


def find_video(date_compact):
    """제목에 'YYYYMMDD'가 들어간 모닝루틴 영상을 검색으로 찾는다."""
    query = f"ytsearch10:{TITLE_PREFIX} {date_compact}"
    opts = base_opts() | {"extract_flat": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        result = ydl.extract_info(query, download=False)
    for entry in result.get("entries") or []:
        title = entry.get("title") or ""
        channel = entry.get("channel") or entry.get("uploader") or ""
        if TITLE_PREFIX in title and date_compact in title and (not channel or CHANNEL_HINT in channel):
            return entry.get("id"), title
    return None, None


def fmt_ts(seconds):
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def parse_json3(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    lines = []
    for ev in data.get("events", []):
        segs = ev.get("segs")
        if not segs:
            continue
        text = "".join(s.get("utf8", "") for s in segs).replace("\n", " ").strip()
        if not text:
            continue
        lines.append((ev.get("tStartMs", 0) / 1000, text))
    return lines


def fetch_subtitles(video_id):
    """한국어 수동 자막 → 한국어 자동 자막 순으로 json3 자막을 받는다."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmp:
        opts = base_opts() | {
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["ko", "ko-orig"],
            "subtitlesformat": "json3",
            "outtmpl": os.path.join(tmp, "%(id)s.%(ext)s"),
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        files = sorted(f for f in os.listdir(tmp) if f.endswith(".json3"))
        if not files:
            return info, None, None
        manual = set((info.get("subtitles") or {}).keys())
        # 수동 자막 파일이 있으면 우선
        chosen = next((f for f in files if f.split(".")[-2] in manual), files[0])
        kind = "수동 자막" if chosen.split(".")[-2] in manual else "자동 생성 자막"
        return info, parse_json3(os.path.join(tmp, chosen)), kind


def merge_lines(lines, min_gap=5.0):
    """자동 자막은 조각이 잘게 나뉘므로 약 5초 단위로 합쳐 읽기 좋게 만든다."""
    merged = []
    for start, text in lines:
        if merged and start - merged[-1][0] < min_gap and len(merged[-1][1]) < 120:
            merged[-1] = (merged[-1][0], merged[-1][1] + " " + text)
        else:
            merged.append((start, text))
    return merged


def main():
    if len(sys.argv) > 1:
        day = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    else:
        day = datetime.now(KST).date()
    date_iso, date_compact = day.isoformat(), day.strftime("%Y%m%d")
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"hankyung_{date_iso}_transcript.md")
    if os.path.exists(out_path):
        log(f"이미 저장됨: {out_path}")
        return 0

    try:
        video_id, title = find_video(date_compact)
    except Exception as e:  # noqa: BLE001
        log(f"검색 실패: {e}")
        return 4 if is_block_error(e) else 2
    if not video_id:
        log(f"{date_compact} 모닝루틴 영상을 찾지 못함")
        return 2
    log(f"영상 발견: {title} ({video_id})")

    try:
        info, lines, kind = fetch_subtitles(video_id)
    except Exception as e:  # noqa: BLE001
        log(f"자막 요청 실패: {e}")
        return 4 if is_block_error(e) else 3
    if not lines:
        log("자막이 아직 없음")
        return 3

    merged = merge_lines(lines)
    url = f"https://www.youtube.com/watch?v={video_id}"
    header = [
        f"# {title}",
        "",
        f"- 방송일: {date_iso}",
        f"- 영상: {url}",
        f"- 채널: {info.get('channel') or info.get('uploader') or ''}",
        f"- 영상 길이: {fmt_ts(info.get('duration') or 0)}",
        f"- 자막 종류: {kind} (원자막 조각 {len(lines)}개 → {len(merged)}줄로 병합)",
        f"- 수집 시각(KST): {datetime.now(KST).strftime('%Y-%m-%d %H:%M')}",
        "- 주의: 유튜브 자막을 그대로 옮긴 것으로 고유명사·숫자·단위에 오인식이 있을 수 있음",
        "",
        "## 스크립트",
        "",
    ]
    body = [f"{fmt_ts(t)} {text}" for t, text in merged]
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(header + body) + "\n")
    log(f"저장 완료: {out_path} ({len(merged)}줄, 마지막 {body[-1][:40]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

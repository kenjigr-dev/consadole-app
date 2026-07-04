"""コンサドーレ情報ボード: データ取得モジュール

- ニュース: Google News RSS (安定・キー不要)
- 日程・結果: クラブ公式サイトのスクレイピング(失敗時はスナップショットに自動フォールバック)
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import quote

import feedparser
import requests
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 (personal fan dashboard; contact: local user)"}
TIMEOUT = 15


# ============ ニュース ============
@dataclass
class NewsItem:
    title: str
    source: str
    date: str
    url: str


def fetch_news(query: str = "コンサドーレ札幌", limit: int = 10) -> list[NewsItem]:
    """Google News RSSから最新ニュースを取得する。"""
    url = (
        "https://news.google.com/rss/search?"
        f"q={quote(query)}&hl=ja&gl=JP&ceid=JP:ja"
    )
    feed = feedparser.parse(url)
    items: list[NewsItem] = []
    for e in feed.entries[:limit]:
        # タイトル末尾の「 - 媒体名」を分離
        title = e.get("title", "")
        source = ""
        m = re.match(r"^(.*)\s-\s([^-]+)$", title)
        if m:
            title, source = m.group(1).strip(), m.group(2).strip()
        if not source:
            source = getattr(getattr(e, "source", None), "title", "") or "ニュース"
        # 日付を「7月4日」形式に
        date = ""
        if getattr(e, "published_parsed", None):
            t = e.published_parsed
            date = f"{t.tm_mon}月{t.tm_mday}日"
        items.append(NewsItem(title=title, source=source, date=date, url=e.get("link", "")))
    return items


# ============ 日程・結果 ============
@dataclass
class Match:
    date: str       # 例: 8月8日(土)
    kickoff: str    # 例: 14:45 / 未定
    comp: str       # 例: J2第1節 / 天皇杯2回戦
    opponent: str
    home_away: str  # H / A
    venue: str
    result: str     # 例: ○2-1 / 予定

# 2026-07-04時点の確定日程(スクレイピング失敗時のフォールバック)
SNAPSHOT_SCHEDULE: list[Match] = [
    Match("7月25日(土)", "15:00", "プレシーズンマッチ", "名古屋", "H", "宮の沢白い恋人サッカー場", "予定"),
    Match("8月8日(土)", "14:45", "J2 第1節", "徳島", "H", "大和ハウス プレミストドーム", "予定"),
    Match("8月15/16日", "未定", "J2 第2節", "新潟", "A", "未定", "予定"),
    Match("8月22/23日", "未定", "J2 第3節", "大宮", "H", "未定", "予定"),
    Match("8月26日(水)", "19:00", "天皇杯 2回戦", "甲府", "H", "大和ハウス プレミストドーム", "予定"),
    Match("8月29日(土)", "未定", "J2 第4節", "甲府", "A", "未定", "予定"),
]
SNAPSHOT_DATE = "2026年7月4日"


def fetch_schedule() -> tuple[list[Match], bool]:
    """クラブ公式サイトから日程・結果の取得を試みる。

    Returns:
        (試合リスト, ライブ取得に成功したかどうか)
    """
    try:
        res = requests.get(
            "https://www.consadole-sapporo.jp/game/gamelist/",
            headers=UA, timeout=TIMEOUT,
        )
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        matches = _parse_official_gamelist(soup)
        if matches:
            return matches, True
    except Exception:
        pass
    return SNAPSHOT_SCHEDULE, False


def _parse_official_gamelist(soup: BeautifulSoup) -> list[Match]:
    """公式サイトの試合一覧を解析する。

    サイト構造は変わることがあるため、複数のパターンを試し、
    読み取れた分だけ返す(全滅ならフォールバックが使われる)。
    """
    matches: list[Match] = []

    # パターン1: テーブル形式
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
            row = " ".join(cells)
            m = re.search(r"(\d{1,2})[./月](\d{1,2})", row)
            if not m:
                continue
            date = f"{int(m.group(1))}月{int(m.group(2))}日"
            score = re.search(r"(\d+)\s*[-−]\s*(\d+)", row)
            ko = re.search(r"(\d{1,2}:\d{2})", row)
            opp = _find_opponent(row)
            if not opp:
                continue
            matches.append(Match(
                date=date,
                kickoff=ko.group(1) if ko else "未定",
                comp=_find_comp(row),
                opponent=opp,
                home_away="H" if ("ドーム" in row or "厚別" in row or "宮の沢" in row) else "A",
                venue=_find_venue(row),
                result=f"{score.group(1)}-{score.group(2)}" if score else "予定",
            ))
    return matches


_OPPONENTS = [
    "徳島", "新潟", "大宮", "甲府", "名古屋", "仙台", "秋田", "山形", "いわき",
    "栃木C", "横浜FC", "湘南", "富山", "磐田", "藤枝", "今治", "鳥栖", "大分",
    "宮崎", "八戸",
]


def _find_opponent(text: str) -> str:
    for o in _OPPONENTS:
        if o in text:
            return o
    return ""


def _find_comp(text: str) -> str:
    if "天皇杯" in text:
        return "天皇杯"
    if "ルヴァン" in text:
        return "ルヴァンカップ"
    m = re.search(r"第\s*(\d+)\s*節", text)
    if m:
        return f"J2 第{m.group(1)}節"
    return "試合"


def _find_venue(text: str) -> str:
    for v in ["大和ハウス プレミストドーム", "プレミストドーム", "札幌厚別公園競技場",
              "宮の沢白い恋人サッカー場"]:
        if v in text:
            return v
    return "-"


if __name__ == "__main__":
    # 動作確認用: python fetchers.py
    print("--- ニュース ---")
    for n in fetch_news(limit=5):
        print(f"[{n.source}] {n.date} {n.title}")
    print("--- 日程 ---")
    sched, live = fetch_schedule()
    print(f"ライブ取得: {live}")
    for m in sched:
        print(f"{m.date} {m.kickoff} vs {m.opponent} ({m.home_away}) {m.result}")

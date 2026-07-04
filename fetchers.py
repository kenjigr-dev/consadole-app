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


# ============ 選手一覧 ============
@dataclass
class Player:
    number: str
    name: str
    position: str  # GK/DF/MF/FW

# 2026-07-04時点の登録選手(ゲキサカ掲載、取得失敗時のフォールバック)
SNAPSHOT_PLAYERS: list[Player] = [
    Player("1", "菅野孝憲", "GK"), Player("24", "田川知樹", "GK"),
    Player("41", "唯野鶴眞", "GK"), Player("51", "高木駿", "GK"),
    Player("2", "高尾瑠", "DF"), Player("3", "パク・ミンギュ", "DF"),
    Player("4", "中村桐耶", "DF"), Player("5", "福森晃斗", "DF"),
    Player("15", "家泉怜依", "DF"), Player("17", "内田瑞己", "DF"),
    Player("25", "大崎玲央", "DF"), Player("28", "岡田大和", "DF"),
    Player("31", "堀米悠斗", "DF"), Player("39", "川原颯斗", "DF"),
    Player("47", "西野奨太", "DF"), Player("50", "浦上仁騎", "DF"),
    Player("7", "スパチョーク", "MF"), Player("10", "宮澤裕樹", "MF"),
    Player("11", "青木亮太", "MF"), Player("13", "堀米勇輝", "MF"),
    Player("14", "田中克幸", "MF"), Player("16", "長谷川竜也", "MF"),
    Player("18", "木戸柊摩", "MF"), Player("27", "荒野拓馬", "MF"),
    Player("30", "田中宏武", "MF"), Player("35", "原康介", "MF"),
    Player("40", "佐藤陽成", "MF"), Player("70", "フランシス・カン", "MF"),
    Player("9", "マリオ・セルジオ", "FW"), Player("9", "ジョルディ・サンチェス", "FW"),
    Player("19", "ティラパット", "FW"), Player("20", "アマドゥ・バカヨコ", "FW"),
    Player("22", "キングロード・サフォ", "FW"), Player("23", "大森真吾", "FW"),
    Player("71", "白井陽斗", "FW"),
]


def fetch_players() -> tuple[list[Player], bool]:
    """ゲキサカの選手一覧を取得する。失敗時はスナップショットを返す。"""
    try:
        res = requests.get(
            "https://web.gekisaka.jp/club/player?club_id=561",
            headers=UA, timeout=TIMEOUT,
        )
        res.raise_for_status()
        players = _parse_gekisaka_players(res.text)
        if len(players) >= 15:  # 妥当な人数が取れた時だけライブ扱い
            return players, True
    except Exception:
        pass
    return SNAPSHOT_PLAYERS, False


def _parse_gekisaka_players(html: str) -> list[Player]:
    """「▼GK」等の見出しと「番号+名前」の並びを解析する。

    番号と名前が同じ行でも別々の行でも読めるようにする。
    """
    text = BeautifulSoup(html, "html.parser").get_text("\n")
    players: list[Player] = []
    pos = ""
    pending_num = ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^[▼■]\s*(GK|DF|MF|FW)", line)
        if m:
            pos = m.group(1)
            pending_num = ""
            continue
        if not pos:
            continue
        # 「1菅野孝憲」形式(同一行)
        pm = re.match(r"^(\d{1,2})\s*([^\d].+)$", line)
        if pm and 1 < len(pm.group(2)) < 20:
            players.append(Player(pm.group(1), pm.group(2).strip(), pos))
            pending_num = ""
            continue
        # 「1」→次行「菅野孝憲」形式(別行)
        if re.fullmatch(r"\d{1,2}", line):
            pending_num = line
            continue
        if pending_num and 1 < len(line) < 20 and not line.startswith(("http", "▼")):
            players.append(Player(pending_num, line, pos))
            pending_num = ""
    return players


# ============ J2順位表 ============
J2_CLUBS_2627 = [
    "札幌", "仙台", "秋田", "山形", "いわき", "水戸", "大宮", "千葉", "甲府",
    "長野", "松本", "金沢", "沼津", "磐田", "藤枝", "岐阜", "奈良", "愛媛",
    "徳島", "新潟",
]


@dataclass
class StandingRow:
    rank: str
    club: str
    pts: str
    played: str
    win: str
    draw: str
    lose: str
    gf: str
    ga: str
    gd: str


def fetch_standings() -> tuple[list[StandingRow], bool]:
    """スポーツナビのJ2順位表を取得する。

    開幕前やサイト構造変更で読み取れない場合は ([], False) を返す。
    """
    try:
        res = requests.get(
            "https://soccer.yahoo.co.jp/jleague/category/j2/standings",
            headers=UA, timeout=TIMEOUT,
        )
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        rows: list[StandingRow] = []
        for tr in soup.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
            if len(cells) < 8:
                continue
            club = next((c for c in cells if any(k in c for k in J2_CLUBS_2627)), "")
            nums = [c for c in cells if re.fullmatch(r"-?\d+", c)]
            if not club or len(nums) < 7:
                continue
            rows.append(StandingRow(
                rank=nums[0], club=club, pts=nums[1], played=nums[2],
                win=nums[3], draw=nums[4], lose=nums[5],
                gf=nums[6], ga=nums[7] if len(nums) > 7 else "-",
                gd=nums[8] if len(nums) > 8 else "-",
            ))
        if len(rows) >= 10:
            return rows, True
    except Exception:
        pass
    return [], False

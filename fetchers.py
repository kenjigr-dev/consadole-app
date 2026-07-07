"""コンサ情報ボード: データ取得モジュール

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

UA = {
    "User-Agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                   "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"),
    "Accept-Language": "ja,en;q=0.8",
}
TIMEOUT = 15


# ============ ニュース ============
@dataclass
class NewsItem:
    title: str
    source: str
    date: str
    url: str


def fetch_news(query: str = "コンサドーレ札幌", limit: int = 10) -> list[NewsItem]:
    """Google News RSSから最新ニュースを取得する(新しい順にソート)。"""
    import calendar
    from datetime import datetime, timezone, timedelta
    JST = timezone(timedelta(hours=9))
    url = (
        "https://news.google.com/rss/search?"
        f"q={quote(query)}&hl=ja&gl=JP&ceid=JP:ja"
    )
    feed = feedparser.parse(url)
    # 公開日時の新しい順に並べ替え(RSSの並びは必ずしも新着順ではない)
    entries = sorted(
        feed.entries,
        key=lambda e: e.get("published_parsed") or (0,) * 9,
        reverse=True,
    )
    items: list[NewsItem] = []
    for e in entries[:limit]:
        # タイトル末尾の「 - 媒体名」を分離
        title = e.get("title", "")
        source = ""
        m = re.match(r"^(.*)\s-\s([^-]+)$", title)
        if m:
            title, source = m.group(1).strip(), m.group(2).strip()
        if not source:
            source = getattr(getattr(e, "source", None), "title", "") or "ニュース"
        # UTCの公開日時を日本時間に変換して「7月5日 18:30」形式に
        date = ""
        if getattr(e, "published_parsed", None):
            ts = calendar.timegm(e.published_parsed)
            jt = datetime.fromtimestamp(ts, tz=JST)
            date = f"{jt.month}月{jt.day}日 {jt:%H:%M}"
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

def fetch_season_results(url: str) -> list[tuple]:
    """スポーツナビの札幌 日程・結果ページから、消化済み試合を
    (日付, 対戦相手, H/A, スコア, 結果) 形式で返す。未消化の試合は含まない。"""
    try:
        res = requests.get(url, headers=UA, timeout=TIMEOUT)
        res.raise_for_status()
    except Exception:
        return []
    soup = BeautifulSoup(res.text, "html.parser")
    results: list[tuple] = []
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 6:
                continue
            date_cell = cells[0].get_text(" ", strip=True)
            mark = cells[2].get_text(strip=True)
            home_a, away_a = cells[3].find("a"), cells[5].find("a")
            score_cell = cells[4].get_text(" ", strip=True)
            if not (home_a and away_a) or "試合終了" not in score_cell:
                continue
            home_name, away_name = home_a.get_text(strip=True), away_a.get_text(strip=True)
            m_date = re.search(r"(\d{1,2})/(\d{1,2})", date_cell)
            nums = re.findall(r"\d+", score_cell.split("試合終了")[0])
            if not m_date or len(nums) < 2:
                continue
            date_str = f"{int(m_date.group(1)):02d}.{int(m_date.group(2)):02d}"
            h_score, a_score = int(nums[0]), int(nums[1])
            is_pk = "PK" in score_cell
            if home_name == "札幌":
                opp, ha, sp, op = away_name, "H", h_score, a_score
            elif away_name == "札幌":
                opp, ha, sp, op = home_name, "A", a_score, h_score
            else:
                continue
            win = mark == "○"
            if is_pk:
                score_str, result = f"{sp}-{op} PK{'○' if win else '●'}", ("PK勝" if win else "PK負")
            else:
                score_str, result = f"{sp}-{op}", ("勝" if win else "負")
            results.append((date_str, opp, ha, score_str, result))
    return results

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
    url: str = ""  # ゲキサカ選手ページ

# 2026-07-04時点の登録選手(ゲキサカ掲載、取得失敗時のフォールバック)
SNAPSHOT_PLAYERS: list[Player] = [
    Player("1", "菅野孝憲", "GK"), Player("24", "田川知樹", "GK"),
    Player("41", "唯野鶴眞", "GK"), Player("51", "高木駿", "GK"),
    Player("2", "高尾瑠", "DF"), Player("3", "パク・ミンギュ", "DF"),
    Player("4", "中村桐耶", "DF"), Player("5", "福森晃斗", "DF"), Player("17", "内田瑞己", "DF"),
    Player("25", "大崎玲央", "DF"), Player("28", "岡田大和", "DF"),
    Player("31", "堀米悠斗", "DF"), Player("39", "川原颯斗", "DF"),
    Player("47", "西野奨太", "DF"), Player("50", "浦上仁騎", "DF"),
    Player("7", "スパチョーク", "MF"), Player("10", "宮澤裕樹", "MF"),
    Player("11", "青木亮太", "MF"), Player("13", "堀米勇輝", "MF"),
    Player("14", "田中克幸", "MF"), Player("16", "長谷川竜也", "MF"),
    Player("18", "木戸柊摩", "MF"), Player("27", "荒野拓馬", "MF"),
    Player("30", "田中宏武", "MF"), Player("35", "原康介", "MF"),
    Player("40", "佐藤陽成", "MF"),
    Player("9", "マリオ・セルジオ", "FW"),
    Player("19", "ティラパット", "FW"), Player("20", "アマドゥ・バカヨコ", "FW"),
    Player("22", "キングロード・サフォ", "FW"), Player("23", "大森真吾", "FW"),
    Player("71", "白井陽斗", "FW"),
]


# 退団・移籍が確定した選手(データ源の更新が遅れても表示しない)
DEPARTED_PLAYERS = {"家泉怜依", "フランシス・カン", "ジョルディ・サンチェス"}


def _exclude_departed(players: list[Player]) -> list[Player]:
    return [p for p in players if p.name not in DEPARTED_PLAYERS]


def fetch_players() -> tuple[list[Player], bool]:
    """ゲキサカの選手一覧を取得する。失敗時はスナップショットを返す。"""
    try:
        res = requests.get(
            "https://web.gekisaka.jp/club/detail?club_id=561",
            headers=UA, timeout=TIMEOUT,
        )
        res.raise_for_status()
        players = _parse_gekisaka_players(res.text)
        if len(players) >= 15:  # 妥当な人数が取れた時だけライブ扱い
            return _exclude_departed(players), True
    except Exception:
        pass
    return _exclude_departed(SNAPSHOT_PLAYERS), False


def _parse_gekisaka_players(html: str) -> list[Player]:
    """選手一覧を解析する。リンク付きHTML構造を優先し、失敗時はテキスト解析。"""
    soup = BeautifulSoup(html, "html.parser")

    # パターンA: <a href="/player/?...">名前</a> を順に辿り、直前の数字と▼見出しを対応付け
    players: list[Player] = []
    pos, pending_num = "", ""
    for node in soup.descendants:
        if isinstance(node, str):
            for t in node.splitlines():
                t = t.strip()
                m = re.match(r"^[▼■]\s*(GK|DF|MF|FW)", t)
                if m:
                    pos = m.group(1)
                    pending_num = ""
                elif re.fullmatch(r"\d{1,2}", t):
                    pending_num = t
        elif getattr(node, "name", "") == "a" and "/player/" in (node.get("href") or ""):
            name = node.get_text(strip=True)
            if pos and pending_num and 1 < len(name) < 20:
                href = node["href"]
                if href.startswith("/"):
                    href = "https://web.gekisaka.jp" + href
                players.append(Player(pending_num, name, pos, href))
                pending_num = ""
    if len(players) >= 15:
        return players

    # パターンB: テキストのみ(リンク構造が変わった場合の保険)
    text = soup.get_text("\n")
    players, pos, pending_num = [], "", ""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^[▼■]\s*(GK|DF|MF|FW)", line)
        if m:
            pos, pending_num = m.group(1), ""
            continue
        if not pos:
            continue
        pm = re.match(r"^(\d{1,2})\s*([^\d].+)$", line)
        if pm and 1 < len(pm.group(2)) < 20:
            players.append(Player(pm.group(1), pm.group(2).strip(), pos))
            pending_num = ""
            continue
        if re.fullmatch(r"\d{1,2}", line):
            pending_num = line
            continue
        if pending_num and 1 < len(line) < 20 and not line.startswith(("http", "▼")):
            players.append(Player(pending_num, line, pos))
            pending_num = ""
    return players


def fetch_player_detail(url: str) -> dict:
    """ゲキサカの選手個人ページからプロフィール・経歴・関連ニュースを取得する。"""
    headers = {
        "User-Agent": ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                       "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"),
        "Referer": "https://web.gekisaka.jp/club/detail?club_id=561",
        "Accept-Language": "ja,en;q=0.8",
    }
    res = requests.get(url, headers=headers, timeout=TIMEOUT)
    res.raise_for_status()
    text = BeautifulSoup(res.text, "html.parser").get_text("\n")
    d: dict = {"news": []}

    m = re.search(r"■所属\s*[:：]\s*(.+)", text)
    if m:
        d["club"] = m.group(1).strip()
    m = re.search(r"■背番号\s*[:：]\s*(\S+)", text)
    if m:
        d["number"] = m.group(1).strip()
    m = re.search(r"■ポジション\s*[:：]\s*(\S+)", text)
    if m:
        d["position"] = m.group(1).strip()
    m = re.search(r"■\s*(\d{4}-\d{2}-\d{2})", text)
    if m:
        d["birth"] = m.group(1)
    m = re.search(r"■\s*(\d{2,3}cm/\d{2,3}kg)", text)
    if m:
        d["body"] = m.group(1)
    m = re.search(r"経歴\s*=\s*([^\n■]+)", text)
    if m:
        d["career"] = m.group(1).strip()
    m = re.search(r"Jリーグ受賞歴\s*=?\s*([^\n■]+)", text)
    if m:
        d["awards"] = m.group(1).strip()
    m = re.search(r"■代表歴\s*[:：]?\s*\n?\s*([^\n■]+)", text)
    if m:
        d["natl"] = m.group(1).strip()

    # 関連ニュース: 「見出し 20xx-xx-xx」形式の行
    for line in text.splitlines():
        nm = re.match(r"^(.{8,60}?)\s+(20\d{2}-\d{2}-\d{2})$", line.strip())
        if nm and len(d["news"]) < 5:
            d["news"].append({"title": nm.group(1).strip(), "date": nm.group(2)})
    return d


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


def fetch_player_wiki(name: str) -> dict:
    """Wikipediaの要約API(構造が安定)から選手の人物紹介を取得する。"""
    from urllib.parse import quote
    res = requests.get(
        f"https://ja.wikipedia.org/api/rest_v1/page/summary/{quote(name)}",
        headers=UA, timeout=TIMEOUT,
    )
    res.raise_for_status()
    data = res.json()
    extract = data.get("extract", "")
    # 同名の別人ページを避ける(サッカー関係の記述があるものだけ採用)
    if "サッカー" not in extract and "フットボール" not in extract:
        return {}
    return {
        "extract": extract,
        "wiki_url": data.get("content_urls", {}).get("mobile", {}).get("page", ""),
    }

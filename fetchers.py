"""コンサ情報ボード: データ取得モジュール

- ニュース: Google News RSS (安定・キー不要)
- 日程・結果: クラブ公式サイトのスクレイピング(失敗時はスナップショットに自動フォールバック)
- 選手一覧・詳細: スポーツナビ(日程・順位表と同じサイトに統一)
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
    entries = sorted(
        feed.entries,
        key=lambda e: e.get("published_parsed") or (0,) * 9,
        reverse=True,
    )
    items: list[NewsItem] = []
    for e in entries[:limit]:
        title = e.get("title", "")
        source = ""
        m = re.match(r"^(.*)\s-\s([^-]+)$", title)
        if m:
            title, source = m.group(1).strip(), m.group(2).strip()
        if not source:
            source = getattr(getattr(e, "source", None), "title", "") or "ニュース"
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
    date: str
    kickoff: str
    comp: str
    opponent: str
    home_away: str
    venue: str
    result: str

SNAPSHOT_SCHEDULE: list[Match] = [
    Match("8月15日(土)", "19:00", "J2 第2節", "新潟", "A", "デンカＳビッグスワンスタジアム", "予定"),
    Match("8月22日(土)", "15:00", "J2 第3節", "大宮", "H", "大和ハウス プレミストドーム", "予定"),
    Match("8月26日(水)", "19:00", "天皇杯 2回戦", "甲府", "H", "大和ハウス プレミストドーム", "予定"),
    Match("8月29日(土)", "19:00", "J2 第4節", "甲府", "A", "ＪＩＴリサイクルインクスタジアム", "予定"),
    Match("9月6日(日)", "13:00", "J2 第5節", "栃木C", "H", "札幌厚別公園競技場", "予定"),
]
SNAPSHOT_DATE = "2026年8月12日(8/8 徳島戦: 札幌 2-0 勝利)"


def _fetch_official_page_text() -> str | None:
    try:
        res = requests.get(
            "https://www.consadole-sapporo.jp/game/list/",
            headers=UA, timeout=TIMEOUT,
        )
        res.raise_for_status()
    except Exception:
        return None
    soup = BeautifulSoup(res.text, "html.parser")
    return soup.get_text(" ", strip=True)


def fetch_schedule() -> tuple[list[Match], bool]:
    text = _fetch_official_page_text()
    if text:
        matches, _ = _parse_official_gamelist(text)
        if matches:
            return matches, True
    return SNAPSHOT_SCHEDULE, False


_OPPONENTS = [
    "横浜FC", "栃木C",  # 長い表記を先に(部分一致の優先順位)
    "徳島", "新潟", "大宮", "甲府", "名古屋", "仙台", "秋田", "山形", "いわき",
    "湘南", "富山", "磐田", "藤枝", "今治", "鳥栖", "大分", "宮崎", "八戸",
]
_ALL_TEAMS = _OPPONENTS + ["札幌"]
_TEAM_ALT = "|".join(re.escape(t) for t in sorted(_ALL_TEAMS, key=len, reverse=True))
_MATCH_RE = re.compile(
    rf"(?P<pre>.{{0,70}}?)(?P<t1>{_TEAM_ALT})\s*home\s*(?P=t1)\s*"
    rf"(?P<score>\d+\s*-\s*\d+|-)\s*(?P<t2>{_TEAM_ALT})\s*away\s*(?P=t2)"
)


def _parse_official_gamelist(text: str) -> tuple[list[Match], list[tuple]]:
    """公式サイト試合日程ページ(divカードレイアウト、<table>なし)を
    home/awayラベルを手がかりにテキストから解析する。
    戻り値: (Matchのリスト, 消化済み試合の (日付,対戦相手,H/A,スコア,結果) リスト)"""
    schedule: list[Match] = []
    results: list[tuple] = []
    for m in _MATCH_RE.finditer(text):
        pre, t1, t2, score = m.group("pre"), m.group("t1"), m.group("t2"), m.group("score")
        date_m = re.search(r"(\d{1,2})\.(\d{1,2})", pre)
        time_m = re.search(r"(\d{1,2}:\d{2})", pre)
        round_m = re.search(r"第\s*(\d+)\s*節", pre)
        if "天皇杯" in pre:
            comp = "天皇杯" + (re.search(r"(\d+回戦)", pre).group(1) if re.search(r"(\d+回戦)", pre) else "")
        elif "ルヴァン" in pre:
            comp = "ルヴァンカップ"
        elif round_m:
            comp = f"J2 第{round_m.group(1)}節"
        else:
            comp = "試合"
        if t1 != "札幌" and t2 != "札幌":
            continue  # 札幌戦以外(誤マッチ)は除外
        opp = t2 if t1 == "札幌" else t1
        ha = "H" if t1 == "札幌" else "A"
        date_str = f"{int(date_m.group(1))}月{int(date_m.group(2))}日" if date_m else "未定"
        score_clean = re.sub(r"\s+", "", score)
        schedule.append(Match(
            date=date_str, kickoff=time_m.group(1) if time_m else "未定",
            comp=comp, opponent=opp, home_away=ha,
            venue=_find_venue(pre), result=score_clean if score_clean != "-" else "予定",
        ))
        if score_clean != "-" and date_m:
            h, a = (int(x) for x in score_clean.split("-"))
            sp, op = (h, a) if t1 == "札幌" else (a, h)
            label = "勝" if sp > op else ("分" if sp == op else "負")
            date_key = f"{int(date_m.group(1)):02d}.{int(date_m.group(2)):02d}"
            results.append((date_key, opp, ha, f"{sp}-{op}", label))
    return schedule, results


def fetch_official_results() -> tuple[list[tuple], str]:
    """公式サイトから消化済み試合結果を取得。戻り値は(結果リスト, 診断メッセージ)。"""
    text = _fetch_official_page_text()
    if not text:
        return [], "公式サイトのHTTP取得に失敗"
    _, results = _parse_official_gamelist(text)
    if not results:
        return [], f"公式サイトは取得できたが試合データを抽出できず(HTML長:{len(text)})"
    return results, f"OK(公式サイト): {len(results)}試合取得"


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


# J2昇格/降格でカテゴリが変わるため、シーズンによって要更新
SEASON_RESULTS_URL = "https://soccer.yahoo.co.jp/jleague/category/j2/teams/276/schedule?gk=6"


def fetch_season_results(url: str = SEASON_RESULTS_URL) -> tuple[list[tuple], str]:
    """スポーツナビの札幌 日程・結果ページから、消化済み試合を
    (日付, 対戦相手, H/A, スコア, 結果) 形式で返す。未消化の試合は含まない。
    戻り値は (結果リスト, 診断メッセージ)。"""
    try:
        res = requests.get(url, headers=UA, timeout=TIMEOUT)
        res.raise_for_status()
    except Exception as e:
        return [], f"HTTP取得失敗: {type(e).__name__}: {e}"
    soup = BeautifulSoup(res.text, "html.parser")
    results: list[tuple] = []
    tables_found = len(soup.find_all("table"))
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
    if not results:
        return [], f"取得は成功したが試合データを0件しか抽出できず(table数:{tables_found}, HTML長:{len(res.text)})"
    return results, f"OK: {len(results)}試合取得"


if __name__ == "__main__":
    print("--- ニュース ---")
    for n in fetch_news(limit=5):
        print(f"[{n.source}] {n.date} {n.title}")
    print("--- 日程 ---")
    sched, live = fetch_schedule()
    print(f"ライブ取得: {live}")
    for m in sched:
        print(f"{m.date} {m.kickoff} vs {m.opponent} ({m.home_away}) {m.result}")


# ============ 選手一覧・詳細(スポーツナビ) ============
@dataclass
class Player:
    number: str
    name: str
    position: str  # GK/DF/MF/FW
    url: str = ""  # スポーツナビ選手ページ

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

DEPARTED_PLAYERS = {"家泉怜依", "フランシス・カン", "ジョルディ・サンチェス"}


def _exclude_departed(players: list[Player]) -> list[Player]:
    return [p for p in players if p.name not in DEPARTED_PLAYERS]


def fetch_players() -> tuple[list[Player], bool]:
    """スポーツナビの選手一覧を取得する。失敗時はスナップショットを返す。"""
    try:
        res = requests.get(
            "https://soccer.yahoo.co.jp/jleague/category/j2/teams/276/players",
            headers=UA, timeout=TIMEOUT,
        )
        res.raise_for_status()
        soup = BeautifulSoup(res.text, "html.parser")
        players: list[Player] = []
        for table in soup.find_all("table"):
            for tr in table.find_all("tr"):
                cells = tr.find_all("td")
                if len(cells) < 3:
                    continue
                pos = cells[0].get_text(strip=True)
                if pos not in ("GK", "DF", "MF", "FW"):
                    continue  # 監督などスタッフ行は除外
                number = cells[1].get_text(strip=True)
                a = cells[2].find("a")
                if not a:
                    continue
                name = a.get_text(strip=True)
                href = a.get("href", "")
                p_url = href if href.startswith("http") else "https://soccer.yahoo.co.jp" + href
                players.append(Player(number, name, pos, p_url))
        if len(players) >= 15:
            return _exclude_departed(players), True
    except Exception:
        pass
    return _exclude_departed(SNAPSHOT_PLAYERS), False


def fetch_player_detail(url: str) -> dict:
    """スポーツナビの選手個別ページからプロフィール・経歴を取得する。"""
    res = requests.get(url, headers=UA, timeout=TIMEOUT)
    res.raise_for_status()
    text = BeautifulSoup(res.text, "html.parser").get_text("\n")
    d: dict = {"news": []}
    m = re.search(r"生年月日[^\d]*(\d{4})年(\d{1,2})月(\d{1,2})日", text)
    if m:
        y, mo, da = int(m.group(1)), int(m.group(2)), int(m.group(3))
        d["birth"] = f"{y}-{mo:02d}-{da:02d}"
    h = re.search(r"身長[^\d]*(\d{2,3})cm", text)
    w = re.search(r"体重[^\d]*(\d{2,3})kg", text)
    if h and w:
        d["body"] = f"{h.group(1)}cm/{w.group(1)}kg"
    m = re.search(r"過去の所属\s*\n*\s*([^\n]+)", text)
    if m:
        d["career"] = m.group(1).strip()
    m = re.search(r"個人タイトル\s*\n*\s*([^\n]+)", text)
    if m:
        d["awards"] = m.group(1).strip()
    return d


def fetch_player_wiki(name: str) -> dict:
    """Wikipediaの要約API(構造が安定)から選手の人物紹介を取得する。予備ルートとして維持。"""
    res = requests.get(
        f"https://ja.wikipedia.org/api/rest_v1/page/summary/{quote(name)}",
        headers=UA, timeout=TIMEOUT,
    )
    res.raise_for_status()
    data = res.json()
    extract = data.get("extract", "")
    if "サッカー" not in extract and "フットボール" not in extract:
        return {}
    return {
        "extract": extract,
        "wiki_url": data.get("content_urls", {}).get("mobile", {}).get("page", ""),
    }


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

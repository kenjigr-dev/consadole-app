"""コンサドーレ情報ボード — マッチデー中心設計・iPhone最適化"""
import re
from datetime import date, datetime

import pandas as pd
import streamlit as st

from fetchers import (SNAPSHOT_DATE, fetch_news, fetch_players,
                      fetch_schedule, fetch_standings)

# ============ 静的データ(2026-07-04時点) ============
SEASON_SP = [
    ("02.08", "いわき", "A", "0-1", "負"), ("02.14", "大宮", "A", "2-3", "負"),
    ("02.21", "長野", "A", "1-1 PK○", "PK勝"), ("02.28", "岐阜", "H", "1-2", "負"),
    ("03.07", "松本", "A", "0-3", "負"), ("03.14", "磐田", "A", "1-0", "勝"),
    ("03.21", "甲府", "H", "1-0", "勝"), ("03.28", "藤枝", "A", "1-1 PK○", "PK勝"),
    ("04.04", "福島", "H", "0-2", "負"), ("04.11", "甲府", "A", "1-2", "負"),
    ("04.18", "松本", "H", "2-1", "勝"), ("04.25", "いわき", "H", "2-1", "勝"),
    ("04.29", "藤枝", "H", "2-1", "勝"), ("05.02", "岐阜", "A", "3-0", "勝"),
    ("05.06", "長野", "H", "2-0", "勝"), ("05.09", "大宮", "H", "4-3", "勝"),
    ("05.16", "福島", "A", "3-0", "勝"), ("05.23", "磐田", "H", "0-1", "負"),
    ("05.31", "秋田", "A", "1-1 PK●", "PK負"), ("06.06", "新潟", "A", "0-0 PK●", "PK負"),
]
HISTORY = [
    (2025, "J2", 12), (2024, "J1", 19), (2023, "J1", 12), (2022, "J1", 10),
    (2021, "J1", 10), (2020, "J1", 12), (2019, "J1", 10), (2018, "J1", 4),
    (2017, "J1", 11), (2016, "J2", 1), (2015, "J2", 10), (2014, "J2", 10),
]
KICKOFF_DATE = date(2026, 8, 8)
RED, BLACK, GRAY, PINK = "#C8102E", "#17181B", "#7a7f88", "#E8899A"
PTS = {"勝": 3, "PK勝": 2, "PK負": 1, "負": 0}
RESULT_DOT = {"勝": ("○", RED), "PK勝": ("○", PINK), "PK負": ("●", "#B9BDC4"), "負": ("●", BLACK)}

st.set_page_config(page_title="コンサドーレ情報ボード", page_icon="⚽", layout="centered")

st.markdown("""
<style>
.block-container {padding: 0.5rem 0.85rem 3rem !important; max-width: 640px;}
header[data-testid="stHeader"] {height: 0;}
button[data-baseweb="tab"] {font-size: 14px !important; font-weight: 800 !important;
  padding: 8px 9px !important;}
button[data-baseweb="tab"][aria-selected="true"] {color: #C8102E !important;}
div[data-baseweb="tab-highlight"] {background-color: #C8102E !important;}
[data-testid="stDataFrame"] {font-size: 13px;}
h3 {font-size: 1.02rem !important; border-left: 4px solid #C8102E;
  padding-left: 9px; margin: 0.5rem 0 0.4rem !important;}
</style>
""", unsafe_allow_html=True)


# ============ 部品 ============
def card(html, pad="12px 14px", mb="10px"):
    return (f'<div style="background:#fff;border-radius:12px;padding:{pad};'
            f'margin-bottom:{mb};box-shadow:0 1px 3px rgba(23,24,27,.08)">{html}</div>')


def stat_grid(pairs, accent_first=True):
    cells = ""
    for i, (label, value) in enumerate(pairs):
        color = RED if (accent_first and i == 0) else BLACK
        cells += (f'<div style="flex:1;text-align:center;padding:6px 2px">'
                  f'<div style="font-size:25px;font-weight:900;color:{color};line-height:1.1">{value}</div>'
                  f'<div style="font-size:10.5px;color:{GRAY};font-weight:700;margin-top:2px">{label}</div></div>')
    return (f'<div style="display:flex;background:#fff;border-radius:12px;'
            f'padding:7px 4px;box-shadow:0 1px 3px rgba(23,24,27,.08);margin-bottom:10px">{cells}</div>')


def form_dots(results, size=15):
    """直近試合のフォームを●○で表示(左が古い、右が最新)"""
    dots = ""
    for r in results:
        ch, color = RESULT_DOT[r]
        dots += f'<span style="color:{color};font-size:{size}px;font-weight:900;margin:0 2px">{ch}</span>'
    return dots


def parse_jp_date(s, base_year=2026):
    """「7月25日(土)」等をdateに変換。読めなければNone。"""
    m = re.search(r"(\d{1,2})月(\d{1,2})", s)
    if not m:
        return None
    mo, d = int(m.group(1)), int(m.group(2))
    year = base_year + 1 if mo <= 6 else base_year  # 秋春制: 1〜6月は翌年
    try:
        return date(year, mo, d)
    except ValueError:
        return None


def section_label(text):
    return (f'<div style="margin:12px 0 6px;font-size:14px;font-weight:900;color:{BLACK};'
            f'border-left:4px solid {RED};padding-left:9px">{text}</div>')


# ============ ヘッダー ============
stripe = "".join(f'<span style="display:inline-block;width:4.16%;height:8px;'
                 f'background:{RED if i % 2 else BLACK}"></span>' for i in range(24))
st.markdown(
    f'<div style="font-size:0;line-height:0">{stripe}</div>'
    f'<div style="background:{BLACK};padding:10px 14px;border-radius:0 0 12px 12px;margin-bottom:8px;'
    f'display:flex;justify-content:space-between;align-items:center">'
    f'<div><div style="color:{RED};font-size:9px;letter-spacing:.2em;font-weight:800">'
    f'HOKKAIDO CONSADOLE SAPPORO</div>'
    f'<div style="color:#fff;font-size:18px;font-weight:900">コンサドーレ情報ボード</div></div>'
    f'<div style="text-align:right;color:#B9BDC4;font-size:10px">{date.today():%-m/%-d}<br>'
    f'<span style="color:#fff;font-weight:800">2026/27</span></div></div>',
    unsafe_allow_html=True,
)

tabs = st.tabs(["ホーム", "ニュース", "日程", "順位表", "選手", "分析"])


@st.cache_data(ttl=300, show_spinner=False)
def cached_news():
    return fetch_news(limit=10), datetime.now()


@st.cache_data(ttl=300, show_spinner=False)
def cached_schedule():
    s, live = fetch_schedule()
    return s, live, datetime.now()


@st.cache_data(ttl=600, show_spinner=False)
def cached_standings():
    return fetch_standings()


@st.cache_data(ttl=3600, show_spinner=False)
def cached_players():
    return fetch_players()


def get_schedule_safe():
    try:
        return cached_schedule()
    except Exception:
        from fetchers import SNAPSHOT_SCHEDULE
        return SNAPSHOT_SCHEDULE, False, None


# ============ ホーム ============
with tabs[0]:
    sched, s_live, _ = get_schedule_safe()
    today = date.today()

    # --- 次の試合(マッチデーカード) ---
    next_m, next_d = None, None
    for m in sched:
        d = parse_jp_date(m.date)
        if d and d >= today and m.result in ("予定",):
            next_m, next_d = m, d
            break
    if next_m:
        dd = (next_d - today).days
        when = "本日!" if dd == 0 else f"あと{dd}日"
        ha = "ホーム" if next_m.home_away == "H" else "アウェイ"
        st.markdown(
            f'<div style="background:{BLACK};border-radius:14px;padding:14px;color:#fff;'
            f'margin-bottom:10px;position:relative;overflow:hidden">'
            f'<div style="position:absolute;top:0;left:0;right:0;height:4px;background:'
            f'repeating-linear-gradient(90deg,{RED} 0 20px,{BLACK} 20px 40px)"></div>'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-top:3px">'
            f'<span style="color:{PINK};font-size:10px;font-weight:800;letter-spacing:.15em">NEXT MATCH'
            f' <span style="color:#B9BDC4">/ {next_m.comp}</span></span>'
            f'<span style="background:{RED};border-radius:20px;padding:2px 11px;font-size:12px;'
            f'font-weight:900">{when}</span></div>'
            f'<div style="font-size:23px;font-weight:900;margin-top:6px">vs {next_m.opponent}'
            f'<span style="font-size:12px;color:{PINK};font-weight:800;margin-left:8px">{ha}</span></div>'
            f'<div style="font-size:12.5px;color:#B9BDC4;margin-top:3px">'
            f'{next_m.date} {next_m.kickoff} <br>{next_m.venue}</div></div>',
            unsafe_allow_html=True,
        )

    # --- 開幕カウントダウン(コンパクト) ---
    days = (KICKOFF_DATE - today).days
    if days > 0:
        st.markdown(card(
            f'<div style="display:flex;justify-content:space-between;align-items:center">'
            f'<div style="font-size:12.5px;font-weight:700;color:{BLACK}">'
            f'J2リーグ開幕 <span style="color:{GRAY}">8/8(土) 14:45 vs 徳島</span></div>'
            f'<div style="font-weight:900;color:{RED};font-size:16px">あと{days}日</div></div>',
            pad="10px 14px",
        ), unsafe_allow_html=True)

    # --- チーム状態(フォーム+総括) ---
    st.markdown(section_label("チーム状態"), unsafe_allow_html=True)
    last5 = SEASON_SP[-5:]
    w = sum(1 for m in SEASON_SP if m[4] == "勝")
    pw = sum(1 for m in SEASON_SP if m[4] == "PK勝")
    pl = sum(1 for m in SEASON_SP if m[4] == "PK負")
    lo = sum(1 for m in SEASON_SP if m[4] == "負")
    st.markdown(card(
        f'<div style="display:flex;justify-content:space-between;align-items:center">'
        f'<span style="font-size:12px;font-weight:700;color:{GRAY}">直近5試合(特別シーズン)</span>'
        f'<span>{form_dots([m[4] for m in last5])}</span></div>'
        f'<div style="font-size:10.5px;color:{GRAY};margin-top:2px;text-align:right">'
        f'{" → ".join(m[1] for m in last5)}</div>',
        pad="10px 14px", mb="8px",
    ), unsafe_allow_html=True)
    st.markdown(stat_grid([
        ("勝点", w * 3 + pw * 2 + pl), ("勝利", w), ("PK勝", pw), ("PK負", pl), ("敗戦", lo),
    ]), unsafe_allow_html=True)

    # --- 新シーズン情報 ---
    st.markdown(section_label("2026/27シーズン"), unsafe_allow_html=True)
    st.markdown(card(
        f'<table style="width:100%;font-size:12.5px;border-collapse:collapse">'
        f'<tr><td style="color:{RED};font-weight:800;width:60px;padding:4px 0">開幕</td>'
        f'<td>8月8日・9日(秋春制へ移行/全38節・20クラブ)</td></tr>'
        f'<tr><td style="color:{RED};font-weight:800;padding:4px 0">中断</td>'
        f'<td>12月2週頃〜2月3週頃 ウィンターブレーク</td></tr>'
        f'<tr><td style="color:{RED};font-weight:800;padding:4px 0">最終節</td>'
        f'<td>2027年5月22日・23日 → 昇格PO 5月末〜6月上旬</td></tr></table>'
    ), unsafe_allow_html=True)

    st.markdown(section_label("リンク"), unsafe_allow_html=True)
    st.markdown(card(
        f'<div style="font-size:13px;line-height:2.1">'
        f'<a href="https://www.consadole-sapporo.jp/" target="_blank" style="color:{BLACK};font-weight:700">公式サイト →</a><br>'
        f'<a href="https://www.jleague.jp/club/sapporo/" target="_blank" style="color:{BLACK};font-weight:700">Jリーグ公式・札幌ページ →</a><br>'
        f'<a href="https://www.football-lab.jp/sapp" target="_blank" style="color:{BLACK};font-weight:700">Football LAB(データ分析) →</a></div>'
    ), unsafe_allow_html=True)

# ============ ニュース ============
with tabs[1]:
    c1, c2 = st.columns([3, 1])
    c1.markdown("### 最新ニュース")
    if c2.button("更新", key="news_btn", use_container_width=True):
        cached_news.clear()
    try:
        with st.spinner("取得中…"):
            news, at = cached_news()
        st.caption(f"リアルタイム取得 {at:%H:%M}(5分ごと自動更新)")
        for n in news:
            st.markdown(card(
                f'<span style="background:{BLACK};color:#fff;font-size:10px;font-weight:800;'
                f'border-radius:4px;padding:2px 7px">{n.source}</span> '
                f'<span style="color:{GRAY};font-size:11px">{n.date}</span>'
                f'<div style="font-weight:800;font-size:14px;margin-top:5px;line-height:1.55">'
                f'<a href="{n.url}" target="_blank" style="color:{BLACK};text-decoration:none">{n.title}</a></div>'
            ), unsafe_allow_html=True)
    except Exception:
        st.error("ニュースの取得に失敗しました。通信環境を確認して「更新」を押してください。")

# ============ 日程 ============
with tabs[2]:
    c1, c2 = st.columns([3, 1])
    c1.markdown("### 日程・結果")
    if c2.button("更新", key="sched_btn", use_container_width=True):
        cached_schedule.clear()
    sched, live, at = get_schedule_safe()
    st.caption(f"公式サイトからライブ取得({at:%H:%M})" if live
               else f"{SNAPSHOT_DATE}時点の確定日程")
    for m in sched:
        d = parse_jp_date(m.date)
        is_next = (m is (next_m if 'next_m' in dir() else None))
        ha_label = "H" if m.home_away == "H" else "A"
        ha_color = RED if m.home_away == "H" else GRAY
        res_color = RED if m.result != "予定" else "#555"
        st.markdown(card(
            f'<div style="display:flex;align-items:center;gap:10px">'
            f'<div style="min-width:76px"><b style="font-size:13px">{m.date}</b><br>'
            f'<span style="font-size:10px;color:{GRAY}">{m.comp}</span></div>'
            f'<span style="background:{ha_color};color:#fff;font-weight:900;font-size:12px;'
            f'border-radius:6px;padding:3px 8px">{ha_label}</span>'
            f'<div style="flex:1"><b style="font-size:15px">{m.opponent}</b><br>'
            f'<span style="font-size:10.5px;color:{GRAY}">{m.venue}</span></div>'
            f'<div style="text-align:right;font-weight:800;color:{res_color};min-width:52px">'
            f"{m.result}<br><span style='font-size:11px;color:{GRAY};font-weight:400'>{m.kickoff}</span></div></div>",
            pad="10px 12px", mb="8px",
        ), unsafe_allow_html=True)
    st.markdown("[公式サイトで全日程を確認する](https://www.consadole-sapporo.jp/game/)")

# ============ 順位表 ============
with tabs[3]:
    c1, c2 = st.columns([3, 1])
    c1.markdown("### J2順位表")
    if c2.button("更新", key="stand_btn", use_container_width=True):
        cached_standings.clear()
    try:
        with st.spinner("取得中…"):
            rows, live = cached_standings()
    except Exception:
        rows, live = [], False
    if live and rows:
        df = pd.DataFrame([{
            "順位": r.rank, "クラブ": r.club, "勝点": r.pts, "試合": r.played,
            "勝": r.win, "分": r.draw, "負": r.lose, "得失": r.gd,
        } for r in rows])
        sap = df["クラブ"].str.contains("札幌")
        st.dataframe(
            df.style.apply(lambda x: ["background-color:#fdeaec" if sap.iloc[i] else ""
                                      for i in range(len(x))], axis=0),
            use_container_width=True, hide_index=True,
        )
        st.caption("スポーツナビからライブ取得(10分ごと自動更新)。上位2枠=自動昇格、3〜6位=昇格PO圏。")
    else:
        st.markdown(card(
            f'<b style="color:{RED}">開幕前のため、2026/27の順位表はまだありません。</b><br>'
            f'<span style="font-size:13px">開幕(8/8)後にJ2全20クラブの最新順位を自動表示し、'
            f'札幌の行をハイライトします。昇格圏(2位以内)・PO圏(6位以内)との勝点差もここで追えます。</span>'
        ), unsafe_allow_html=True)
        st.markdown("[スポーツナビでJ2順位表を見る](https://soccer.yahoo.co.jp/jleague/category/j2/standings)")

# ============ 選手 ============
with tabs[4]:
    c1, c2 = st.columns([3, 1])
    c1.markdown("### 所属選手")
    if c2.button("更新", key="play_btn", use_container_width=True):
        cached_players.clear()
    try:
        with st.spinner("取得中…"):
            players, p_live = cached_players()
    except Exception:
        from fetchers import SNAPSHOT_PLAYERS
        players, p_live = SNAPSHOT_PLAYERS, False
    st.caption("ゲキサカからライブ取得(移籍を自動反映)" if p_live
               else f"{SNAPSHOT_DATE}時点の登録選手")
    for pos, label in [("GK", "ゴールキーパー"), ("DF", "ディフェンダー"),
                       ("MF", "ミッドフィールダー"), ("FW", "フォワード")]:
        group = [p for p in players if p.position == pos]
        if not group:
            continue
        chips = "".join(
            f'<div style="display:flex;align-items:center;gap:8px;background:#fff;'
            f'border-radius:10px;padding:8px 10px;box-shadow:0 1px 3px rgba(23,24,27,.08)">'
            f'<span style="background:{BLACK};color:#fff;font-weight:900;font-size:13px;'
            f'border-radius:8px;min-width:30px;text-align:center;padding:4px 0">{p.number}</span>'
            f'<span style="font-weight:700;font-size:13.5px">{p.name}</span></div>'
            for p in group
        )
        st.markdown(
            f'<div style="margin:10px 0 6px"><span style="background:{RED};color:#fff;'
            f'font-size:11px;font-weight:900;border-radius:4px;padding:3px 10px">{pos}</span> '
            f'<span style="font-size:12px;color:{GRAY};font-weight:700">{label}({len(group)}名)</span></div>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">{chips}</div>',
            unsafe_allow_html=True,
        )

# ============ 分析 ============
with tabs[5]:
    st.markdown("### アナリストの視点(2026特別シーズン)")

    # 前半戦 vs 後半戦
    def summarize(ms):
        p = sum(PTS[m[4]] for m in ms)
        gf = sum(int(m[3].split(" ")[0].split("-")[0]) for m in ms)
        ga = sum(int(m[3].split(" ")[0].split("-")[1]) for m in ms)
        return p, gf, ga

    p1, gf1, ga1 = summarize(SEASON_SP[:10])
    p2, gf2, ga2 = summarize(SEASON_SP[10:])
    st.markdown(card(
        f'<b style="font-size:13.5px">① 別チーム級の後半戦</b>'
        f'<table style="width:100%;font-size:13px;margin-top:6px;border-collapse:collapse;text-align:center">'
        f'<tr style="color:{GRAY};font-size:11px"><td></td><td>勝点</td><td>得点</td><td>失点</td></tr>'
        f'<tr><td style="text-align:left;font-weight:700">前半10試合</td>'
        f'<td>{p1}</td><td>{gf1}</td><td>{ga1}</td></tr>'
        f'<tr style="color:{RED};font-weight:800"><td style="text-align:left">後半10試合</td>'
        f'<td>{p2}</td><td>{gf2}</td><td>{ga2}</td></tr></table>'
        f'<div style="font-size:12px;color:{GRAY};margin-top:6px">後半戦は7連勝を含む圧倒的内容。'
        f'この状態を8月の開幕に持ち込めるかが最大の焦点。</div>'
    ), unsafe_allow_html=True)

    # ホーム/アウェイ
    hm = [m for m in SEASON_SP if m[2] == "H"]
    aw = [m for m in SEASON_SP if m[2] == "A"]
    ph, gfh, gah = summarize(hm)
    pa, gfa, gaa = summarize(aw)
    cs = sum(1 for m in SEASON_SP if int(m[3].split(" ")[0].split("-")[1]) == 0)
    st.markdown(card(
        f'<b style="font-size:13.5px">② ホーム/アウェイと守備</b>'
        f'<div style="display:flex;gap:8px;margin-top:8px;text-align:center">'
        f'<div style="flex:1;background:#fdeaec;border-radius:10px;padding:8px">'
        f'<div style="font-size:11px;font-weight:800;color:{RED}">ホーム {len(hm)}試合</div>'
        f'<div style="font-size:19px;font-weight:900">勝点{ph}</div>'
        f'<div style="font-size:11px;color:{GRAY}">得{gfh}/失{gah}</div></div>'
        f'<div style="flex:1;background:#f0f1f3;border-radius:10px;padding:8px">'
        f'<div style="font-size:11px;font-weight:800;color:{GRAY}">アウェイ {len(aw)}試合</div>'
        f'<div style="font-size:19px;font-weight:900">勝点{pa}</div>'
        f'<div style="font-size:11px;color:{GRAY}">得{gfa}/失{gaa}</div></div>'
        f'<div style="flex:1;background:{BLACK};border-radius:10px;padding:8px;color:#fff">'
        f'<div style="font-size:11px;font-weight:800;color:{PINK}">完封</div>'
        f'<div style="font-size:19px;font-weight:900">{cs}試合</div>'
        f'<div style="font-size:11px;color:#B9BDC4">/20試合</div></div></div>'
    ), unsafe_allow_html=True)

    st.markdown("### 勝点の積み上げ")
    total, pts_cum = 0, []
    for m in SEASON_SP:
        total += PTS[m[4]]
        pts_cum.append(total)
    df_pts = pd.DataFrame({"勝点": pts_cum}, index=range(1, 21))
    df_pts.index.name = "節"
    st.line_chart(df_pts, color=RED, height=200)

    st.markdown("### 得点・失点の推移")
    gf = [int(m[3].split(" ")[0].split("-")[0]) for m in SEASON_SP]
    ga = [int(m[3].split(" ")[0].split("-")[1]) for m in SEASON_SP]
    df_g = pd.DataFrame({"得点": gf, "失点": ga}, index=range(1, 21))
    df_g.index.name = "節"
    st.bar_chart(df_g, color=[RED, "#B9BDC4"], height=200)

    st.markdown("### 全試合結果")
    st.dataframe(
        pd.DataFrame([{"日付": d, "対戦": o, "H/A": h, "スコア": s, "結果": r}
                      for d, o, h, s, r in SEASON_SP]),
        use_container_width=True, hide_index=True, height=350,
    )

    st.markdown("### リーグ成績の推移")
    st.dataframe(
        pd.DataFrame([{"年": y, "リーグ": lg, "順位": f"{r}位"} for y, lg, r in HISTORY]),
        use_container_width=True, hide_index=True,
    )
    st.caption("J2優勝3回(2000・2007・2016)/ J1最高4位(2018)/ 2017〜24年に8季連続J1在籍")

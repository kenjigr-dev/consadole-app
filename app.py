"""コンサドーレ情報ボード (Streamlit版)  —  iPhone最適化版

起動: streamlit run app.py
"""
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
RED, BLACK, GRAY = "#C8102E", "#17181B", "#7a7f88"
PTS = {"勝": 3, "PK勝": 2, "PK負": 1, "負": 0}

st.set_page_config(page_title="コンサドーレ情報ボード", page_icon="⚽", layout="centered")

# ============ iPhone最適化CSS ============
st.markdown("""
<style>
/* 余白を詰めて画面を広く使う */
.block-container {padding: 0.6rem 0.9rem 3rem !important; max-width: 640px;}
header[data-testid="stHeader"] {height: 0;}
/* タブを大きく押しやすく */
button[data-baseweb="tab"] {font-size: 14px !important; font-weight: 800 !important;
  padding: 8px 10px !important;}
button[data-baseweb="tab"][aria-selected="true"] {color: #C8102E !important;}
div[data-baseweb="tab-highlight"] {background-color: #C8102E !important;}
/* 表の文字を読みやすく */
[data-testid="stDataFrame"] {font-size: 13px;}
h3 {font-size: 1.05rem !important; border-left: 4px solid #C8102E;
  padding-left: 9px; margin-top: 0.4rem !important;}
</style>
""", unsafe_allow_html=True)

# ============ 共通パーツ ============
def stripes():
    bar = "".join(
        f'<span style="display:inline-block;width:4.16%;height:9px;'
        f'background:{RED if i % 2 else BLACK}"></span>' for i in range(24)
    )
    return f'<div style="font-size:0;line-height:0">{bar}</div>'


def stat_grid(pairs, accent_first=True):
    """中央揃え・横並び固定の成績グリッド(iPhoneでも崩れない)"""
    cells = ""
    for i, (label, value) in enumerate(pairs):
        color = RED if (accent_first and i == 0) else BLACK
        cells += (
            f'<div style="flex:1;text-align:center;padding:6px 2px">'
            f'<div style="font-size:26px;font-weight:900;color:{color};line-height:1.1">{value}</div>'
            f'<div style="font-size:11px;color:{GRAY};font-weight:700;margin-top:2px">{label}</div>'
            f"</div>"
        )
    return (
        f'<div style="display:flex;background:#fff;border-radius:12px;'
        f'padding:8px 4px;box-shadow:0 1px 3px rgba(23,24,27,.08)">{cells}</div>'
    )


def card(html):
    return (
        f'<div style="background:#fff;border-radius:12px;padding:12px 14px;'
        f'margin-bottom:10px;box-shadow:0 1px 3px rgba(23,24,27,.08)">{html}</div>'
    )


st.markdown(
    stripes()
    + f'<div style="background:{BLACK};padding:12px 14px;border-radius:0 0 12px 12px;'
    f'margin-bottom:6px">'
    f'<div style="color:{RED};font-size:10px;letter-spacing:.22em;font-weight:800">'
    f"HOKKAIDO CONSADOLE SAPPORO</div>"
    f'<div style="color:#fff;font-size:19px;font-weight:900">コンサドーレ情報ボード</div>'
    f"</div>",
    unsafe_allow_html=True,
)

tabs = st.tabs(["ホーム", "ニュース", "日程", "順位表", "選手", "記録"])


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


# ============ ホーム ============
with tabs[0]:
    days = (KICKOFF_DATE - date.today()).days
    if days > 0:
        st.markdown(
            f'<div style="background:{BLACK};border-radius:14px;padding:18px 14px;'
            f'text-align:center;color:#fff;margin-bottom:10px">'
            f'<div style="color:#E8899A;font-size:10px;letter-spacing:.18em;font-weight:800">'
            f"2026/27 明治安田J2リーグ</div>"
            f'<div style="color:#B9BDC4;font-size:12px;margin-top:4px">開幕まで</div>'
            f'<div style="font-size:50px;font-weight:900;line-height:1.05">{days}'
            f'<span style="font-size:18px">日</span></div>'
            f'<div style="font-size:14px;font-weight:800;margin-top:5px">'
            f'8/8(土) 14:45 <span style="color:#E8899A">vs 徳島</span></div>'
            f'<div style="color:#B9BDC4;font-size:10.5px">大和ハウス プレミストドーム(ホーム開幕戦)</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(card(
            f'<b style="color:{RED}">2026/27シーズン開催中!</b> 最新結果は「日程」タブへ'
        ), unsafe_allow_html=True)

    st.markdown("### 2026 特別シーズン総括")
    w = sum(1 for m in SEASON_SP if m[4] == "勝")
    pw = sum(1 for m in SEASON_SP if m[4] == "PK勝")
    pl = sum(1 for m in SEASON_SP if m[4] == "PK負")
    lo = sum(1 for m in SEASON_SP if m[4] == "負")
    st.markdown(stat_grid([
        ("勝点", w * 3 + pw * 2 + pl), ("勝利", w), ("PK勝", pw), ("PK負", pl), ("敗戦", lo),
    ]), unsafe_allow_html=True)
    st.caption("J2J3百年構想リーグ(2〜6月・全20試合)。序盤5戦未勝利から4/18〜5/16に7連勝。")

    st.markdown("### 新シーズンはここが変わる")
    st.markdown(card(
        f'<table style="width:100%;font-size:13px;border-collapse:collapse">'
        f'<tr><td style="color:{RED};font-weight:800;width:62px;padding:5px 0">開幕</td>'
        f"<td>2026年8月8日・9日(秋春制へ移行)</td></tr>"
        f'<tr><td style="color:{RED};font-weight:800;padding:5px 0">中断</td>'
        f"<td>12月2週頃〜2月3週頃はウィンターブレーク</td></tr>"
        f'<tr><td style="color:{RED};font-weight:800;padding:5px 0">最終節</td>'
        f"<td>2027年5月22日・23日(全38節・20クラブ)</td></tr>"
        f'<tr><td style="color:{RED};font-weight:800;padding:5px 0">昇格PO</td>'
        f"<td>準決勝 5/29・30 / 決勝 6/5・6</td></tr></table>"
    ), unsafe_allow_html=True)

    st.markdown("### クラブ・リンク")
    st.markdown(card(
        f'<div style="font-size:13px;line-height:2">'
        f'<a href="https://www.consadole-sapporo.jp/" target="_blank" '
        f'style="color:{BLACK};font-weight:700">公式サイト →</a><br>'
        f'<a href="https://www.jleague.jp/club/sapporo/" target="_blank" '
        f'style="color:{BLACK};font-weight:700">Jリーグ公式・札幌ページ →</a><br>'
        f'<a href="https://www.football-lab.jp/sapp" target="_blank" '
        f'style="color:{BLACK};font-weight:700">Football LAB(データ分析) →</a></div>'
    ), unsafe_allow_html=True)
    st.caption("名前の由来:「どさんこ」の逆さ読み+「オーレ」/ クラブカラー: 赤・黒")

# ============ ニュース ============
with tabs[1]:
    c1, c2 = st.columns([3, 1])
    c1.markdown("### 最新ニュース")
    if c2.button("更新", key="news_btn", use_container_width=True):
        cached_news.clear()
    try:
        with st.spinner("取得中…"):
            news, at = cached_news()
        st.caption(f"Google Newsからリアルタイム取得({at:%H:%M}時点・5分ごと自動更新)")
        for n in news:
            st.markdown(card(
                f'<span style="background:{BLACK};color:#fff;font-size:10px;font-weight:800;'
                f'border-radius:4px;padding:2px 7px">{n.source}</span> '
                f'<span style="color:{GRAY};font-size:11px">{n.date}</span>'
                f'<div style="font-weight:800;font-size:14px;margin-top:5px;line-height:1.5">'
                f'<a href="{n.url}" target="_blank" style="color:{BLACK};text-decoration:none">'
                f"{n.title}</a></div>"
                f'<a href="{n.url}" target="_blank" style="color:{RED};font-size:12px;'
                f'font-weight:700;text-decoration:none">記事を読む →</a>'
            ), unsafe_allow_html=True)
    except Exception:
        st.error("ニュースの取得に失敗しました。通信環境を確認して「更新」を押してください。")

# ============ 日程 ============
with tabs[2]:
    c1, c2 = st.columns([3, 1])
    c1.markdown("### 日程・結果")
    if c2.button("更新", key="sched_btn", use_container_width=True):
        cached_schedule.clear()
    try:
        with st.spinner("取得中…"):
            sched, live, at = cached_schedule()
    except Exception:
        from fetchers import SNAPSHOT_SCHEDULE
        sched, live, at = SNAPSHOT_SCHEDULE, False, None
    st.caption(
        f"公式サイトからライブ取得({at:%H:%M}時点)" if live
        else f"{SNAPSHOT_DATE}時点の確定日程を表示中"
    )
    for m in sched:
        ha_label = "ホーム" if m.home_away == "H" else "アウェイ"
        ha_color = RED if m.home_away == "H" else GRAY
        res_color = RED if m.result != "予定" else "#555"
        st.markdown(card(
            f'<div style="display:flex;align-items:center;gap:10px">'
            f'<div style="min-width:80px"><b style="font-size:13px">{m.date}</b><br>'
            f'<span style="font-size:10.5px;color:{GRAY}">{m.comp}</span></div>'
            f'<div style="flex:1"><b style="font-size:15px">vs {m.opponent}</b><br>'
            f'<span style="font-size:11px;color:{ha_color};font-weight:700">{ha_label}</span>'
            f'<span style="font-size:11px;color:{GRAY}"> {m.venue}</span></div>'
            f'<div style="text-align:right;font-weight:800;color:{res_color};min-width:56px">'
            f"{m.result}<br><span style='font-size:11px;color:{GRAY};font-weight:400'>{m.kickoff}</span></div>"
            f"</div>"
        ), unsafe_allow_html=True)

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
            df.style.apply(
                lambda x: ["background-color:#fdeaec" if sap.iloc[i] else ""
                           for i in range(len(x))], axis=0),
            use_container_width=True, hide_index=True,
        )
        st.caption("スポーツナビからライブ取得(10分ごと自動更新)")
    else:
        st.markdown(card(
            f'<b style="color:{RED}">開幕前のため、2026/27シーズンの順位表はまだありません。</b><br>'
            f'<span style="font-size:13px">開幕(8/8)後は、このタブに最新のJ2順位表が自動表示され、'
            f"札幌の行がハイライトされます。</span>"
        ), unsafe_allow_html=True)
        st.markdown(
            "[スポーツナビでJ2順位表を見る]"
            "(https://soccer.yahoo.co.jp/jleague/category/j2/standings)"
        )

# ============ 選手 ============
with tabs[4]:
    c1, c2 = st.columns([3, 1])
    c1.markdown("### 所属選手")
    if c2.button("更新", key="play_btn", use_container_width=True):
        cached_players.clear()
    try:
        with st.spinner("取得中…"):
            players, live = cached_players()
    except Exception:
        from fetchers import SNAPSHOT_PLAYERS
        players, live = SNAPSHOT_PLAYERS, False
    st.caption(
        "ゲキサカからライブ取得(移籍があれば自動反映)" if live
        else f"{SNAPSHOT_DATE}時点の登録選手を表示中"
    )
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
            f'<span style="font-size:12px;color:{GRAY};font-weight:700">{label}</span></div>'
            f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">{chips}</div>',
            unsafe_allow_html=True,
        )

# ============ 記録 ============
with tabs[5]:
    st.markdown("### 勝点の積み上げ(2026特別シーズン)")
    pts_cum, total = [], 0
    for m in SEASON_SP:
        total += PTS[m[4]]
        pts_cum.append(total)
    df_pts = pd.DataFrame({"勝点": pts_cum}, index=range(1, 21))
    df_pts.index.name = "節"
    st.line_chart(df_pts, color=RED, height=220)
    st.caption("第10節(勝点10)以降に急上昇 = 7連勝の期間。最終勝点33。")

    st.markdown("### 得点・失点の推移")
    gf = [int(m[3].split(" ")[0].split("-")[0]) for m in SEASON_SP]
    ga = [int(m[3].split(" ")[0].split("-")[1]) for m in SEASON_SP]
    df_g = pd.DataFrame({"得点": gf, "失点": ga}, index=range(1, 21))
    df_g.index.name = "節"
    st.bar_chart(df_g, color=[RED, "#B9BDC4"], height=220)
    st.caption(f"総得点 {sum(gf)} / 総失点 {sum(ga)}(得失点差 +{sum(gf)-sum(ga)})")

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

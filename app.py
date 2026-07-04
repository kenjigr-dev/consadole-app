"""コンサドーレ情報ボード (Streamlit版)

起動: streamlit run app.py
ニュースと日程はWebから直接リアルタイム取得(5分キャッシュ)。
"""
from datetime import date, datetime

import streamlit as st

from fetchers import (SNAPSHOT_DATE, SNAPSHOT_SCHEDULE, fetch_news,
                      fetch_schedule)

# ============ 静的データ(2026-07-04時点) ============
SEASON_SP = [
    ("02.08", "いわき", "A", "0-1", "負"), ("02.14", "大宮", "A", "2-3", "負"),
    ("02.21", "長野", "A", "1-1 (PK5-4)", "PK勝"), ("02.28", "岐阜", "H", "1-2", "負"),
    ("03.07", "松本", "A", "0-3", "負"), ("03.14", "磐田", "A", "1-0", "勝"),
    ("03.21", "甲府", "H", "1-0", "勝"), ("03.28", "藤枝", "A", "1-1 (PK4-2)", "PK勝"),
    ("04.04", "福島", "H", "0-2", "負"), ("04.11", "甲府", "A", "1-2", "負"),
    ("04.18", "松本", "H", "2-1", "勝"), ("04.25", "いわき", "H", "2-1", "勝"),
    ("04.29", "藤枝", "H", "2-1", "勝"), ("05.02", "岐阜", "A", "3-0", "勝"),
    ("05.06", "長野", "H", "2-0", "勝"), ("05.09", "大宮", "H", "4-3", "勝"),
    ("05.16", "福島", "A", "3-0", "勝"), ("05.23", "磐田", "H", "0-1", "負"),
    ("05.31", "秋田", "A", "1-1 (PK4-5)", "PK負"), ("06.06", "新潟", "A", "0-0 (PK4-5)", "PK負"),
]
HISTORY = [
    (2025, "J2", 12), (2024, "J1", 19), (2023, "J1", 12), (2022, "J1", 10),
    (2021, "J1", 10), (2020, "J1", 12), (2019, "J1", 10), (2018, "J1", 4),
    (2017, "J1", 11), (2016, "J2", 1), (2015, "J2", 10), (2014, "J2", 10),
]
KICKOFF_DATE = date(2026, 8, 8)

RED, BLACK = "#C8102E", "#17181B"

st.set_page_config(page_title="コンサドーレ情報ボード", page_icon="⚽", layout="centered")

# 赤黒ストライプのヘッダー
stripe = "".join(
    f'<span style="display:inline-block;width:4.16%;height:10px;'
    f'background:{RED if i % 2 else BLACK}"></span>'
    for i in range(24)
)
st.markdown(
    f'<div style="font-size:0;line-height:0">{stripe}</div>'
    f'<div style="background:{BLACK};padding:14px 16px;border-radius:0 0 12px 12px">'
    f'<div style="color:{RED};font-size:11px;letter-spacing:.25em;font-weight:800">'
    f'HOKKAIDO CONSADOLE SAPPORO</div>'
    f'<div style="color:#fff;font-size:22px;font-weight:900">コンサドーレ情報ボード</div>'
    f"</div>",
    unsafe_allow_html=True,
)

tab_home, tab_news, tab_sched, tab_rec, tab_club = st.tabs(
    ["ホーム", "ニュース", "日程・結果", "記録", "クラブ"]
)


# ============ キャッシュ付き取得(5分ごとに自動で最新化) ============
@st.cache_data(ttl=300, show_spinner=False)
def cached_news():
    return fetch_news(limit=10), datetime.now()


@st.cache_data(ttl=300, show_spinner=False)
def cached_schedule():
    sched, live = fetch_schedule()
    return sched, live, datetime.now()


# ============ ホーム ============
with tab_home:
    days = (KICKOFF_DATE - date.today()).days
    if days > 0:
        st.markdown(
            f'<div style="background:{BLACK};border-radius:14px;padding:22px;'
            f'text-align:center;color:#fff">'
            f'<div style="color:#E8899A;font-size:11px;letter-spacing:.2em;font-weight:800">'
            f"2026/27 明治安田J2リーグ</div>"
            f'<div style="color:#B9BDC4;font-size:13px;margin-top:6px">開幕まで</div>'
            f'<div style="font-size:54px;font-weight:900;line-height:1.1">{days}'
            f'<span style="font-size:20px">日</span></div>'
            f'<div style="font-size:14px;font-weight:800;margin-top:6px">'
            f'8/8(土) 14:45 <span style="color:#E8899A">vs 徳島</span></div>'
            f'<div style="color:#B9BDC4;font-size:11px">大和ハウス プレミストドーム(ホーム開幕戦)</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.success("2026/27シーズン開催中! 最新結果は「日程・結果」タブへ")

    st.subheader("新シーズンはここが変わる")
    st.markdown(
        "- **開幕**: 2026年8月8日・9日(秋春制へ移行後初のシーズン)\n"
        "- **中断**: 12月2週頃〜2027年2月3週頃はウィンターブレーク\n"
        "- **最終節**: 2027年5月22日・23日(全38節・20クラブ)\n"
        "- **昇格PO**: 準決勝 5月29日・30日 / 決勝 6月5日・6日"
    )

    st.subheader("2026 特別シーズン総括")
    w = sum(1 for m in SEASON_SP if m[4] == "勝")
    pw = sum(1 for m in SEASON_SP if m[4] == "PK勝")
    pl = sum(1 for m in SEASON_SP if m[4] == "PK負")
    l = sum(1 for m in SEASON_SP if m[4] == "負")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("勝利", w)
    c2.metric("PK勝", pw)
    c3.metric("PK負", pl)
    c4.metric("敗戦", l)
    c5.metric("勝点", w * 3 + pw * 2 + pl)
    st.caption("J2J3百年構想リーグ(2〜6月・全20試合)。序盤5戦未勝利から4/18〜5/16に7連勝。")

# ============ ニュース ============
with tab_news:
    col1, col2 = st.columns([3, 1])
    col1.subheader("最新ニュース")
    if col2.button("今すぐ更新", key="news_btn"):
        cached_news.clear()
    try:
        with st.spinner("ニュースを取得中…"):
            news, fetched_at = cached_news()
        st.caption(
            f"Google News経由でリアルタイム取得(最終更新 {fetched_at:%H:%M}、5分ごとに自動更新)"
        )
        for n in news:
            st.markdown(
                f'<div style="background:#fff;border-radius:12px;padding:12px 14px;'
                f'margin-bottom:10px;box-shadow:0 1px 3px rgba(23,24,27,.08)">'
                f'<span style="background:{BLACK};color:#fff;font-size:10px;font-weight:800;'
                f'border-radius:4px;padding:2px 7px">{n.source}</span> '
                f'<span style="color:#9aa0aa;font-size:11px">{n.date}</span>'
                f'<div style="font-weight:800;font-size:14.5px;margin-top:5px;color:{BLACK}">'
                f'<a href="{n.url}" target="_blank" style="color:{BLACK};text-decoration:none">'
                f"{n.title}</a></div>"
                f'<a href="{n.url}" target="_blank" style="color:{RED};font-size:12px;'
                f'font-weight:700;text-decoration:none">記事を読む →</a></div>',
                unsafe_allow_html=True,
            )
    except Exception as e:
        st.error(f"ニュースの取得に失敗しました。通信環境を確認してください。({e})")

# ============ 日程・結果 ============
with tab_sched:
    col1, col2 = st.columns([3, 1])
    col1.subheader("2026/27シーズン 日程・結果")
    if col2.button("今すぐ更新", key="sched_btn"):
        cached_schedule.clear()
    try:
        with st.spinner("日程・結果を取得中…"):
            sched, live, fetched_at = cached_schedule()
    except Exception:
        sched, live, fetched_at = SNAPSHOT_SCHEDULE, False, None
    if live:
        st.caption(f"公式サイトからリアルタイム取得(最終更新 {fetched_at:%H:%M})")
    else:
        st.caption(
            f"{SNAPSHOT_DATE}時点の確定日程を表示中"
            "(公式サイトの構造変更等でライブ取得できない場合はこちらが表示されます)"
        )
    for m in sched:
        ha = "🏠 ホーム" if m.home_away == "H" else "✈️ アウェイ"
        res_color = RED if m.result not in ("予定",) else "#555"
        st.markdown(
            f'<div style="background:#fff;border-radius:12px;padding:12px 14px;'
            f'margin-bottom:10px;box-shadow:0 1px 3px rgba(23,24,27,.08);'
            f'display:flex;align-items:center;gap:12px">'
            f'<div style="min-width:86px"><b>{m.date}</b><br>'
            f'<span style="font-size:11px;color:#7a7f88">{m.comp}</span></div>'
            f'<div style="flex:1"><b style="font-size:15px">vs {m.opponent}</b><br>'
            f'<span style="font-size:11.5px;color:#7a7f88">{ha}・{m.venue}</span></div>'
            f'<div style="font-weight:800;color:{res_color};text-align:right">'
            f"{m.result}<br><span style='font-size:11px;color:#7a7f88'>{m.kickoff}</span></div>"
            f"</div>",
            unsafe_allow_html=True,
        )
    st.markdown(
        "[公式サイトで全日程を確認する](https://www.consadole-sapporo.jp/game/)"
    )

# ============ 記録 ============
with tab_rec:
    st.subheader("2026 J2J3百年構想リーグ 全結果")
    st.dataframe(
        [{"日付": d, "対戦": o, "H/A": h, "スコア": s, "結果": r}
         for d, o, h, s, r in SEASON_SP],
        use_container_width=True, hide_index=True,
    )
    st.subheader("リーグ成績の推移")
    st.dataframe(
        [{"年": y, "リーグ": lg, "順位": f"{r}位"} for y, lg, r in HISTORY],
        use_container_width=True, hide_index=True,
    )
    st.markdown(
        "- J2リーグ優勝 **3回**(2000・2007・2016年)\n"
        "- J1最高順位 **4位**(2018年)\n"
        "- 2017〜2024年に8季連続J1在籍(クラブ最長)"
    )

# ============ クラブ ============
with tab_club:
    st.subheader("クラブプロフィール")
    st.markdown(
        "| | |\n|---|---|\n"
        "| 正式名称 | 北海道コンサドーレ札幌 |\n"
        "| 名前の由来 | 「どさんこ」の逆さ読み+ラテン語風の「オーレ」 |\n"
        "| クラブカラー | 赤・黒 |\n"
        "| ホーム | 大和ハウス プレミストドーム / 札幌厚別公園競技場 |\n"
        "| アクセス | 地下鉄東豊線「福住」駅から徒歩10分 |"
    )
    st.subheader("公式情報リンク")
    st.markdown(
        "- [公式サイト](https://www.consadole-sapporo.jp/)\n"
        "- [Jリーグ公式・札幌ページ](https://www.jleague.jp/club/sapporo/)\n"
        "- [Football LAB(データ分析)](https://www.football-lab.jp/sapp)"
    )

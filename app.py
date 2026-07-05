"""コンサ情報ボード — マッチデー中心設計・iPhone最適化"""
import re
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from fetchers import (SNAPSHOT_DATE, fetch_news, fetch_players,
                      fetch_schedule, fetch_standings)

JST = timezone(timedelta(hours=9))


def now_jst() -> datetime:
    """日本時間の現在時刻(サーバーはUTCで動くため必ずこれを使う)"""
    return datetime.now(JST)


def today_jst() -> date:
    return now_jst().date()

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
RED, BLACK, GRAY, PINK = "#E8112D", "#17181B", "#9aa0ab", "#FF6B81"
BG, CARD_BG, CARD_BD, TXT = "#0D0E11", "#191B20", "#272A31", "#F2F3F5"
GRAD_RED = "linear-gradient(135deg,#E8112D 0%,#8f0a1d 100%)"
PTS = {"勝": 3, "PK勝": 2, "PK負": 1, "負": 0}
RESULT_DOT = {"勝": ("W", "#FF3B55"), "PK勝": ("W", PINK), "PK負": ("L", "#7d8494"), "負": ("L", "#4a4f59")}

st.set_page_config(page_title="コンサ情報ボード", page_icon="⚽", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Anton&display=swap');
.block-container {padding: 0.5rem 0.85rem 3rem !important; max-width: 640px;}
/* Streamlitの標準UIを隠す */
header[data-testid="stHeader"] {display: none !important;}
div[data-testid="stToolbar"], div[data-testid="stDecoration"],
div[data-testid="stStatusWidget"] {display: none !important;}
#MainMenu {visibility: hidden !important;}
footer {display: none !important;}
div[class^="viewerBadge"], div[class*=" viewerBadge"] {display: none !important;}
.stAppDeployButton {display: none !important;}
/* タブ: スタジアムの電光掲示板風 */
div[data-baseweb="tab-list"] {gap: 2px; background: #14161a; border-radius: 12px;
  padding: 4px;}
button[data-baseweb="tab"] {font-size: 13.5px !important; font-weight: 800 !important;
  padding: 9px 8px !important; border-radius: 9px !important; color: #9aa0ab !important;}
button[data-baseweb="tab"][aria-selected="true"] {color: #fff !important;
  background: linear-gradient(135deg,#E8112D,#8f0a1d) !important;
  box-shadow: 0 2px 10px rgba(232,17,45,.45);}
div[data-baseweb="tab-highlight"] {display: none !important;}
div[data-baseweb="tab-border"] {display: none !important;}
/* 数字はスコアボード書体 */
.score-num {font-family: 'Anton', sans-serif; letter-spacing: .02em;}
/* カードの登場アニメーション */
@keyframes rise {from {opacity: 0; transform: translateY(8px);} to {opacity: 1; transform: none;}}
@keyframes pulse {0%,100% {box-shadow: 0 0 24px rgba(232,17,45,.35);}
  50% {box-shadow: 0 0 44px rgba(232,17,45,.65);}}
.rise {animation: rise .45s ease both;}
/* ボタン */
div.stButton > button {border: 1px solid #272A31 !important; border-radius: 12px !important;
  background: #191B20 !important; color: #F2F3F5 !important; font-weight: 700 !important;}
div.stButton > button:hover {border-color: #E8112D !important; color: #FF6B81 !important;}
/* 選手ボタン(key=pl_*)は大きく・太く・背番号を強調 */
div[class*="st-key-pl_"] button {padding: 13px 6px !important; min-height: 52px !important;
  border-left: 3px solid #E8112D !important;}
div[class*="st-key-pl_"] button p {font-size: 16px !important; font-weight: 900 !important;
  letter-spacing: .02em !important;}
[data-testid="stDataFrame"] {font-size: 13px;}
h3 {font-size: 1.0rem !important; margin: 0.5rem 0 0.4rem !important; color: #F2F3F5;}
</style>
""", unsafe_allow_html=True)


# ============ 部品 ============
def card(html, pad="13px 15px", mb="10px", glow=False):
    extra = "animation:pulse 3s ease-in-out infinite;" if glow else ""
    return (f'<div class="rise" style="background:{CARD_BG};border:1px solid {CARD_BD};'
            f'border-radius:16px;padding:{pad};margin-bottom:{mb};{extra}">{html}</div>')


def stat_grid(pairs, accent_first=True):
    cells = ""
    for i, (label, value) in enumerate(pairs):
        color = "#FF3B55" if (accent_first and i == 0) else TXT
        top = RED if (accent_first and i == 0) else CARD_BD
        cells += (f'<div style="flex:1;text-align:center;padding:9px 2px;background:{CARD_BG};'
                  f'border:1px solid {CARD_BD};border-top:3px solid {top};border-radius:12px">'
                  f'<div class="score-num" style="font-size:29px;color:{color};line-height:1.05">{value}</div>'
                  f'<div style="font-size:10px;color:{GRAY};font-weight:800;letter-spacing:.08em;'
                  f'margin-top:3px">{label}</div></div>')
    return f'<div class="rise" style="display:flex;gap:6px;margin-bottom:10px">{cells}</div>'


def form_dots(results, size=15):
    """直近試合のフォームを●○で表示(左が古い、右が最新)"""
    dots = ""
    for r in results:
        ch, color = RESULT_DOT[r]
        dots += (f'<span class="score-num" style="display:inline-block;width:22px;height:22px;'
                 f'line-height:22px;text-align:center;border-radius:6px;margin:0 2px;'
                 f'background:{color};color:#0D0E11;font-size:13px">{ch}</span>')
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


def section_label(text, en=""):
    eyebrow = (f'<div style="font-size:9.5px;letter-spacing:.3em;color:{RED};'
               f'font-weight:800">{en}</div>' if en else "")
    return (f'<div style="margin:16px 0 8px">{eyebrow}'
            f'<div style="font-size:15px;font-weight:900;color:{TXT}">{text}</div></div>')


# ============ ヘッダー ============
stripe = "".join(f'<span style="display:inline-block;width:4.16%;height:8px;'
                 f'background:{RED if i % 2 else BLACK}"></span>' for i in range(24))
st.markdown(
    f'<div style="font-size:0;line-height:0">{stripe}</div>'
    f'<div style="background:linear-gradient(180deg,#191B20,#0D0E11);'
    f'border:1px solid {CARD_BD};border-top:none;padding:12px 15px;'
    f'border-radius:0 0 16px 16px;margin-bottom:10px">'
    f'<div style="color:{RED};font-size:9px;letter-spacing:.28em;font-weight:800">'
    f'HOKKAIDO CONSADOLE SAPPORO</div>'
    f'<div style="color:{TXT};font-size:19px;font-weight:900;letter-spacing:.02em">'
    f'コンサ<span style="color:{RED}">情報ボード</span></div></div>',
    unsafe_allow_html=True,
)

tabs = st.tabs(["ホーム", "ニュース", "日程", "順位表", "選手", "分析"])


@st.cache_data(ttl=300, show_spinner=False)
def cached_news():
    return fetch_news(limit=10), now_jst()


@st.cache_data(ttl=300, show_spinner=False)
def cached_schedule():
    s, live = fetch_schedule()
    return s, live, now_jst()


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
    today = today_jst()

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
            f'<div class="rise" style="background:linear-gradient(135deg,#22060b 0%,#191B20 55%);'
            f'border:1px solid #3a1218;border-radius:18px;padding:16px 15px;color:{TXT};'
            f'margin-bottom:10px;position:relative;overflow:hidden;'
            f'animation:pulse 3.2s ease-in-out infinite">'
            f'<div style="position:absolute;top:0;left:0;right:0;height:4px;background:'
            f'repeating-linear-gradient(90deg,{RED} 0 22px,transparent 22px 44px)"></div>'
            f'<div style="position:absolute;right:-30px;top:-30px;width:130px;height:130px;'
            f'border-radius:50%;background:radial-gradient(circle,rgba(232,17,45,.28),transparent 70%)"></div>'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-top:4px">'
            f'<span style="color:{PINK};font-size:10px;font-weight:800;letter-spacing:.22em">NEXT MATCH'
            f' <span style="color:{GRAY};letter-spacing:0">/ {next_m.comp}</span></span>'
            f'<span class="score-num" style="background:{GRAD_RED};border-radius:20px;'
            f'padding:3px 13px;font-size:13px;box-shadow:0 2px 12px rgba(232,17,45,.5)">{when}</span></div>'
            f'<div style="margin-top:10px;display:flex;align-items:baseline;gap:10px">'
            f'<span class="score-num" style="font-size:21px;color:{TXT}">札幌</span>'
            f'<span class="score-num" style="font-size:15px;color:{RED}">VS</span>'
            f'<span class="score-num" style="font-size:30px;color:{TXT}">{next_m.opponent}</span>'
            f'<span style="font-size:11px;color:{PINK};font-weight:800">{ha}</span></div>'
            f'<div style="font-size:12px;color:{GRAY};margin-top:6px">'
            f'{next_m.date} {next_m.kickoff}<br>{next_m.venue}</div></div>',
            unsafe_allow_html=True,
        )

    # --- 開幕カウントダウン(コンパクト) ---
    days = (KICKOFF_DATE - today).days
    if days > 0:
        st.markdown(card(
            f'<div style="display:flex;justify-content:space-between;align-items:center">'
            f'<div style="font-size:12.5px;font-weight:700;color:{TXT}">'
            f'J2リーグ開幕<br><span style="color:{GRAY};font-size:11px">8/8(土) 14:45 vs 徳島</span></div>'
            f'<div style="text-align:right"><span class="score-num" style="color:#FF3B55;'
            f'font-size:34px;line-height:1">{days}</span>'
            f'<span style="color:{GRAY};font-size:11px;font-weight:700"> 日</span></div></div>',
            pad="10px 15px",
        ), unsafe_allow_html=True)

    # --- 次節 予想スタメン(フォーメーション表示) ---
    st.markdown(section_label("次節 予想スタメン", "PREDICTED XI — AI予想"), unsafe_allow_html=True)
    PREDICTED_XI = [  # (背番号, 名前, 横位置%, 縦位置%) 上が敵陣
        ("20", "バカヨコ", 50, 12),
        ("7", "スパチョーク", 16, 31), ("11", "青木亮太", 50, 29), ("71", "白井陽斗", 84, 31),
        ("27", "荒野拓馬", 36, 51), ("18", "木戸柊摩", 64, 51),
        ("5", "福森晃斗", 13, 70), ("25", "大崎玲央", 37, 74),
        ("3", "パク・ミンギュ", 63, 74), ("2", "高尾瑠", 87, 70),
        ("24", "田川知樹", 50, 90),
    ]
    chips = ""
    for num, name, x, y in PREDICTED_XI:
        chips += (
            f'<div style="position:absolute;left:{x}%;top:{y}%;'
            f'transform:translate(-50%,-50%);text-align:center;width:76px">'
            f'<div class="score-num" style="width:30px;height:30px;line-height:30px;'
            f'margin:0 auto;border-radius:50%;background:{GRAD_RED};color:#fff;'
            f'font-size:14px;box-shadow:0 2px 8px rgba(0,0,0,.5);'
            f'border:1.5px solid rgba(255,255,255,.7)">{num}</div>'
            f'<div style="font-size:10px;font-weight:800;color:#fff;margin-top:2px;'
            f'text-shadow:0 1px 3px rgba(0,0,0,.9);line-height:1.2">{name}</div></div>'
        )
    pitch = (
        f'<div class="rise" style="position:relative;height:400px;border-radius:16px;'
        f'overflow:hidden;border:1px solid {CARD_BD};margin-bottom:8px;'
        f'background:repeating-linear-gradient(180deg,#11592d 0 50px,#0e4d27 50px 100px)">'
        # ピッチの線
        f'<div style="position:absolute;inset:8px;border:1.5px solid rgba(255,255,255,.35);'
        f'border-radius:4px"></div>'
        f'<div style="position:absolute;left:50%;top:8px;transform:translateX(-50%);'
        f'width:90px;height:45px;border:1.5px solid rgba(255,255,255,.3);'
        f'border-top:none;border-radius:0 0 60px 60px"></div>'
        f'<div style="position:absolute;left:50%;bottom:8px;transform:translateX(-50%);'
        f'width:170px;height:58px;border:1.5px solid rgba(255,255,255,.35);border-bottom:none"></div>'
        f'<div style="position:absolute;left:50%;bottom:8px;transform:translateX(-50%);'
        f'width:80px;height:26px;border:1.5px solid rgba(255,255,255,.35);border-bottom:none"></div>'
        f'<div style="position:absolute;left:12px;top:12px;background:rgba(0,0,0,.55);'
        f'border-radius:8px;padding:4px 10px;font-size:10px;font-weight:800;color:#fff">'
        f'4-2-3-1 <span style="color:{PINK}">/ 監督 川井健太</span></div>'
        + chips + '</div>'
    )
    st.markdown(pitch, unsafe_allow_html=True)
    st.markdown(card(
        f'<div style="font-size:11.5px;color:{GRAY};line-height:1.8">'
        f'<b style="color:{PINK}">予想の根拠:</b> 2026特別シーズンの実績スタメンをベースに、'
        f'家泉怜依の退団(→大崎玲央)、マリオ・セルジオの負傷離脱を反映。'
        f'西野奨太・堀米悠斗・ジョルディ・サンチェスらが割って入る候補。'
        f'※AIによる予想であり公式発表ではありません。</div>',
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
        f'<a href="https://www.consadole-sapporo.jp/" target="_blank" style="color:{TXT};font-weight:700">公式サイト →</a><br>'
        f'<a href="https://www.jleague.jp/club/sapporo/" target="_blank" style="color:{TXT};font-weight:700">Jリーグ公式・札幌ページ →</a><br>'
        f'<a href="https://www.football-lab.jp/sapp" target="_blank" style="color:{TXT};font-weight:700">Football LAB(データ分析) →</a></div>'
    ), unsafe_allow_html=True)

# ============ ニュース ============
with tabs[1]:
    c1, c2 = st.columns([3, 1])
    c1.markdown("### 最新ニュース")
    if c2.button("更新", key="news_btn", width="stretch"):
        cached_news.clear()
    try:
        with st.spinner("取得中…"):
            news, at = cached_news()
        if not news:
            st.warning("ニュースを取得できませんでした。しばらくしてから「更新」を押してください。")
        else:
            st.caption(f"リアルタイム取得 {at:%H:%M}(5分ごと自動更新)")
        for n in news:
            st.markdown(card(
                f'<span style="background:{GRAD_RED};color:#fff;font-size:10px;font-weight:800;'
                f'border-radius:5px;padding:2px 8px">{n.source}</span> '
                f'<span style="color:{GRAY};font-size:11px">{n.date}</span>'
                f'<div style="font-weight:800;font-size:14px;margin-top:6px;line-height:1.6">'
                f'<a href="{n.url}" target="_blank" style="color:{TXT};text-decoration:none">{n.title}</a></div>'
            ), unsafe_allow_html=True)
    except Exception:
        st.error("ニュースの取得に失敗しました。通信環境を確認して「更新」を押してください。")

# ============ 日程 ============
with tabs[2]:
    c1, c2 = st.columns([3, 1])
    c1.markdown("### 日程・結果")
    if c2.button("更新", key="sched_btn", width="stretch"):
        cached_schedule.clear()
    sched, live, at = get_schedule_safe()
    st.caption(f"公式サイトからライブ取得({at:%H:%M})" if live
               else f"{SNAPSHOT_DATE}時点の確定日程")
    TICKET_URL = "https://www.consadole-sapporo.jp/ticket/"
    st.markdown(
        f'<a href="{TICKET_URL}" target="_blank" style="text-decoration:none">'
        f'<div class="rise" style="background:{GRAD_RED};border-radius:14px;padding:11px 15px;'
        f'margin-bottom:10px;display:flex;justify-content:space-between;align-items:center;'
        f'box-shadow:0 2px 14px rgba(232,17,45,.4)">'
        f'<span style="color:#fff;font-weight:900;font-size:14px">🎫 チケットを購入する</span>'
        f'<span style="color:#fff;font-size:12px;opacity:.9">公式チケットページ →</span></div></a>',
        unsafe_allow_html=True,
    )
    for m in sched:
        ha_label = "H" if m.home_away == "H" else "A"
        ha_color = RED if m.home_away == "H" else GRAY
        res_color = "#FF3B55" if m.result != "予定" else GRAY
        ticket = ""
        if m.home_away == "H" and m.result == "予定":
            ticket = (f' <a href="{TICKET_URL}" target="_blank" style="color:{PINK};'
                      f'font-size:10.5px;font-weight:800;text-decoration:none">🎫チケット</a>')
        st.markdown(card(
            f'<div style="display:flex;align-items:center;gap:10px">'
            f'<div style="min-width:76px"><b style="font-size:13px">{m.date}</b><br>'
            f'<span style="font-size:10px;color:{GRAY}">{m.comp}</span></div>'
            f'<span style="background:{ha_color};color:#fff;font-weight:900;font-size:12px;'
            f'border-radius:6px;padding:3px 8px">{ha_label}</span>'
            f'<div style="flex:1"><b style="font-size:15px">{m.opponent}</b><br>'
            f'<span style="font-size:10.5px;color:{GRAY}">{m.venue}</span>{ticket}</div>'
            f'<div style="text-align:right;font-weight:800;color:{res_color};min-width:52px">'
            f"{m.result}<br><span style='font-size:11px;color:{GRAY};font-weight:400'>{m.kickoff}</span></div></div>",
            pad="10px 12px", mb="8px",
        ), unsafe_allow_html=True)
    st.markdown("[公式サイトで全日程を確認する](https://www.consadole-sapporo.jp/game/)")

# ============ 順位表 ============
with tabs[3]:
    c1, c2 = st.columns([3, 1])
    c1.markdown("### J2順位表")
    if c2.button("更新", key="stand_btn", width="stretch"):
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
            df.style.apply(lambda x: ["background-color:#3a1218" if sap.iloc[i] else ""
                                      for i in range(len(x))], axis=0),
            width="stretch", hide_index=True,
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
    if c2.button("更新", key="play_btn", width="stretch"):
        cached_players.clear()
    try:
        with st.spinner("取得中…"):
            players, p_live = cached_players()
    except Exception:
        from fetchers import SNAPSHOT_PLAYERS
        players, p_live = SNAPSHOT_PLAYERS, False
    st.caption("選手名をタップすると経歴がポップアップ表示されます"
               + ("(名簿はライブ取得)" if p_live else f"(名簿は{SNAPSHOT_DATE}時点)"))

    @st.cache_data(ttl=86400, show_spinner=False)
    def cached_player_detail(url):
        from fetchers import fetch_player_detail
        return fetch_player_detail(url)

    @st.cache_data(ttl=86400, show_spinner=False)
    def cached_player_wiki(name):
        from fetchers import fetch_player_wiki
        return fetch_player_wiki(name)

    @st.dialog("選手詳細")
    def show_player(p_sel):
        p_url = getattr(p_sel, "url", "")
        diag = []
        head_html = (
            f'<div style="display:flex;align-items:center;gap:10px">'
            f'<span class="score-num" style="background:{GRAD_RED};color:#fff;font-size:19px;'
            f'border-radius:10px;min-width:44px;text-align:center;padding:8px 0">{p_sel.number}</span>'
            f'<div><div style="font-weight:900;font-size:17px">{p_sel.name}</div>'
            f'<div style="font-size:11px;color:{RED};font-weight:800">{p_sel.position}</div></div></div>'
        )
        links_html = (
            f'<div style="margin-top:8px;font-size:12.5px;line-height:2">'
            + (f'<a href="{p_url}" target="_blank" style="color:{RED};font-weight:700;'
               f'text-decoration:none">ゲキサカで出場成績を見る →</a><br>' if p_url else "")
            + f'<a href="https://www.google.com/search?q={p_sel.name}+コンサドーレ+経歴+成績" '
            f'target="_blank" style="color:{RED};font-weight:700;text-decoration:none">'
            f'経歴・成績を検索 →</a></div>'
        )
        body = None
        # ルート1: ゲキサカ
        if p_url:
            try:
                with st.spinner("経歴を取得中…"):
                    det = cached_player_detail(p_url)
                if det.get("birth") or det.get("career"):
                    age = ""
                    if det.get("birth"):
                        b = datetime.strptime(det["birth"], "%Y-%m-%d").date()
                        t = today_jst()
                        a = t.year - b.year - ((t.month, t.day) < (b.month, b.day))
                        age = f"({a}歳)"
                    rows = ""
                    for label, key, suffix in [("生年月日", "birth", f" {age}"),
                                               ("身長/体重", "body", ""),
                                               ("受賞歴", "awards", ""),
                                               ("代表歴", "natl", "")]:
                        if det.get(key):
                            rows += (f'<tr><td style="color:{GRAY};font-weight:700;width:76px;'
                                     f'padding:4px 0;vertical-align:top">{label}</td>'
                                     f'<td>{det[key]}{suffix}</td></tr>')
                    career_html = ""
                    if det.get("career"):
                        steps = det["career"].replace("−", "-").split("-")
                        chain = ' <span style="color:' + RED + '">→</span> '.join(
                            s.strip() for s in steps if s.strip())
                        career_html = (f'<div style="font-size:11px;color:{GRAY};font-weight:700;'
                                       f'margin-top:8px">経歴</div>'
                                       f'<div style="font-size:12.5px;line-height:1.9">{chain}</div>')
                    news_html = ""
                    if det.get("news"):
                        items = "".join(
                            f'<div style="font-size:12px;padding:3px 0;border-top:1px solid #eef0f2">'
                            f'<span style="color:{GRAY}">{n["date"]}</span> {n["title"]}</div>'
                            for n in det["news"])
                        news_html = (f'<div style="font-size:11px;color:{GRAY};font-weight:700;'
                                     f'margin-top:8px">関連ニュース</div>{items}')
                    body = (head_html
                            + f'<table style="width:100%;font-size:12.5px;'
                            f'border-collapse:collapse;margin-top:8px">{rows}</table>'
                            + career_html + news_html + links_html)
                else:
                    diag.append("ゲキサカ: データ項目が空")
            except Exception as e:
                diag.append(f"ゲキサカ: {type(e).__name__} {str(e)[:60]}")
        else:
            diag.append("ゲキサカ: URLなし(オフライン名簿)")
        # ルート2: Wikipedia
        if body is None:
            try:
                with st.spinner("経歴を取得中…"):
                    wiki = cached_player_wiki(p_sel.name)
                if wiki.get("extract"):
                    wiki_link = (f'<a href="{wiki["wiki_url"]}" target="_blank" '
                                 f'style="color:{RED};font-size:12px;font-weight:700;'
                                 f'text-decoration:none">Wikipediaで続きを読む →</a>'
                                 if wiki.get("wiki_url") else "")
                    body = (head_html
                            + f'<div style="font-size:13px;line-height:1.9;margin-top:8px">'
                            f'{wiki["extract"]}</div>{wiki_link}{links_html}')
                else:
                    diag.append("Wikipedia: 該当記事なし")
            except Exception as e:
                diag.append(f"Wikipedia: {type(e).__name__} {str(e)[:60]}")
        # ルート3: リンク集
        if body is None:
            body = (head_html
                    + f'<div style="font-size:12.5px;color:{GRAY};margin-top:8px">'
                    f'経歴データを取得できませんでした。以下からご覧ください。</div>'
                    + links_html)
        if diag and body and "取得できませんでした" in body:
            body += (f'<div style="font-size:10px;color:#b9bdc4;margin-top:8px;'
                     f'font-family:monospace">診断: {" / ".join(diag)}</div>')
        st.markdown(card(body, mb="0"), unsafe_allow_html=True)

    # --- 名簿(タップでポップアップ) ---
    for pos, label in [("GK", "ゴールキーパー"), ("DF", "ディフェンダー"),
                       ("MF", "ミッドフィールダー"), ("FW", "フォワード")]:
        idx = [i for i, p in enumerate(players) if p.position == pos]
        if not idx:
            continue
        st.markdown(
            f'<div style="margin:10px 0 4px"><span style="background:{RED};color:#fff;'
            f'font-size:11px;font-weight:900;border-radius:4px;padding:3px 10px">{pos}</span> '
            f'<span style="font-size:12px;color:{GRAY};font-weight:700">{label}({len(idx)}名)</span></div>',
            unsafe_allow_html=True,
        )
        for row_start in range(0, len(idx), 2):
            cols = st.columns(2)
            for col, i in zip(cols, idx[row_start:row_start + 2]):
                p = players[i]
                if col.button(f":red[{p.number}]  **{p.name}**", key=f"pl_{i}",
                              width="stretch"):
                    show_player(p)

# ============ 分析 ============
with tabs[5]:
    st.markdown("### アナリストの視点")

    # --- クラブの現在地(複数年の文脈) ---
    st.markdown(card(
        f'<b style="font-size:13.5px;color:{PINK}">クラブの現在地 — 再建2年目の勝負</b>'
        f'<div style="font-size:12.5px;line-height:1.9;margin-top:6px">'
        f'2017〜24年に<b>8季連続でJ1に在籍</b>したが、2024年に19位で降格。'
        f'昇格を狙った2025年は<b>12位(16勝5分17敗・50得点63失点)</b>と失速し、'
        f'長期政権だったミシャ式攻撃サッカーからの転換を迫られた。'
        f'2026年、鳥栖などを指揮した<b style="color:{RED}">川井健太監督</b>が就任(1年目)。'
        f'ボールを保持しつつ守備を作り直す路線で、特別シーズン後半に手応えを掴んだ。'
        f'秋春制元年の2026/27は<b>「1年でのJ1復帰」</b>が至上命題となる。</div>'
    ), unsafe_allow_html=True)

    # --- 昨季との比較(1試合平均) ---
    SP_GF = sum(int(m[3].split(" ")[0].split("-")[0]) for m in SEASON_SP)
    SP_GA = sum(int(m[3].split(" ")[0].split("-")[1]) for m in SEASON_SP)
    SP_PTS = sum(PTS[m[4]] for m in SEASON_SP)
    N = len(SEASON_SP)
    Y25 = {"pts": 53, "gp": 38, "gf": 50, "ga": 63}  # 2025年J2実績
    st.markdown(card(
        f'<b style="font-size:13.5px">昨季2025 → 2026特別シーズンの変化(1試合平均)</b>'
        f'<table style="width:100%;font-size:13px;margin-top:6px;border-collapse:collapse;text-align:center">'
        f'<tr style="color:{GRAY};font-size:11px"><td></td><td>勝点</td><td>得点</td><td>失点</td></tr>'
        f'<tr><td style="text-align:left;font-weight:700">2025(J2・12位)</td>'
        f'<td>{Y25["pts"]/Y25["gp"]:.2f}</td><td>{Y25["gf"]/Y25["gp"]:.2f}</td>'
        f'<td>{Y25["ga"]/Y25["gp"]:.2f}</td></tr>'
        f'<tr style="color:{RED};font-weight:800"><td style="text-align:left">2026特別(川井体制)</td>'
        f'<td>{SP_PTS/N:.2f}</td><td>{SP_GF/N:.2f}</td><td>{SP_GA/N:.2f}</td></tr></table>'
        f'<div style="font-size:12px;color:{GRAY};margin-top:6px">'
        f'最大の変化は<b style="color:{TXT}">守備(失点{Y25["ga"]/Y25["gp"]:.2f}→{SP_GA/N:.2f})</b>。'
        f'昨季の「打ち合って失速」から、完封{sum(1 for m in SEASON_SP if int(m[3].split(" ")[0].split("-")[1]) == 0)}試合の'
        f'「勝ち切れるチーム」へ体質が変わりつつある。</div>'
    ), unsafe_allow_html=True)

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
        f'<div style="flex:1;background:#22060b;border:1px solid #3a1218;border-radius:12px;padding:9px">'
        f'<div style="font-size:10.5px;font-weight:800;color:{PINK}">ホーム {len(hm)}試合</div>'
        f'<div class="score-num" style="font-size:21px;color:#FF3B55">勝点{ph}</div>'
        f'<div style="font-size:10.5px;color:{GRAY}">得{gfh}/失{gah}</div></div>'
        f'<div style="flex:1;background:{CARD_BG};border:1px solid {CARD_BD};border-radius:12px;padding:9px">'
        f'<div style="font-size:10.5px;font-weight:800;color:{GRAY}">アウェイ {len(aw)}試合</div>'
        f'<div class="score-num" style="font-size:21px;color:{TXT}">勝点{pa}</div>'
        f'<div style="font-size:10.5px;color:{GRAY}">得{gfa}/失{gaa}</div></div>'
        f'<div style="flex:1;background:{GRAD_RED};border-radius:12px;padding:9px;color:#fff;'
        f'box-shadow:0 2px 14px rgba(232,17,45,.4)">'
        f'<div style="font-size:10.5px;font-weight:800">完封</div>'
        f'<div class="score-num" style="font-size:21px">{cs}試合</div>'
        f'<div style="font-size:10.5px;opacity:.85">/20試合</div></div></div>'
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
        width="stretch", hide_index=True, height=350,
    )

    st.markdown("### リーグ成績の推移")
    st.dataframe(
        pd.DataFrame([{"年": y, "リーグ": lg, "順位": f"{r}位"} for y, lg, r in HISTORY]),
        width="stretch", hide_index=True,
    )
    st.caption("J2優勝3回(2000・2007・2016)/ J1最高4位(2018)/ 2017〜24年に8季連続J1在籍")

st.caption("コンサ情報ボード v2.2 — Stadium Night Edition")

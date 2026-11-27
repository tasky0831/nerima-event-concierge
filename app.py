from datetime import datetime
import hmac
import html
import re
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="近所のイベントコンシェルジュ",
    page_icon="📍",
    layout="centered",
    initial_sidebar_state="collapsed",
)

APP_TITLE = "近所のイベントコンシェルジュ"
JST = ZoneInfo("Asia/Tokyo")
NEW_BADGE_DAYS = 3

EXPECTED_KEYS = [
    "event_id",
    "area_type",
    "category",
    "title",
    "event_date",
    "location",
    "booking_info",
    "baby_point",
    "source_url",
    "added_date",
]

AREA_OPTIONS = ["すべて", "近所", "電車", "車お出かけ"]
CATEGORIES = ["商業施設", "公園・自然", "テーマパーク", "地域・グルメ"]


def render_app_title() -> None:
    """アプリタイトルを通常の約2/3サイズで表示する。"""
    st.markdown(
        f'<h1 style="font-size: 1.5rem; font-weight: 700; line-height: 1.3; margin: 0 0 0.5rem 0;">{html.escape(APP_TITLE)}</h1>',
        unsafe_allow_html=True,
    )


def check_authentication() -> bool:
    """簡易パスワード認証を行い、認証済みならTrueを返す。"""
    if st.session_state.get("authenticated", False):
        return True

    render_app_title()
    st.caption("閲覧するにはパスワードを入力してください。")

    try:
        app_password = str(st.secrets["APP_PASSWORD"])
    except Exception:
        st.error(
            "アプリの設定（APP_PASSWORD）が読み込めませんでした。"
            "Secretsの設定を確認してください。"
        )
        return False

    with st.form("login_form"):
        password_input = st.text_input("パスワード", type="password")
        submitted = st.form_submit_button("ログイン", use_container_width=True)

    if submitted:
        if hmac.compare_digest(password_input, app_password):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("パスワードが正しくありません。")

    return False


def parse_added_datetime(value: str) -> pd.Timestamp:
    """added_date文字列をJSTのnaive Timestampに変換する。変換不可はNaT。"""
    raw = str(value or "").strip()
    if not raw:
        return pd.NaT

    ts = pd.to_datetime(raw, errors="coerce")
    if pd.isna(ts):
        return pd.NaT

    if ts.tzinfo is not None:
        ts = ts.tz_convert(JST).tz_localize(None)
    return ts


def format_added_date(raw_value: str, parsed_ts: pd.Timestamp) -> str:
    """画面表示用の更新日時文字列を返す。"""
    if pd.isna(parsed_ts):
        return raw_value.strip() if raw_value.strip() else "記載なし"
    if parsed_ts.hour == 0 and parsed_ts.minute == 0 and parsed_ts.second == 0:
        return parsed_ts.strftime("%Y/%m/%d")
    return parsed_ts.strftime("%Y/%m/%d %H:%M")


def is_new_event(parsed_ts: pd.Timestamp, today_jst) -> bool:
    """直近3日以内に追加されたイベントならTrueを返す。"""
    if pd.isna(parsed_ts):
        return False
    delta_days = (today_jst - parsed_ts.date()).days
    return 0 <= delta_days <= NEW_BADGE_DAYS


def extract_station(location: str, station_col: str = "") -> str:
    """駅名を抽出する（station列があれば優先、なければlocationから抽出）。"""
    if station_col.strip():
        return station_col.strip()
    loc = str(location or "").strip()
    if not loc:
        return ""
    match = re.search(r"([^\s（(「『・、,]+駅)", loc)
    if match:
        return match.group(1)
    return ""


@st.cache_data(ttl=600, show_spinner="最新のイベント情報を取得しています...")
def fetch_events(gas_url: str) -> pd.DataFrame:
    """GAS WebアプリURLからJSON配列を取得し、DataFrameとして返す。"""
    response = requests.get(gas_url, timeout=15)
    response.raise_for_status()

    data = response.json()
    if not isinstance(data, list):
        raise ValueError("GASからのレスポンスがJSON配列ではありません。")

    if not data:
        return pd.DataFrame(columns=EXPECTED_KEYS + ["station"])

    normalized_rows = []
    for item in data:
        if not isinstance(item, dict):
            continue
        row = {key: str(item.get(key) or "").strip() for key in EXPECTED_KEYS}
        row["station"] = str(item.get("station") or "").strip()
        normalized_rows.append(row)

    return pd.DataFrame(normalized_rows, columns=EXPECTED_KEYS + ["station"])


def is_booking_not_required(booking_info: str) -> bool:
    text = booking_info.strip()
    return "不要" in text or "予約なし" in text or "申込不要" in text


def is_booking_required(booking_info: str) -> bool:
    text = booking_info.strip()
    if not text or is_booking_not_required(text):
        return False
    return "要予約" in text or "予約" in text or "申込" in text or "必要" in text


def render_badges(area_type: str, category: str, is_new: bool) -> None:
    area_escaped = html.escape(area_type or "エリア未設定")
    cat_escaped = html.escape(category or "カテゴリ未設定")

    if area_type == "近所":
        area_bg, area_fg = "#E8F4FD", "#0B5394"
    elif area_type == "電車":
        area_bg, area_fg = "#F3E8FF", "#6B21A8"
    else:
        area_bg, area_fg = "#EAF7EE", "#1E6B3A"

    new_badge_html = ""
    if is_new:
        new_badge_html = (
            '<span style="background:#EF4444; color:#FFFFFF; padding:3px 10px;'
            ' border-radius:999px; font-size:0.78rem; font-weight:700;'
            ' letter-spacing:0.04em;">NEW</span>'
        )

    badges_html = "".join(
        [
            '<div style="display:flex; flex-wrap:wrap; align-items:center; gap:6px; margin-bottom:4px;">',
            new_badge_html,
            f'<span style="background:{area_bg}; color:{area_fg}; padding:3px 10px; border-radius:999px; font-size:0.8rem; font-weight:600;">{area_escaped}</span>',
            f'<span style="background:#F3F4F6; color:#374151; padding:3px 10px; border-radius:999px; font-size:0.8rem; font-weight:600;">{cat_escaped}</span>',
            "</div>",
        ]
    )
    st.markdown(badges_html, unsafe_allow_html=True)


def main() -> None:
    if not check_authentication():
        st.stop()

    render_app_title()

    if st.button("🔄 最新情報に更新", use_container_width=True):
        fetch_events.clear()
        st.rerun()

    try:
        gas_url = str(st.secrets["GAS_API_URL"]).strip()
    except Exception:
        st.error(
            "データ取得先のURL（GAS_API_URL）が設定されていません。"
            "Secretsの設定を確認してください。"
        )
        st.stop()

    if not gas_url:
        st.error("GAS_API_URLが空です。Secretsの設定を確認してください。")
        st.stop()

    try:
        df = fetch_events(gas_url)
    except requests.exceptions.Timeout:
        st.error("データ取得がタイムアウトしました。時間をおいて再度お試しください。")
        st.stop()
    except requests.exceptions.RequestException as e:
        st.error(f"イベントデータの取得中に通信エラーが発生しました: {e}")
        st.stop()
    except ValueError as e:
        st.error(f"取得したデータの形式が正しくありません: {e}")
        st.stop()
    except Exception as e:
        st.error(f"予期しないエラーが発生しました: {e}")
        st.stop()

    if df.empty:
        st.info("現在表示できるイベントデータがありません。")
        st.stop()

    today_jst = datetime.now(JST).date()
    df = df.copy()
    df["_added_ts"] = df["added_date"].apply(parse_added_datetime)
    df["_is_new"] = df["_added_ts"].apply(lambda ts: is_new_event(ts, today_jst))
    df["_added_display"] = df.apply(
        lambda r: format_added_date(r["added_date"], r["_added_ts"]), axis=1
    )
    df["_station_key"] = df.apply(
        lambda r: extract_station(r["location"], r["station"]), axis=1
    )

    with st.expander("絞り込み検索", expanded=True):
        area_filter = st.radio(
            "エリア区分",
            options=AREA_OPTIONS,
            horizontal=True,
        )

        available_categories = list(
            dict.fromkeys(CATEGORIES + [c for c in df["category"].unique() if c])
        )
        category_filter = st.multiselect(
            "カテゴリ",
            options=available_categories,
            default=CATEGORIES,
        )

        booking_filter = st.selectbox(
            "予約条件",
            options=["すべて", "予約不要のみ", "要予約のみ"],
        )

        keyword = st.text_input(
            "キーワード検索",
            placeholder="イベント名・場所・0歳児ポイントから検索",
        ).strip()

        sort_option = st.selectbox(
            "並び替え",
            options=[
                "更新日時（新しい順）",
                "更新日時（古い順）",
                "駅順",
                "標準（データ順）",
            ],
            index=0,
        )

    filtered = df.copy()

    if area_filter != "すべて":
        filtered = filtered[filtered["area_type"] == area_filter]

    if category_filter:
        filtered = filtered[filtered["category"].isin(category_filter)]
    else:
        filtered = filtered.iloc[0:0]

    if booking_filter == "予約不要のみ":
        filtered = filtered[filtered["booking_info"].apply(is_booking_not_required)]
    elif booking_filter == "要予約のみ":
        filtered = filtered[filtered["booking_info"].apply(is_booking_required)]

    if keyword:
        kw_lower = keyword.lower()
        mask = (
            filtered["title"].str.lower().str.contains(kw_lower, na=False, regex=False)
            | filtered["location"].str.lower().str.contains(kw_lower, na=False, regex=False)
            | filtered["baby_point"].str.lower().str.contains(kw_lower, na=False, regex=False)
        )
        filtered = filtered[mask]

    if sort_option == "更新日時（新しい順）":
        filtered = filtered.sort_values(
            by="_added_ts", ascending=False, na_position="last", kind="mergesort"
        )
    elif sort_option == "更新日時（古い順）":
        filtered = filtered.sort_values(
            by="_added_ts", ascending=True, na_position="last", kind="mergesort"
        )
    elif sort_option == "駅順":
        filtered["_has_station"] = filtered["_station_key"].apply(lambda s: 0 if s else 1)
        filtered["_sort_station"] = filtered.apply(
            lambda r: r["_station_key"] if r["_station_key"] else r["location"],
            axis=1,
        )
        filtered = filtered.sort_values(
            by=["_has_station", "_sort_station", "_added_ts"],
            ascending=[True, True, False],
            na_position="last",
            kind="mergesort",
        )

    new_count = int(filtered["_is_new"].sum()) if not filtered.empty else 0
    if new_count > 0:
        st.markdown(f"**該当件数：{len(filtered)}件**（うち **NEW：{new_count}件**）")
    else:
        st.markdown(f"**該当件数：{len(filtered)}件**")

    if filtered.empty:
        st.info("条件に一致するイベントが見つかりませんでした。絞り込み条件を変更してみてください。")
        return

    for _, row in filtered.iterrows():
        with st.container(border=True):
            render_badges(row["area_type"], row["category"], bool(row["_is_new"]))
            event_title = html.escape(row["title"] or "（タイトルなし）")
            st.markdown(
                f'<h3 style="font-size: 1.15rem; font-weight: 700; line-height: 1.35; margin: 0.25rem 0 0.5rem 0;">{event_title}</h3>',
                unsafe_allow_html=True,
            )

            st.markdown(
                f"- **開催日時**：{row['event_date'] or '未定'}\n"
                f"- **場所**：{row['location'] or '未定'}\n"
                f"- **予約情報**：{row['booking_info'] or '記載なし'}\n"
                f"- **更新日時**：{row['_added_display']}"
            )

            if row["baby_point"]:
                st.info(f"👶 **0歳児ポイント**\n\n{row['baby_point']}")

            source_url = row["source_url"]
            if source_url.startswith(("http://", "https://")):
                st.link_button(
                    "公式サイト・詳細を見る",
                    source_url,
                    use_container_width=True,
                )


if __name__ == "__main__":
    main()

import hmac
import html
import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="練馬・車お出かけ イベントコンシェルジュ",
    page_icon="🚗",
    layout="centered",
    initial_sidebar_state="collapsed",
)

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
]

CATEGORIES = ["商業施設", "公園・自然", "テーマパーク", "地域・グルメ"]


def check_authentication() -> bool:
    """簡易パスワード認証を行い、認証済みならTrueを返す。"""
    if st.session_state.get("authenticated", False):
        return True

    st.title("🚗 練馬・車お出かけ イベントコンシェルジュ")
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


@st.cache_data(ttl=600, show_spinner="最新のイベント情報を取得しています...")
def fetch_events(gas_url: str) -> pd.DataFrame:
    """GAS WebアプリURLからJSON配列を取得し、DataFrameとして返す。"""
    response = requests.get(gas_url, timeout=15)
    response.raise_for_status()

    data = response.json()
    if not isinstance(data, list):
        raise ValueError("GASからのレスポンスがJSON配列ではありません。")

    if not data:
        return pd.DataFrame(columns=EXPECTED_KEYS)

    normalized_rows = []
    for item in data:
        if not isinstance(item, dict):
            continue
        row = {key: str(item.get(key) or "").strip() for key in EXPECTED_KEYS}
        normalized_rows.append(row)

    return pd.DataFrame(normalized_rows, columns=EXPECTED_KEYS)


def is_booking_not_required(booking_info: str) -> bool:
    text = booking_info.strip()
    return "不要" in text or "予約なし" in text or "申込不要" in text


def is_booking_required(booking_info: str) -> bool:
    text = booking_info.strip()
    if not text or is_booking_not_required(text):
        return False
    return "要予約" in text or "予約" in text or "申込" in text or "必要" in text


def render_badges(area_type: str, category: str) -> None:
    area_escaped = html.escape(area_type or "エリア未設定")
    cat_escaped = html.escape(category or "カテゴリ未設定")

    area_bg = "#E8F4FD" if area_type == "近所" else "#EAF7EE"
    area_fg = "#0B5394" if area_type == "近所" else "#1E6B3A"

    st.markdown(
        f"""
        <div style="display:flex; flex-wrap:wrap; gap:6px; margin-bottom:4px;">
            <span style="background:{area_bg}; color:{area_fg}; padding:3px 10px;
                         border-radius:999px; font-size:0.8rem; font-weight:600;">
                {area_escaped}
            </span>
            <span style="background:#F3F4F6; color:#374151; padding:3px 10px;
                         border-radius:999px; font-size:0.8rem; font-weight:600;">
                {cat_escaped}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    if not check_authentication():
        st.stop()

    st.title("🚗 練馬・車お出かけ イベントコンシェルジュ")

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

    with st.expander("絞り込み検索", expanded=True):
        area_filter = st.radio(
            "エリア区分",
            options=["すべて", "近所", "車お出かけ"],
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

    st.markdown(f"**該当件数：{len(filtered)}件**")

    if filtered.empty:
        st.info("条件に一致するイベントが見つかりませんでした。絞り込み条件を変更してみてください。")
        return

    for _, row in filtered.iterrows():
        with st.container(border=True):
            render_badges(row["area_type"], row["category"])
            st.markdown(f"### {row['title'] or '（タイトルなし）'}")

            st.markdown(
                f"- **開催日時**：{row['event_date'] or '未定'}\n"
                f"- **場所**：{row['location'] or '未定'}\n"
                f"- **予約情報**：{row['booking_info'] or '記載なし'}"
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

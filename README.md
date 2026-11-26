# 近所のイベントコンシェルジュ

Google Apps Script（GAS）のWebアプリURLからイベントデータをJSON形式で取得し、iPhoneのSafariから快適に閲覧・絞り込みができるStreamlit Webアプリです。

## ファイル構成

- `app.py`：Streamlitアプリ本体（パスワード認証、GASデータ取得・キャッシュ、モバイル最適化カードUI）
- `requirements.txt`：依存パッケージ一覧（`streamlit`, `pandas`, `requests`）
- `.gitignore`：機密情報（`.streamlit/secrets.toml`）やキャッシュ（`__pycache__/`）を除外
- `README.md`：セットアップおよびデプロイ手順

## GASから返却するJSON仕様

`GAS_API_URL` へのGETリクエストで、以下のキーを持つオブジェクトの配列（JSON配列）を返すように構成してください。

- `event_id`
- `area_type`（例：`近所` / `車お出かけ`）
- `category`（例：`商業施設` / `公園・自然` / `テーマパーク` / `地域・グルメ`）
- `title`
- `event_date`
- `location`
- `booking_info`
- `baby_point`
- `source_url`

## Streamlit Community Cloud でのデプロイ手順

1. 本リポジトリをGitHubにプッシュします。
2. [Streamlit Community Cloud](https://share.streamlit.io/) にGitHubアカウントでサインインします。
3. **Create app**（または **New app**）をクリックし、以下を指定します。
   - **Repository**：`nerima-event-concierge`
   - **Branch**：`main`
   - **Main file path**：`app.py`
4. デプロイ画面の **Advanced settings...**（またはデプロイ後のアプリメニュー **Settings → Secrets**）を開きます。
5. 以下の形式で **Secrets** を設定し、保存（Save）して **Deploy** を実行します。

```toml
APP_PASSWORD = "your_secure_password"
GAS_API_URL = "https://script.google.com/macros/s/XXXXXXXXXXXXXXXXXXXXXXXX/exec"
```

## ローカル実行方法

1. リポジトリ直下に `.streamlit/secrets.toml` を作成し、上記の `APP_PASSWORD` と `GAS_API_URL` を記述します（`.gitignore` によりGitにはコミットされません）。
2. 依存パッケージをインストールして起動します。

```bash
pip install -r requirements.txt
streamlit run app.py
```

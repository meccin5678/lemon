# -*- coding: utf-8 -*-
"""
Render 無料プラン向け 最小構成「レシピ投稿ミニアプリ」
- Flask 3 + SQLAlchemy 2 + Render PostgreSQL（DATABASE_URL）
- 単一ファイル構成（app.py）
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Optional, List

from dotenv import load_dotenv  # .env から環境変数読込（無ければ無視される）
from flask import Flask, request, redirect, url_for, render_template_string
from sqlalchemy import (
    create_engine, String, Integer, Text, DateTime, CheckConstraint, func
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session

# ==============================
# 環境変数の読み込み
# ==============================
load_dotenv()  # ローカル実行時のみ有効（Render 本番では不要だが無害）

# ==============================
# DB 接続ユーティリティ
# ==============================
def get_database_url() -> Optional[str]:
    """
    DATABASE_URL を取得し、Render の "postgres://" を SQLAlchemy 用に
    "postgresql+psycopg2://" へ置換する。
    """
    url = os.environ.get("DATABASE_URL")
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    return url

DATABASE_URL = get_database_url()
if not DATABASE_URL:
    # Render 以外の実行（ローカルなど）で未設定の場合はエラーメッセージを出すため、
    # あえて None のまま進める（ページ上で案内表示）
    pass

# SQLAlchemy エンジン（DB 接続）
engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None

# ==============================
# モデル定義
# ==============================
class Base(DeclarativeBase):
    pass

class Recipe(Base):
    """
    recipes テーブル
    - id:        整数PK, autoincrement
    - title:     文字列(<=200), 必須
    - minutes:   整数, 必須, 1以上
    - description: テキスト, 任意
    - created_at: 作成日時(UTC想定), デフォルト現在時刻
    """
    __tablename__ = "recipes"
    __table_args__ = (
        CheckConstraint("minutes >= 1", name="ck_recipes_minutes_ge_1"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # DBサーバ側で現在時刻を入れる。タイムゾーン付きでも問題なし。
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

# 起動時にテーブル自動作成（DB 未設定時はスキップ）
if engine is not None:
    Base.metadata.create_all(engine)

# ==============================
# Flask アプリ本体
# ==============================
app = Flask(__name__)

# 1ページ構成（一覧 + 新規追加フォーム）
PAGE_TEMPLATE = """
<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>レシピ投稿ミニアプリ</title>
<style>
  body { font-family: system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial, "Noto Sans JP", sans-serif; margin: 2rem; color:#222; }
  h1 { margin-bottom: 0.5rem; }
  .notice { padding: 0.75rem 1rem; background:#fff3cd; border:1px solid #ffeeba; border-radius:8px; margin:1rem 0; }
  .errors { padding: 0.75rem 1rem; background:#f8d7da; border:1px solid #f5c6cb; color:#721c24; border-radius:8px; margin:1rem 0; }
  form { display: grid; gap: 0.75rem; max-width: 520px; margin: 1rem 0 2rem; }
  label { font-weight: 600; }
  input[type="text"], input[type="number"], textarea {
    width: 100%; padding: 0.6rem 0.7rem; border:1px solid #ccc; border-radius:8px; font-size: 1rem;
  }
  textarea { min-height: 120px; }
  .btn { display:inline-block; padding:0.6rem 1rem; background:#0969da; color:#fff; border:none; border-radius:8px; cursor:pointer; font-weight:600; }
  .btn:hover { background:#0757b3; }
  .list { margin-top: 1rem; }
  .card { border:1px solid #e5e7eb; border-radius:12px; padding:1rem; margin:0.5rem 0; background:#fff; }
  .meta { color:#555; font-size:0.9rem; margin-top:0.25rem; }
  .empty { color:#666; }
  .footer { margin-top:2rem; color:#666; font-size:0.9rem; }
</style>
</head>
<body>
  <h1>レシピ投稿ミニアプリ</h1>
  <p>「タイトル」「所要分数」「説明」を入力して投稿してください。投稿後は一覧の先頭に表示されます。</p>

  {% if not db_ready %}
    <div class="notice">
      <strong>DB未設定：</strong> 環境変数 <code>DATABASE_URL</code> が見つかりません。<br>
      ローカルでは .env に <code>DATABASE_URL=...</code> を設定してください。Render では Web Service の Environment Variables に設定します。
    </div>
  {% endif %}

  {% if errors %}
    <div class="errors">
      <div><strong>入力エラーがあります：</strong></div>
      <ul>
        {% for e in errors %}
        <li>{{ e }}</li>
        {% endfor %}
      </ul>
    </div>
  {% endif %}

  <form method="post" action="{{ url_for('index') }}">
    <div>
      <label for="title">タイトル（必須・200文字まで）</label>
      <input id="title" name="title" type="text" maxlength="200" required value="{{ form_values.title }}">
    </div>
    <div>
      <label for="minutes">所要分数（必須・整数・1以上）</label>
      <input id="minutes" name="minutes" type="number" step="1" min="1" required value="{{ form_values.minutes }}">
    </div>
    <div>
      <label for="description">説明（任意）</label>
      <textarea id="description" name="description">{{ form_values.description }}</textarea>
    </div>
    <div>
      <button class="btn" type="submit">投稿する</button>
    </div>
  </form>

  <h2>レシピ一覧</h2>
  <div class="list">
    {% if recipes %}
      {% for r in recipes %}
        <div class="card">
          <div><strong>{{ r.title }}</strong></div>
          <div class="meta">所要分数: {{ r.minutes }} 分 / 投稿日時(UTC): {{ r.created_at }}</div>
          {% if r.description %}
            <div style="margin-top:0.5rem; white-space:pre-wrap;">{{ r.description }}</div>
          {% endif %}
        </div>
      {% endfor %}
    {% else %}
      <div class="empty">投稿はまだありません。最初のレシピを投稿してみましょう！</div>
    {% endif %}
  </div>

  <div class="footer">
    <code>DEBUG={{ debug|lower }}</code> / <code>PORT={{ port }}</code>
  </div>
</body>
</html>
"""

def _to_bool_env(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

@app.route("/", methods=["GET", "POST"])
def index():
    """
    GET: 一覧 + フォーム表示
    POST: バリデーション → 保存（成功時 PRG でリダイレクト）/ 失敗時は同ページにエラー表示
    """
    errors: List[str] = []
    form_values = {
        "title": "",
        "minutes": "",
        "description": "",
    }

    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        minutes_raw = (request.form.get("minutes") or "").strip()
        description = (request.form.get("description") or "").strip()

        form_values["title"] = title
        form_values["minutes"] = minutes_raw
        form_values["description"] = description

        # --- 入力バリデーション（日本語メッセージ） ---
        if not title:
            errors.append("タイトルは必須です。")
        if len(title) > 200:
            errors.append("タイトルは200文字以内で入力してください。")

        minutes_val: Optional[int] = None
        if not minutes_raw:
            errors.append("所要分数は必須です。")
        else:
            try:
                minutes_val = int(minutes_raw)
                if minutes_val < 1:
                    errors.append("所要分数は1以上の整数で入力してください。")
            except ValueError:
                errors.append("所要分数は整数で入力してください。")

        # DB 未設定のときは保存不可だが、ユーザーに案内する
        if engine is None:
            errors.append("データベースが未設定のため保存できません。DATABASE_URL を設定してください。")

        if not errors and engine is not None and minutes_val is not None:
            # --- 保存処理（SQLAlchemy 2系 / コンテキストマネージャで明示コミット） ---
            try:
                with Session(engine) as session:
                    item = Recipe(title=title, minutes=minutes_val, description=description or None)
                    session.add(item)
                    session.commit()
                # 成功時は PRG（Post/Redirect/Get）
                return redirect(url_for("index"))
            except Exception as e:
                # 例外時は簡易エラーメッセージ（本番ではロギング推奨）
                errors.append("保存中にエラーが発生しました。入力内容を確認のうえ、再度お試しください。")
                # 具体的な例外内容は学習用にコメントアウト（必要に応じて表示可）
                # errors.append(str(e))

    # --- 一覧表示（新しい順） ---
    recipes: List[Recipe] = []
    if engine is not None:
        try:
            with Session(engine) as session:
                recipes = session.query(Recipe).order_by(Recipe.created_at.desc(), Recipe.id.desc()).all()
        except Exception:
            # DB が未初期化／接続失敗時などは静かに空リスト表示
            recipes = []

    # ページ描画
    port = int(os.environ.get("PORT", "8000"))
    debug = _to_bool_env(os.environ.get("DEBUG"), default=False)
    return render_template_string(
        PAGE_TEMPLATE,
        errors=errors,
        recipes=recipes,
        debug=str(debug),
        port=port,
        db_ready=(engine is not None),
        form_values=form_values,
    )

# ==============================
# アプリ起動
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    debug = _to_bool_env(os.environ.get("DEBUG"), default=False)
    # 0.0.0.0/PORT は PaaS 共通要件。Render でもこのままOK。
    app.run(host="0.0.0.0", port=port, debug=debug)

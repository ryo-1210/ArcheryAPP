# =====================================================
# Google Sheets / Drive 連携モジュール
# =====================================================

import io
from datetime import datetime

import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# -----------------------------------------------------
# 設定(実際の値に置き換えてください)
# -----------------------------------------------------
SPREADSHEET_NAME = "archery_records"  # 使用するスプレッドシートの名前
DRIVE_FOLDER_ID = "1Idd2BL62cCFZBSB8Sv8wzsopXwCG41lR"  # 画像保存先のGoogle DriveフォルダID

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# スプレッドシートの列構成(この順番で1行が記録される)
COLUMNS = [
    "timestamp",
    "user_id",
    "target_size_cm",
    "arrow_count",
    "scores",          # カンマ区切り
    "coords_x",         # カンマ区切り
    "coords_y",         # カンマ区切り
    "total_score",
    "centroid_x",
    "centroid_y",
    "spread",
    "offset_x",
    "offset_y",
    "left_image_drive_id",
    "right_image_drive_id",
]


# -----------------------------------------------------
# 認証(Streamlit Secretsから読み込む)
# -----------------------------------------------------
@st.cache_resource
def get_credentials():
    info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    return creds


@st.cache_resource
def get_gspread_client():
    creds = get_credentials()
    return gspread.authorize(creds)


@st.cache_resource
def get_drive_service():
    creds = get_credentials()
    return build("drive", "v3", credentials=creds)


# -----------------------------------------------------
# スプレッドシート操作
# -----------------------------------------------------
def get_worksheet():
    """スプレッドシートを開く。シートが無ければヘッダー付きで新規作成する"""
    client = get_gspread_client()
    sh = client.open(SPREADSHEET_NAME)
    worksheet = sh.sheet1

    # 1行目が空ならヘッダーを書き込む
    first_row = worksheet.row_values(1)
    if not first_row:
        worksheet.append_row(COLUMNS)

    return worksheet


def append_record(record: dict):
    """
    1件のデータをスプレッドシートに追加する。
    record: COLUMNSのキーを持つ辞書

    注: value_input_option="RAW"を指定することで、
    "5,3,3,0,0"のようなカンマ区切り文字列や"001"のようなID文字列が
    Google Sheets側で数値に変換されてしまうのを防ぐ。
    """
    worksheet = get_worksheet()
    row = [record.get(col, "") for col in COLUMNS]
    worksheet.append_row(row, value_input_option="RAW")


def fetch_all_records(user_id: str = None):
    """
    全レコードを取得する。user_idを指定すればそのIDのみに絞り込む。
    戻り値: 辞書のリスト

    注: gspreadはスプレッドシート上の'001のような文字列を、
    読み取り時に数値の1に変換してしまうことがあるため、
    比較前に3桁ゼロパディングして文字列として正規化する。
    """
    worksheet = get_worksheet()
    records = worksheet.get_all_records()

    def normalize_id(value):
        """user_idを3桁ゼロパディングの文字列に正規化する"""
        s = str(value).strip()
        if s.isdigit():
            return s.zfill(3)
        return s

    def strip_leading_quote(value):
        """先頭にアポストロフィが紛れ込んでいた場合に除去する(保険処理)"""
        s = str(value)
        if s.startswith("'"):
            return s[1:]
        return s

    # 取得した全レコードのuser_idを正規化しておく(表示・比較の両方で使う)
    for r in records:
        r["user_id"] = normalize_id(strip_leading_quote(r.get("user_id", "")))
        # scoresが数値化されてしまっている場合に備え、文字列に変換しておく
        # (既にカンマ区切り文字列ならそのまま、数値化されていた場合はその数値文字列になる)
        r["scores"] = strip_leading_quote(r.get("scores", ""))

    if user_id:
        target = normalize_id(user_id)
        records = [r for r in records if r["user_id"] == target]

    return records


# -----------------------------------------------------
# Google Drive操作(画像保存)
# -----------------------------------------------------
# 注: サービスアカウントには個人Drive容量の割り当てがないため、
# Driveへの自動アップロードは無効化しています。
# 画像は登録時にダウンロードボタンで個別に保存する運用に変更しました。

def upload_image_to_drive(image_bytes: bytes, filename: str, folder_id: str = DRIVE_FOLDER_ID) -> str:
    """
    (現在は無効化中)画像をGoogle Driveにアップロードする。
    サービスアカウントの容量制限のため使用していません。
    """
    raise NotImplementedError("Drive自動アップロードは現在無効化されています")


def generate_image_filename(user_id: str, side: str, ext: str = "jpg") -> str:
    """Drive保存用のファイル名を生成する(日時+ID+左右の情報を含む)"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{user_id}_{side}.{ext}"

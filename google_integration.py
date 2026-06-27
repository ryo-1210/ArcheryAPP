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
    """
    worksheet = get_worksheet()
    row = [record.get(col, "") for col in COLUMNS]
    worksheet.append_row(row)


def fetch_all_records(user_id: str = None):
    """
    全レコードを取得する。user_idを指定すればそのIDのみに絞り込む。
    戻り値: 辞書のリスト
    """
    worksheet = get_worksheet()
    records = worksheet.get_all_records()

    if user_id:
        records = [r for r in records if str(r.get("user_id", "")) == str(user_id)]

    return records


# -----------------------------------------------------
# Google Drive操作(画像保存)
# -----------------------------------------------------
def upload_image_to_drive(image_bytes: bytes, filename: str, folder_id: str = DRIVE_FOLDER_ID) -> str:
    """
    画像をGoogle Driveにアップロードする。
    戻り値: アップロードされたファイルのDrive ID
    """
    service = get_drive_service()

    file_metadata = {
        "name": filename,
        "parents": [folder_id] if folder_id else [],
    }
    media = MediaIoBaseUpload(io.BytesIO(image_bytes), mimetype="image/jpeg", resumable=True)

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id",
    ).execute()

    return file.get("id")


def generate_image_filename(user_id: str, side: str, ext: str = "jpg") -> str:
    """Drive保存用のファイル名を生成する(日時+ID+左右の情報を含む)"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{timestamp}_{user_id}_{side}.{ext}"

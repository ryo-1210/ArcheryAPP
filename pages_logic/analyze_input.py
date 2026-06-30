# =====================================================
# 的解析 - 入力画面
# =====================================================

import numpy as np
import cv2
import streamlit as st
from ultralytics import YOLO

from archery_core import process_single_image, integrate_left_right

MODEL_PATH = "archery_best.pt"

USER_ID_OPTIONS = [f"{i:03d}" for i in range(1, 1000)]  # 001〜999
TARGET_SIZE_OPTIONS = [20, 40, 60, 80, 122]  # cm
DISTANCE_OPTIONS = [5, 10, 15, 18, 20, 25, 30, 50, 70, 90]  # m


@st.cache_resource
def load_model():
    return YOLO(MODEL_PATH)


def load_image_from_upload(uploaded_file):
    """StreamlitのUploadedFileをcv2画像(BGR ndarray)に変換する"""
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    return img


def render_analyze_input(go_to):
    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("⬅", use_container_width=True):
            go_to("top")
            st.rerun()
    with col_title:
        st.title("的解析")

    st.subheader("1枚目")
    left_file = st.file_uploader("1枚目の写真をアップロード", type=["jpg", "jpeg", "png"], key="left_upload")

    st.subheader("2枚目")
    right_file = st.file_uploader("2枚目の写真をアップロード", type=["jpg", "jpeg", "png"], key="right_upload")

    st.subheader("個人ID")
    user_id = st.selectbox("個人IDを選択", USER_ID_OPTIONS, key="user_id_select")

    col_size, col_dist = st.columns(2)
    with col_size:
        st.subheader("的紙サイズ")
        target_size = st.selectbox(
            "的紙サイズを選択(cm)",
            TARGET_SIZE_OPTIONS,
            index=2,  # デフォルト60cm
            key="target_size_select",
        )
        if target_size != 60:
            st.warning("現在のモデルは60cmの的紙での学習データのみのため、60cm以外は検出精度が低い可能性があります。")
    with col_dist:
        st.subheader("距離")
        distance = st.selectbox(
            "射距離を選択(m)",
            DISTANCE_OPTIONS,
            index=3,  # デフォルト18m
            key="distance_select",
            format_func=lambda x: f"{x}m",
        )

    st.text_area("メモ(任意)", placeholder="練習内容や条件などを記入できます", key="memo_input")

    st.write("")

    if left_file is not None and right_file is not None:
        if st.button("解析開始！", type="primary", use_container_width=True):
            with st.spinner("解析中です。1〜2分ほどかかります..."):
                try:
                    model = load_model()

                    left_img = load_image_from_upload(left_file)
                    right_img = load_image_from_upload(right_file)

                    left_points, left_log = process_single_image(model, left_img, label="1枚目")
                    right_points, right_log = process_single_image(model, right_img, label="2枚目")

                    final_points, integrate_log = integrate_left_right(left_points, right_points)

                except ValueError as e:
                    st.error(f"検出に失敗しました: {e}")
                    st.stop()

            # 結果をセッションに保存して編集画面に渡す
            st.session_state.left_points = left_points
            st.session_state.right_points = right_points
            st.session_state.final_points = final_points
            st.session_state.left_log = left_log
            st.session_state.right_log = right_log
            st.session_state.integrate_log = integrate_log

            st.session_state.left_image_bytes = left_file.getvalue()
            st.session_state.right_image_bytes = right_file.getvalue()

            st.session_state.user_id = user_id
            st.session_state.target_size = target_size
            st.session_state.distance = distance
            st.session_state.memo = st.session_state.get("memo_input", "")

            # 編集対象は初期状態として「左右統合」の結果を使う
            st.session_state.edit_points = list(map(list, final_points))
            st.session_state.selected_arrow_idx = None

            go_to("edit_result")
            st.rerun()
    else:
        st.info("1枚目・2枚目の両方をアップロードすると「解析開始！」ボタンが押せます。")

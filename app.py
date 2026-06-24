# =====================================================
# アーチェリー着弾点検出アプリ (Streamlit)
# =====================================================

import streamlit as st
import numpy as np
import cv2
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import japanize_matplotlib
from ultralytics import YOLO

from archery_core import (
    process_single_image,
    integrate_left_right,
    calculate_score,
    format_score,
    RING_RADII_CM,
    RING_COLORS,
    X_RING_RADIUS_CM,
    ARROW_DIAMETER_CM,
)

# -----------------------------------------------------
# ページ設定
# -----------------------------------------------------
st.set_page_config(page_title="アーチェリー着弾点プロット", layout="wide")

MODEL_PATH = "archery_best.pt"  # リポジトリ内に配置するモデルファイル


# -----------------------------------------------------
# モデルの読み込み(キャッシュして毎回の再読み込みを防ぐ)
# -----------------------------------------------------
@st.cache_resource
def load_model():
    return YOLO(MODEL_PATH)


# -----------------------------------------------------
# プロット描画関数
# -----------------------------------------------------
def draw_target(ax):
    for r, c in zip(reversed(RING_RADII_CM), reversed(RING_COLORS)):
        circle = patches.Circle((0, 0), r, facecolor=c, edgecolor='gray', linewidth=0.5, zorder=1)
        ax.add_patch(circle)

    x_circle = patches.Circle((0, 0), X_RING_RADIUS_CM, facecolor='none',
                               edgecolor='black', linewidth=1.0, zorder=2)
    ax.add_patch(x_circle)


def plot_points(points, title, color='blue'):
    fig, ax = plt.subplots(figsize=(6, 6))
    draw_target(ax)

    if len(points) > 0:
        points = np.array(points)
        arrow_radius = ARROW_DIAMETER_CM / 2

        for x, y in points:
            arrow_circle = patches.Circle((x, y), arrow_radius, facecolor=color,
                                          edgecolor='white', linewidth=1.2, zorder=5, alpha=0.9)
            ax.add_patch(arrow_circle)

        scores_and_x = [calculate_score(p) for p in points]
        total_score = sum(s for s, _ in scores_and_x)
        x_count = sum(1 for _, is_x in scores_and_x if is_x)
        score_labels = [format_score(s, x) for s, x in scores_and_x]

        info_text = f"合計点: {total_score} / 矢数: {len(points)} / X数: {x_count}"
        ax.text(0.02, 0.98, info_text, transform=ax.transAxes, va='top', fontsize=11,
               bbox=dict(facecolor='white', alpha=0.8))

        for (x, y), label in zip(points, score_labels):
            ax.annotate(label, (x, y), textcoords="offset points", xytext=(8, 8),
                       fontsize=9, color='black',
                       bbox=dict(facecolor='white', alpha=0.7, pad=1))

    ax.set_xlim(-32, 32)
    ax.set_ylim(-32, 32)
    ax.set_aspect('equal')
    ax.set_xlabel('X (cm)')
    ax.set_ylabel('Y (cm)')
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    return fig


def load_image_from_upload(uploaded_file):
    """StreamlitのUploadedFileをcv2画像(BGR ndarray)に変換する"""
    file_bytes = np.asarray(bytearray(uploaded_file.read()), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    return img


# -----------------------------------------------------
# メイン画面
# -----------------------------------------------------
st.title("🎯 アーチェリー着弾点プロット")
st.write("的を左右から撮影した2枚の写真をアップロードしてください。")

col1, col2 = st.columns(2)
with col1:
    left_file = st.file_uploader("左側の写真", type=["jpg", "jpeg", "png"], key="left")
with col2:
    right_file = st.file_uploader("右側の写真", type=["jpg", "jpeg", "png"], key="right")

if left_file is not None and right_file is not None:
    if st.button("解析する", type="primary", use_container_width=True):
        with st.spinner("解析中です。1〜2分ほどかかります..."):
            try:
                model = load_model()

                left_img = load_image_from_upload(left_file)
                right_img = load_image_from_upload(right_file)

                left_points, left_log = process_single_image(model, left_img, label="左")
                right_points, right_log = process_single_image(model, right_img, label="右")

                final_points, integrate_log = integrate_left_right(left_points, right_points)

            except ValueError as e:
                st.error(f"検出に失敗しました: {e}")
                st.stop()

        # ----- 検出ログの表示 -----
        with st.expander("検出の詳細を見る"):
            st.write(f"左画像: 矢 {left_log['num_arrows_detected']}本検出, "
                     f"的中心候補 {left_log['num_centers_detected']}個")
            st.write(f"右画像: 矢 {right_log['num_arrows_detected']}本検出, "
                     f"的中心候補 {right_log['num_centers_detected']}個")
            st.write(f"左右マッチ数: {integrate_log['matched_count']}, "
                     f"左のみ: {integrate_log['unmatched_left_count']}本, "
                     f"右のみ: {integrate_log['unmatched_right_count']}本")

        # ----- 結果プロット -----
        st.subheader("結果")
        tab1, tab2, tab3 = st.tabs(["左右統合", "左画像のみ", "右画像のみ"])

        with tab1:
            fig = plot_points(final_points, "左右統合", color='#27AE60')
            st.pyplot(fig, use_container_width=True)

        with tab2:
            fig = plot_points(left_points, "左画像のみ", color='#2E86C1')
            st.pyplot(fig, use_container_width=True)

        with tab3:
            fig = plot_points(right_points, "右画像のみ", color='#E67E22')
            st.pyplot(fig, use_container_width=True)

        # ----- 得点テーブル -----
        st.subheader("得点詳細(左右統合)")
        if len(final_points) > 0:
            rows = []
            for i, (x, y) in enumerate(final_points):
                score, is_x = calculate_score([x, y])
                rows.append({
                    "矢番号": i + 1,
                    "X (cm)": round(x, 1),
                    "Y (cm)": round(y, 1),
                    "得点": format_score(score, is_x),
                })
            st.table(rows)
        else:
            st.write("矢が検出されませんでした。")
else:
    st.info("左右両方の写真をアップロードすると「解析する」ボタンが表示されます。")

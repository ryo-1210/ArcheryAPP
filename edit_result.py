# =====================================================
# 的解析 - 編集・登録画面
# =====================================================

import numpy as np
import cv2
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import japanize_matplotlib
import streamlit as st

from archery_core import (
    calculate_score,
    format_score,
    calculate_statistics,
    RING_RADII_CM,
    RING_COLORS,
    X_RING_RADIUS_CM,
    ARROW_DIAMETER_CM,
)
from google_integration import append_record, upload_image_to_drive, generate_image_filename

# 十字キーで1回押すごとに動く距離(cm)
STEP_SIZE_CM = 0.2


def draw_target(ax):
    for r, c in zip(reversed(RING_RADII_CM), reversed(RING_COLORS)):
        circle = patches.Circle((0, 0), r, facecolor=c, edgecolor='gray', linewidth=0.5, zorder=1)
        ax.add_patch(circle)

    x_circle = patches.Circle((0, 0), X_RING_RADIUS_CM, facecolor='none',
                               edgecolor='black', linewidth=1.0, zorder=2)
    ax.add_patch(x_circle)


def plot_points(points, selected_idx=None, color='#27AE60'):
    fig, ax = plt.subplots(figsize=(6, 6))
    draw_target(ax)

    if len(points) > 0:
        points_arr = np.array(points)
        arrow_radius = ARROW_DIAMETER_CM / 2

        scores_and_x = [calculate_score(p) for p in points_arr]
        total_score = sum(s for s, _ in scores_and_x)
        x_count = sum(1 for _, is_x in scores_and_x if is_x)
        score_labels = [format_score(s, x) for s, x in scores_and_x]

        for i, (x, y) in enumerate(points_arr):
            is_selected = (i == selected_idx)
            face_color = '#FF4136' if is_selected else color
            edge_color = 'yellow' if is_selected else 'white'
            edge_width = 2.5 if is_selected else 1.2

            arrow_circle = patches.Circle((x, y), arrow_radius, facecolor=face_color,
                                          edgecolor=edge_color, linewidth=edge_width, zorder=5, alpha=0.95)
            ax.add_patch(arrow_circle)

        info_text = f"合計点: {total_score} / 矢数: {len(points)} / X数: {x_count}"
        ax.text(0.02, 0.98, info_text, transform=ax.transAxes, va='top', fontsize=11,
               bbox=dict(facecolor='white', alpha=0.85))

        for i, ((x, y), label) in enumerate(zip(points_arr, score_labels)):
            ax.annotate(str(i + 1), (x, y), textcoords="offset points", xytext=(8, 8),
                       fontsize=9, color='black', fontweight='bold',
                       bbox=dict(facecolor='white', alpha=0.75, pad=1))

    ax.set_xlim(-32, 32)
    ax.set_ylim(-32, 32)
    ax.set_aspect('equal')
    ax.set_xlabel('X (cm)')
    ax.set_ylabel('Y (cm)')
    ax.grid(True, alpha=0.3)
    return fig


def image_bytes_to_array(image_bytes):
    file_bytes = np.asarray(bytearray(image_bytes), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def render_edit_result(go_to):
    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("⬅", use_container_width=True):
            go_to("analyze_input")
            st.rerun()
    with col_title:
        st.title("データ登録")

    # ----- 採用するプロットの選択(初回のみ) -----
    if "plot_source_selected" not in st.session_state:
        st.subheader("どのプロットを採用しますか？")
        st.caption("左右統合・1枚目のみ・2枚目のみから、最も実際の着弾位置に近いものを選んでください")

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            fig = plot_points(st.session_state.final_points)
            st.pyplot(fig, use_container_width=True)
            if st.button("左右統合を採用", use_container_width=True, type="primary"):
                st.session_state.edit_points = list(map(list, st.session_state.final_points))
                st.session_state.plot_source_selected = "integrated"
                st.rerun()
        with col_b:
            fig = plot_points(st.session_state.left_points)
            st.pyplot(fig, use_container_width=True)
            if st.button("1枚目を採用", use_container_width=True):
                st.session_state.edit_points = list(map(list, st.session_state.left_points))
                st.session_state.plot_source_selected = "left"
                st.rerun()
        with col_c:
            fig = plot_points(st.session_state.right_points)
            st.pyplot(fig, use_container_width=True)
            if st.button("2枚目を採用", use_container_width=True):
                st.session_state.edit_points = list(map(list, st.session_state.right_points))
                st.session_state.plot_source_selected = "right"
                st.rerun()

        return  # 選択するまでは以降の編集UIを表示しない

    points = st.session_state.edit_points
    selected_idx = st.session_state.get("selected_arrow_idx", None)

    source_labels = {"integrated": "左右統合", "left": "1枚目のみ", "right": "2枚目のみ"}
    col_info, col_redo = st.columns([3, 1])
    with col_info:
        st.caption(f"採用中のプロット: {source_labels.get(st.session_state.plot_source_selected, '-')}")
    with col_redo:
        if st.button("選択をやり直す", use_container_width=True):
            st.session_state.pop("plot_source_selected", None)
            st.session_state.selected_arrow_idx = None
            st.rerun()

    # ----- タブ: プロット / 写真1 / 写真2 -----
    tab1, tab2, tab3 = st.tabs(["プロット", "写真1", "写真2"])

    with tab1:
        fig = plot_points(points, selected_idx=selected_idx)
        st.pyplot(fig, use_container_width=True)

    with tab2:
        img = image_bytes_to_array(st.session_state.left_image_bytes)
        st.image(img, use_container_width=True)

    with tab3:
        img = image_bytes_to_array(st.session_state.right_image_bytes)
        st.image(img, use_container_width=True)

    st.write("")

    # ----- 横スクロール可能な座標表(No.ボタン形式) -----
    st.caption("⇔ 矢の番号をタップすると編集できます")

    if len(points) > 0:
        cols = st.columns(len(points))
        for i, col in enumerate(cols):
            with col:
                label = f"No.{i+1}"
                btn_type = "primary" if i == selected_idx else "secondary"
                if st.button(label, key=f"select_arrow_{i}", use_container_width=True, type=btn_type):
                    st.session_state.selected_arrow_idx = i
                    st.rerun()
                x, y = points[i]
                score, is_x = calculate_score([x, y])
                st.caption(f"x:{x:.1f}\ny:{y:.1f}\n得点:{format_score(score, is_x)}")
    else:
        st.write("矢が検出されませんでした。")

    st.write("")

    # ----- 選択中の矢の編集UI(十字キー・削除・リセット) -----
    if selected_idx is not None and selected_idx < len(points):
        st.subheader(f"No.{selected_idx + 1} を編集中")

        col_pad, col_actions = st.columns([2, 1])

        with col_pad:
            # 十字キー(3x3グリッドで配置)
            r1c1, r1c2, r1c3 = st.columns(3)
            with r1c2:
                if st.button("⬆", key="up", use_container_width=True):
                    points[selected_idx][1] += STEP_SIZE_CM
                    st.rerun()

            r2c1, r2c2, r2c3 = st.columns(3)
            with r2c1:
                if st.button("⬅", key="left_btn", use_container_width=True):
                    points[selected_idx][0] -= STEP_SIZE_CM
                    st.rerun()
            with r2c2:
                st.write("")
            with r2c3:
                if st.button("➡", key="right_btn", use_container_width=True):
                    points[selected_idx][0] += STEP_SIZE_CM
                    st.rerun()

            r3c1, r3c2, r3c3 = st.columns(3)
            with r3c2:
                if st.button("⬇", key="down", use_container_width=True):
                    points[selected_idx][1] -= STEP_SIZE_CM
                    st.rerun()

        with col_actions:
            if st.button("🗑 削除", use_container_width=True):
                points.pop(selected_idx)
                st.session_state.edit_points = points
                st.session_state.selected_arrow_idx = None
                st.rerun()

            if st.button("↺ リセット", use_container_width=True):
                # 元の解析結果(final_points)の該当インデックスに戻す
                original = st.session_state.final_points
                if selected_idx < len(original):
                    points[selected_idx] = list(original[selected_idx])
                    st.rerun()

        if st.button("✅ 位置確定", type="primary", use_container_width=True):
            st.session_state.selected_arrow_idx = None
            st.rerun()

    st.write("---")

    # ----- 登録ボタン -----
    if st.button("📥 登録", type="primary", use_container_width=True):
        with st.spinner("登録中です..."):
            try:
                stats = calculate_statistics(points)
                scores_and_x = [calculate_score(p) for p in points]
                total_score = sum(s for s, _ in scores_and_x)
                score_labels = [format_score(s, x) for s, x in scores_and_x]

                user_id = st.session_state.user_id
                target_size = st.session_state.target_size

                # 画像をDriveにアップロード
                left_filename = generate_image_filename(user_id, "left")
                right_filename = generate_image_filename(user_id, "right")
                left_drive_id = upload_image_to_drive(st.session_state.left_image_bytes, left_filename)
                right_drive_id = upload_image_to_drive(st.session_state.right_image_bytes, right_filename)

                from datetime import datetime
                record = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "user_id": user_id,
                    "target_size_cm": target_size,
                    "arrow_count": len(points),
                    "scores": ",".join(score_labels),
                    "coords_x": ",".join(f"{p[0]:.2f}" for p in points),
                    "coords_y": ",".join(f"{p[1]:.2f}" for p in points),
                    "total_score": total_score,
                    "centroid_x": round(stats["centroid_x"], 2) if stats["centroid_x"] is not None else "",
                    "centroid_y": round(stats["centroid_y"], 2) if stats["centroid_y"] is not None else "",
                    "spread": round(stats["spread"], 2) if stats["spread"] is not None else "",
                    "offset_x": round(stats["offset_x"], 2) if stats["offset_x"] is not None else "",
                    "offset_y": round(stats["offset_y"], 2) if stats["offset_y"] is not None else "",
                    "left_image_drive_id": left_drive_id,
                    "right_image_drive_id": right_drive_id,
                }

                append_record(record)

            except Exception as e:
                st.error(f"登録に失敗しました: {e}")
                st.stop()

        st.success("登録が完了しました！")
        st.balloons()

        # セッションをクリアしてトップに戻る
        for key in ["edit_points", "final_points", "left_points", "right_points",
                    "left_image_bytes", "right_image_bytes", "selected_arrow_idx",
                    "plot_source_selected"]:
            st.session_state.pop(key, None)

        go_to("top")
        st.rerun()

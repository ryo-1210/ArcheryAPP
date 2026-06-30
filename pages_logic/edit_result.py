# =====================================================
# 的解析 - 編集・登録画面
# =====================================================

import numpy as np
import cv2
import streamlit as st

from archery_core import (
    calculate_score,
    format_score,
    calculate_statistics,
    plot_points,
)
from google_integration import append_record, update_record

# 十字キーで1回押すごとに動く距離(cm)
STEP_SIZE_CM = 0.2


def image_bytes_to_array(image_bytes):
    file_bytes = np.asarray(bytearray(image_bytes), dtype=np.uint8)
    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def render_edit_result(go_to):
    # スマホ対応CSS
    st.markdown("""
    <style>
    .dpad-container {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        grid-template-rows: auto auto auto;
        gap: 4px;
        max-width: 240px;
        margin: 0 auto;
    }
    .dpad-center {
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 11px;
        color: #888;
    }
    </style>
    """, unsafe_allow_html=True)
    is_editing_existing = st.session_state.get("is_editing_existing", False)
    back_target = "data_view" if is_editing_existing else "analyze_input"

    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("⬅", use_container_width=True):
            go_to(back_target)
            st.rerun()
    with col_title:
        st.title("データ編集" if is_editing_existing else "データ登録")

    # ----- 採用するプロットの選択(新規登録時、初回のみ) -----
    # 既存データの編集時は1種類のプロットしかないため、この選択ステップは不要
    if not is_editing_existing and "plot_source_selected" not in st.session_state:
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

    if not is_editing_existing:
        source_labels = {"integrated": "左右統合", "left": "1枚目のみ", "right": "2枚目のみ",
                          "existing": "登録済みデータ"}
        col_info, col_redo = st.columns([3, 1])
        with col_info:
            st.caption(f"採用中のプロット: {source_labels.get(st.session_state.plot_source_selected, '-')}")
        with col_redo:
            if st.button("選択をやり直す", use_container_width=True):
                st.session_state.pop("plot_source_selected", None)
                st.session_state.selected_arrow_idx = None
                st.rerun()

    # ----- タブ: プロット / 写真1 / 写真2 (画像がある場合のみ) -----
    has_images = st.session_state.get("left_image_bytes") is not None

    if has_images:
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
    else:
        fig = plot_points(points, selected_idx=selected_idx)
        st.pyplot(fig, use_container_width=True)

    # ----- No.ボタン(プロット直下・コンパクト) -----
    if len(points) > 0:
        st.caption("矢の番号をタップして選択→十字キーで位置を調整")
        cols = st.columns(len(points))
        for i, col in enumerate(cols):
            with col:
                btn_type = "primary" if i == selected_idx else "secondary"
                if st.button(f"{i+1}", key=f"select_arrow_{i}",
                             use_container_width=True, type=btn_type):
                    if st.session_state.get("selected_arrow_idx") == i:
                        st.session_state.selected_arrow_idx = None
                    else:
                        st.session_state.selected_arrow_idx = i
                    st.rerun()
    else:
        st.warning("矢が検出されませんでした。")

    # ----- 選択中の矢の編集UI(十字キー・削除・リセット) -----
    if selected_idx is not None and selected_idx < len(points):
        x, y = points[selected_idx]
        score, is_x = calculate_score([x, y])
        st.caption(f"No.{selected_idx+1} を編集中 ／ x={x:.1f}cm, y={y:.1f}cm ／ 得点: {format_score(score, is_x)}")

        col_dpad, col_actions = st.columns([3, 2])

        with col_dpad:
            st.markdown(f'<p style="text-align:center;font-size:13px;margin:0;">現在位置: ({x:.1f}, {y:.1f})</p>', unsafe_allow_html=True)
            # 1行目: ▲ のみ中央
            up_l, up_c, up_r = st.columns([1, 2, 1])
            with up_c:
                if st.button("▲  上", key="up", use_container_width=True):
                    points[selected_idx][1] += STEP_SIZE_CM
                    st.rerun()
            # 2行目: ◀ と ▶
            lr_l, lr_r = st.columns(2)
            with lr_l:
                if st.button("◀  左", key="left_btn", use_container_width=True):
                    points[selected_idx][0] -= STEP_SIZE_CM
                    st.rerun()
            with lr_r:
                if st.button("右  ▶", key="right_btn", use_container_width=True):
                    points[selected_idx][0] += STEP_SIZE_CM
                    st.rerun()
            # 3行目: ▼ のみ中央
            dn_l, dn_c, dn_r = st.columns([1, 2, 1])
            with dn_c:
                if st.button("▼  下", key="down", use_container_width=True):
                    points[selected_idx][1] -= STEP_SIZE_CM
                    st.rerun()

        with col_actions:
            st.write("")  # 上部の余白合わせ
            if st.button("✅ 位置確定", type="primary", use_container_width=True):
                st.session_state.selected_arrow_idx = None
                st.rerun()
            if st.button("🗑 削除", use_container_width=True):
                points.pop(selected_idx)
                st.session_state.edit_points = points
                st.session_state.selected_arrow_idx = None
                st.rerun()
            if not is_editing_existing:
                if st.button("↺ リセット", use_container_width=True):
                    original = st.session_state.final_points
                    if selected_idx < len(original):
                        points[selected_idx] = list(original[selected_idx])
                        st.rerun()

    st.write("---")

    # ----- 得点表(下部に移動) -----
    if len(points) > 0:
        scores_and_x = [calculate_score(p) for p in points]
        score_labels = [format_score(s, x) for s, x in scores_and_x]
        total = sum(s for s, _ in scores_and_x)

        header = "".join(
            f'<th style="border:1px solid #555;padding:4px 8px;background:#2b2b2b;color:#fff;">{i+1}</th>'
            for i in range(len(score_labels))
        )
        cells = "".join(
            f'<td style="border:1px solid #555;padding:4px 8px;text-align:center;">{s}</td>'
            for s in score_labels
        )
        table_html = (
            '<div style="overflow-x:auto;margin:6px 0;">'
            '<table style="border-collapse:collapse;width:max-content;">'
            f'<tr><th style="border:1px solid #555;padding:4px 8px;background:#2b2b2b;color:#fff;">No.</th>{header}</tr>'
            f'<tr><th style="border:1px solid #555;padding:4px 8px;background:#2b2b2b;color:#fff;">得点</th>{cells}</tr>'
            '</table></div>'
        )
        st.markdown(table_html, unsafe_allow_html=True)
        st.caption(f"合計: {total}点")

    st.write("---")

    # ----- 個人ID・メモの編集 -----
    st.subheader("基本情報")
    from pages_logic.analyze_input import USER_ID_OPTIONS

    current_user_id = st.session_state.get("user_id", USER_ID_OPTIONS[0])
    if current_user_id not in USER_ID_OPTIONS:
        current_user_id = USER_ID_OPTIONS[0]

    new_user_id = st.selectbox(
        "個人ID", USER_ID_OPTIONS,
        index=USER_ID_OPTIONS.index(current_user_id),
        key="edit_user_id_select",
    )
    new_memo = st.text_area(
        "メモ", value=st.session_state.get("memo", ""), key="edit_memo_input"
    )
    st.caption(f"的紙サイズ: {st.session_state.get('target_size', '-')}cm / "
               f"距離: {st.session_state.get('distance', '-')}m (変更不可)")

    st.write("---")

    # ----- 学習データ用の画像ダウンロード(任意、画像がある場合のみ) -----
    if has_images:
        with st.expander("📷 学習データ用に画像を保存する(任意)"):
            st.caption("将来のモデル改善のため、元の写真をダウンロードして保存しておけます。")
            col_dl1, col_dl2 = st.columns(2)
            with col_dl1:
                st.download_button(
                    "1枚目をダウンロード",
                    data=st.session_state.left_image_bytes,
                    file_name=f"{st.session_state.user_id}_1.jpg",
                    mime="image/jpeg",
                    use_container_width=True,
                )
            with col_dl2:
                st.download_button(
                    "2枚目をダウンロード",
                    data=st.session_state.right_image_bytes,
                    file_name=f"{st.session_state.user_id}_2.jpg",
                    mime="image/jpeg",
                    use_container_width=True,
                )

    # ----- 登録/更新ボタン -----
    button_label = "💾 更新を保存" if is_editing_existing else "📥 登録"

    if st.button(button_label, type="primary", use_container_width=True):
        with st.spinner("保存中です..."):
            try:
                stats = calculate_statistics(points)
                scores_and_x = [calculate_score(p) for p in points]
                total_score = sum(s for s, _ in scores_and_x)
                score_labels = [format_score(s, x) for s, x in scores_and_x]

                target_size = st.session_state.target_size

                common_fields = {
                    "user_id": new_user_id,
                    "target_size_cm": target_size,
                    "distance_m": st.session_state.get("distance", ""),
                    "arrow_count": len(points),
                    "scores": "/".join(score_labels),
                    "coords_x": ",".join(f"{p[0]:.2f}" for p in points),
                    "coords_y": ",".join(f"{p[1]:.2f}" for p in points),
                    "total_score": total_score,
                    "centroid_x": round(stats["centroid_x"], 2) if stats["centroid_x"] is not None else "",
                    "centroid_y": round(stats["centroid_y"], 2) if stats["centroid_y"] is not None else "",
                    "spread": round(stats["spread"], 2) if stats["spread"] is not None else "",
                    "offset_x": round(stats["offset_x"], 2) if stats["offset_x"] is not None else "",
                    "offset_y": round(stats["offset_y"], 2) if stats["offset_y"] is not None else "",
                    "memo": new_memo,
                }

                if is_editing_existing:
                    record_id = st.session_state.editing_record_id
                    update_record(record_id, common_fields)
                else:
                    from datetime import datetime, timezone, timedelta
                    JST = timezone(timedelta(hours=9))
                    record = {
                        "timestamp": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"),
                        "left_image_drive_id": "",  # Drive自動保存は無効化中
                        "right_image_drive_id": "",  # Drive自動保存は無効化中
                        **common_fields,
                    }
                    append_record(record)

            except Exception as e:
                st.error(f"保存に失敗しました: {e}")
                st.stop()

        st.success("更新が完了しました！" if is_editing_existing else "登録が完了しました！")
        st.balloons()

        # セッションをクリアして元の画面に戻る
        for key in ["edit_points", "final_points", "left_points", "right_points",
                    "left_image_bytes", "right_image_bytes", "selected_arrow_idx",
                    "plot_source_selected", "is_editing_existing", "editing_record_id",
                    "user_id", "memo", "target_size"]:
            st.session_state.pop(key, None)

        go_to(back_target)
        st.rerun()

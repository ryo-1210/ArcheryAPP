# =====================================================
# データ閲覧画面
# =====================================================

import streamlit as st
from google_integration import fetch_all_records
from archery_core import plot_points, calculate_statistics

USER_ID_OPTIONS = ["(全員)"] + [f"{i:03d}" for i in range(1, 1000)]
TARGET_SIZE_FILTER_OPTIONS = ["(全サイズ)", 20, 40, 60, 80, 122]


def build_score_table_html(scores):
    """
    矢の得点リストから、横並び・横スクロール対応のコンパクトなHTML表を組み立てる。
    scores: 得点の文字列リスト(例: ["7", "10", "8", ...])
    """
    cell_style = "border:1px solid #555; padding:4px 10px; text-align:center;"
    header_style = cell_style + "background:#2b2b2b; color:#ffffff;"

    no_header = ""
    for i in range(len(scores)):
        no_header += '<th style="' + header_style + '">' + str(i + 1) + '</th>'

    score_cells = ""
    for s in scores:
        score_cells += '<td style="' + cell_style + '">' + str(s) + '</td>'

    html = '<div style="overflow-x: auto; white-space: nowrap; margin: 6px 0;">'
    html += '<table style="border-collapse: collapse; width: max-content;">'
    html += '<tr><th style="' + header_style + '">No.</th>' + no_header + '</tr>'
    html += '<tr><th style="' + header_style + '">得点</th>' + score_cells + '</tr>'
    html += '</table></div>'

    return html


def parse_record_points(record):
    """
    レコードのcoords_x, coords_y(カンマ区切り文字列)を
    plot_points関数に渡せる [[x, y], [x, y], ...] 形式に変換する
    """
    coords_x = str(record.get("coords_x", "")).strip()
    coords_y = str(record.get("coords_y", "")).strip()

    if not coords_x or not coords_y:
        return []

    try:
        xs = [float(v) for v in coords_x.split(",") if v != ""]
        ys = [float(v) for v in coords_y.split(",") if v != ""]
    except ValueError:
        return []

    return list(zip(xs, ys))


def render_aggregate_section(records, current_filter_key):
    """
    選択された複数レコードの矢を1つの的にまとめてプロットし、
    全体の重心・散らばり・的中心との差分を表示する。
    """
    # 選択されているレコードのみ抜き出す(現在の表示順=新しい順に対応するキー生成と揃える)
    selected_records = []
    for idx, record in enumerate(reversed(records)):
        record_key = f"{record.get('timestamp', '')}_{record.get('user_id', '')}_{idx}"
        if record_key in st.session_state.selected_record_keys:
            selected_records.append(record)

    all_points = []
    for record in selected_records:
        all_points.extend(parse_record_points(record))

    if not all_points:
        st.warning("選択したデータに座標情報がありませんでした。")
        return

    stats = calculate_statistics(all_points)

    with st.container(border=True):
        st.subheader(f"📊 集計結果({len(selected_records)}件 / 矢数 {len(all_points)}本)")

        fig = plot_points(all_points, figsize=(6, 6), color='#9B59B6')
        st.pyplot(fig, use_container_width=True)

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("重心X", f"{stats['centroid_x']:.2f}cm" if stats['centroid_x'] is not None else "-")
            st.metric("重心Y", f"{stats['centroid_y']:.2f}cm" if stats['centroid_y'] is not None else "-")
        with col_b:
            st.metric("散らばり", f"{stats['spread']:.2f}cm" if stats['spread'] is not None else "-")
        with col_c:
            st.metric("的中心とのX差分", f"{stats['offset_x']:+.2f}cm" if stats['offset_x'] is not None else "-")
            st.metric("的中心とのY差分", f"{stats['offset_y']:+.2f}cm" if stats['offset_y'] is not None else "-")

        st.caption("X差分が+なら重心は的の右側、Y差分が+なら重心は的の上側にズレています。")


def render_data_view(go_to):
    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("⬅", use_container_width=True):
            go_to("top")
            st.rerun()
    with col_title:
        st.title("データ閲覧")

    if "viewing_record_key" not in st.session_state:
        st.session_state.viewing_record_key = None

    if "selected_record_keys" not in st.session_state:
        st.session_state.selected_record_keys = set()

    if "show_aggregate" not in st.session_state:
        st.session_state.show_aggregate = False

    col_id, col_size = st.columns(2)
    with col_id:
        user_id = st.selectbox("個人IDで検索", USER_ID_OPTIONS, key="search_user_id")
    with col_size:
        size_filter = st.selectbox(
            "的紙フィルタ", TARGET_SIZE_FILTER_OPTIONS, key="search_target_size"
        )

    with st.spinner("読み込み中..."):
        try:
            if user_id == "(全員)":
                records = fetch_all_records()
            else:
                records = fetch_all_records(user_id=user_id)
        except Exception as e:
            st.error(f"データの取得に失敗しました: {e}")
            st.stop()

    # 的紙サイズで絞り込み
    if size_filter != "(全サイズ)":
        records = [r for r in records if str(r.get("target_size_cm", "")) == str(size_filter)]

    if not records:
        st.info("データが見つかりませんでした。")
        return

    # フィルタが変わったら選択状態をリセットする(別の絞り込み結果と混ざらないように)
    current_filter_key = f"{user_id}_{size_filter}"
    if st.session_state.get("last_filter_key") != current_filter_key:
        st.session_state.selected_record_keys = set()
        st.session_state.show_aggregate = False
        st.session_state.last_filter_key = current_filter_key

    st.write(f"{len(records)}件のデータが見つかりました。")

    # ----- 複数選択して集計するエリア -----
    selected_count = len(st.session_state.selected_record_keys)
    col_count, col_agg_btn, col_clear_btn = st.columns([2, 2, 1])
    with col_count:
        st.write(f"選択中: {selected_count}件")
    with col_agg_btn:
        if st.button("📊 選択データを集計", use_container_width=True, disabled=(selected_count == 0)):
            st.session_state.show_aggregate = True
            st.rerun()
    with col_clear_btn:
        if st.button("選択解除", use_container_width=True):
            st.session_state.selected_record_keys = set()
            st.session_state.show_aggregate = False
            st.rerun()

    # ----- 集計結果の表示 -----
    if st.session_state.show_aggregate and selected_count > 0:
        render_aggregate_section(records, current_filter_key)

    st.write("---")

    # 新しい順に表示
    for idx, record in enumerate(reversed(records)):
        # レコードを一意に識別するキー(タイムスタンプ+ID+インデックスの組み合わせ)
        record_key = f"{record.get('timestamp', '')}_{record.get('user_id', '')}_{idx}"

        with st.container(border=True):
            col_check, col_info, col_search = st.columns([1, 4, 1])
            with col_check:
                is_checked = st.checkbox(
                    "選択", key=f"check_{record_key}",
                    value=(record_key in st.session_state.selected_record_keys),
                    label_visibility="collapsed",
                )
                if is_checked:
                    st.session_state.selected_record_keys.add(record_key)
                else:
                    st.session_state.selected_record_keys.discard(record_key)
            with col_info:
                st.write(f"**{record.get('timestamp', '')}** / ID: {record.get('user_id', '')}")
                st.write(f"的: {record.get('target_size_cm', '-')}cm / 合計点: {record.get('total_score', '-')}")
            with col_search:
                if st.button("🔍", key=f"view_{record_key}", use_container_width=True):
                    # 同じレコードをもう一度押したら閉じる(トグル動作)
                    if st.session_state.get("viewing_record_key") == record_key:
                        st.session_state.viewing_record_key = None
                    else:
                        st.session_state.viewing_record_key = record_key
                    st.rerun()

            scores = str(record.get("scores", "")).split("/")
            st.markdown(build_score_table_html(scores), unsafe_allow_html=True)

            st.caption(f"重心X: {record.get('centroid_x', '-')}cm / 重心Y: {record.get('centroid_y', '-')}cm / "
                       f"散らばり: {record.get('spread', '-')}cm")

            memo = str(record.get("memo", "")).strip()
            if memo:
                st.caption(f"📝 {memo}")

            # 虫眼鏡が押されているレコードのみ、詳細プロットを展開表示する
            if st.session_state.get("viewing_record_key") == record_key:
                st.write("---")
                points = parse_record_points(record)
                if points:
                    fig = plot_points(points, figsize=(5, 5))
                    st.pyplot(fig, use_container_width=True)

                    if st.button("✏️ このデータを編集する", key=f"edit_{record_key}", use_container_width=True):
                        # edit_result.pyが必要とするセッション情報をセットして遷移
                        st.session_state.is_editing_existing = True
                        st.session_state.editing_record_id = record.get("record_id", "")
                        st.session_state.edit_points = [list(p) for p in points]
                        st.session_state.plot_source_selected = "existing"  # 選択ステップをスキップさせる
                        st.session_state.selected_arrow_idx = None
                        st.session_state.user_id = record.get("user_id", "")
                        st.session_state.memo = record.get("memo", "")
                        st.session_state.target_size = record.get("target_size_cm", "")
                        st.session_state.left_image_bytes = None
                        st.session_state.right_image_bytes = None

                        go_to("edit_result")
                        st.rerun()
                else:
                    st.info("このデータには座標情報がありません。")

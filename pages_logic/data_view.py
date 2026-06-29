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


def render_aggregate_section(selected_records):
    """
    選択された複数レコードの矢を1つの的にまとめてプロットし、
    全体の重心・散らばり・的中心との差分を表示する。
    また、選択した各データの個別得点表も補足的に表示する。
    """
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

        st.write("---")
        st.caption("選択した各データの得点(補足)")
        for record in selected_records:
            scores = str(record.get("scores", "")).split("/")
            st.write(f"{record.get('timestamp', '')} / ID: {record.get('user_id', '')}")
            st.markdown(build_score_table_html(scores), unsafe_allow_html=True)


@st.cache_data(ttl=30)
def fetch_records_cached(user_id):
    """
    全件取得をキャッシュする(30秒間は再取得しない)。
    チェックボックスのクリックなどによる再描画のたびに
    スプレッドシートへ問い合わせてspinnerが出るのを防ぐ。
    """
    if user_id == "(全員)":
        return fetch_all_records()
    return fetch_all_records(user_id=user_id)


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

    if "show_aggregate" not in st.session_state:
        st.session_state.show_aggregate = False

    if "checkbox_generation" not in st.session_state:
        st.session_state.checkbox_generation = 0

    col_id, col_size = st.columns(2)
    with col_id:
        user_id = st.selectbox("個人IDで検索", USER_ID_OPTIONS, key="search_user_id")
    with col_size:
        size_filter = st.selectbox(
            "的紙フィルタ", TARGET_SIZE_FILTER_OPTIONS, key="search_target_size"
        )

    sort_order = st.radio(
        "並び順", ["新しい順", "古い順"], key="sort_order_select", horizontal=True,
    )

    try:
        records = fetch_records_cached(user_id)
    except Exception as e:
        st.error(f"データの取得に失敗しました: {e}")
        st.stop()

    # 的紙サイズで絞り込み
    if size_filter != "(全サイズ)":
        records = [r for r in records if str(r.get("target_size_cm", "")) == str(size_filter)]

    if not records:
        st.info("データが見つかりませんでした。")
        return

    # 日付(timestamp)でソート。文字列の "YYYY-MM-DD HH:MM:SS" 形式なのでそのまま文字列比較で並べ替えられる
    records = sorted(records, key=lambda r: str(r.get("timestamp", "")), reverse=(sort_order == "新しい順"))

    st.write(f"{len(records)}件のデータが見つかりました。")
    st.write("---")

    # レコードキーの一覧を先に作っておく(世代番号を含めることで、解除時に確実にリセットできる)
    gen = st.session_state.checkbox_generation
    ordered_records = list(enumerate(records))
    record_keys = [
        f"{record.get('timestamp', '')}_{record.get('user_id', '')}_{idx}_{gen}"
        for idx, record in ordered_records
    ]

    # ----- チェックボックス一覧を先に描画する -----
    # (サイドバーの集計判定より先にウィジェットを生成し、最新の状態を反映させるため)
    for (idx, record), record_key in zip(ordered_records, record_keys):
        with st.container(border=True):
            col_check, col_info, col_search = st.columns([1, 4, 1])
            with col_check:
                st.checkbox(
                    "選択", key=f"check_{record_key}",
                    label_visibility="collapsed",
                )
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

    # ----- サイドバー: 選択状況と集計操作(常時表示) -----
    # チェックボックスがすべて生成された後なので、最新の選択状態を正しく参照できる
    selected_keys = [k for k in record_keys if st.session_state.get(f"check_{k}", False)]
    selected_count = len(selected_keys)

    with st.sidebar:
        st.subheader("複数データの集計")
        st.write(f"選択中: {selected_count}件 / 全{len(record_keys)}件")

        col_all, col_none = st.columns(2)
        with col_all:
            if st.button("全選択", use_container_width=True):
                for k in record_keys:
                    st.session_state[f"check_{k}"] = True
                st.rerun()
        with col_none:
            if st.button("選択解除", use_container_width=True):
                # チェックボックスのkeyに世代番号を含めているため、
                # 世代を1つ進めることで確実に全ウィジェットを未選択状態で再生成できる
                st.session_state.checkbox_generation += 1
                st.session_state.show_aggregate = False
                st.rerun()

        if st.button("📊 選択データを集計", use_container_width=True,
                     disabled=(selected_count == 0), type="primary"):
            st.session_state.show_aggregate = True
            st.rerun()

        # ----- 集計結果はサイドバーに表示する -----
        if st.session_state.show_aggregate and selected_count > 0:
            selected_records = [
                record for record, key in zip((r for _, r in ordered_records), record_keys)
                if key in selected_keys
            ]
            render_aggregate_section(selected_records)

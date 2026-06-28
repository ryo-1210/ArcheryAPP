# =====================================================
# データ閲覧画面
# =====================================================

import streamlit as st
from google_integration import fetch_all_records
from archery_core import plot_points

USER_ID_OPTIONS = ["(全員)"] + [f"{i:03d}" for i in range(1, 1000)]


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

    user_id = st.selectbox("個人IDで検索", USER_ID_OPTIONS, key="search_user_id")

    with st.spinner("読み込み中..."):
        try:
            if user_id == "(全員)":
                records = fetch_all_records()
            else:
                records = fetch_all_records(user_id=user_id)
        except Exception as e:
            st.error(f"データの取得に失敗しました: {e}")
            st.stop()

    if not records:
        st.info("データが見つかりませんでした。")
        return

    st.write(f"{len(records)}件のデータが見つかりました。")
    st.write("---")

    # 新しい順に表示
    for idx, record in enumerate(reversed(records)):
        # レコードを一意に識別するキー(タイムスタンプ+ID+インデックスの組み合わせ)
        record_key = f"{record.get('timestamp', '')}_{record.get('user_id', '')}_{idx}"

        with st.container(border=True):
            col_info, col_search = st.columns([5, 1])
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

            scores = str(record.get("scores", "")).split(",")
            st.markdown(build_score_table_html(scores), unsafe_allow_html=True)

            st.caption(f"重心X: {record.get('centroid_x', '-')}cm / 重心Y: {record.get('centroid_y', '-')}cm")

            # 虫眼鏡が押されているレコードのみ、詳細プロットを展開表示する
            if st.session_state.get("viewing_record_key") == record_key:
                st.write("---")
                points = parse_record_points(record)
                if points:
                    fig = plot_points(points, figsize=(5, 5))
                    st.pyplot(fig, use_container_width=True)
                else:
                    st.info("このデータには座標情報がありません。")

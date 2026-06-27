# =====================================================
# データ閲覧画面
# =====================================================

import streamlit as st
from google_integration import fetch_all_records

USER_ID_OPTIONS = ["(全員)"] + [f"{i:03d}" for i in range(1, 1000)]


def build_score_table_html(scores):
    """
    矢の得点リストから、横並び・横スクロール対応のコンパクトなHTML表を組み立てる。
    scores: 得点の文字列リスト(例: ["7", "10", "8", ...])
    """
    cell_style = "border:1px solid #555; padding:4px 10px; text-align:center;"
    header_style = cell_style + "background:#2b2b2b;"

    no_header = "".join(f'<th style="{header_style}">{i+1}</th>' for i in range(len(scores)))
    score_cells = "".join(f'<td style="{cell_style}">{s}</td>' for s in scores)

    return f"""
    <div style="overflow-x: auto; white-space: nowrap; margin: 6px 0;">
      <table style="border-collapse: collapse; width: max-content;">
        <tr>
          <th style="{header_style}">No.</th>
          {no_header}
        </tr>
        <tr>
          <th style="{header_style}">得点</th>
          {score_cells}
        </tr>
      </table>
    </div>
    """


def render_data_view(go_to):
    col_back, col_title = st.columns([1, 5])
    with col_back:
        if st.button("⬅", use_container_width=True):
            go_to("top")
            st.rerun()
    with col_title:
        st.title("データ閲覧")

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
    for record in reversed(records):
        with st.container(border=True):
            st.write(f"**{record.get('timestamp', '')}** / ID: {record.get('user_id', '')} / "
                     f"的: {record.get('target_size_cm', '-')}cm / 合計点: {record.get('total_score', '-')}")

            scores = str(record.get("scores", "")).split(",")
            st.markdown(build_score_table_html(scores), unsafe_allow_html=True)

            st.caption(f"重心X: {record.get('centroid_x', '-')}cm / 重心Y: {record.get('centroid_y', '-')}cm")

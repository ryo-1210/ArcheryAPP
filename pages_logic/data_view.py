# =====================================================
# データ閲覧画面
# =====================================================

import streamlit as st
from google_integration import fetch_all_records

USER_ID_OPTIONS = ["(全員)"] + [f"{i:03d}" for i in range(1, 1000)]


    
def render_data_view(go_to):
    records_debug = fetch_all_records()
    st.write("デバッグ: 最初のレコードのuser_id型と値")
    if records_debug:
        st.write(type(records_debug[0].get("user_id")), records_debug[0].get("user_id"))
    
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
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"**{record.get('timestamp', '')}** / ID: {record.get('user_id', '')}")

                scores = str(record.get("scores", "")).split(",")
                score_cols = st.columns(min(len(scores), 6))
                for i, col in enumerate(score_cols[:6]):
                    with col:
                        st.metric(f"矢{i+1}", scores[i] if i < len(scores) else "-")

                st.write(f"合計点: {record.get('total_score', '-')}")

            with col2:
                st.caption(f"的: {record.get('target_size_cm', '-')}cm")
                st.caption(f"重心X: {record.get('centroid_x', '-')}")
                st.caption(f"重心Y: {record.get('centroid_y', '-')}")

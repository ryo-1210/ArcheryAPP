# =====================================================
# アーチェリー着弾点検出アプリ (Streamlit) - メインエントリ
# =====================================================

import streamlit as st

st.set_page_config(page_title="アーチェリー着弾点プロット", layout="centered")

# -----------------------------------------------------
# 画面遷移の状態管理
# -----------------------------------------------------
if "page" not in st.session_state:
    st.session_state.page = "top"


def go_to(page_name):
    st.session_state.page = page_name


# -----------------------------------------------------
# トップ画面
# -----------------------------------------------------
def render_top():
    st.title("🏹 アーチェリー着弾点アプリ")
    st.write("")

    if st.button("📊 データ閲覧", use_container_width=True):
        go_to("data_view")
        st.rerun()

    st.write("")

    if st.button("🎯 的解析", use_container_width=True, type="primary"):
        go_to("analyze_input")
        st.rerun()


# -----------------------------------------------------
# 画面の振り分け
# -----------------------------------------------------
page = st.session_state.page

if page == "top":
    render_top()

elif page == "analyze_input":
    from pages_logic.analyze_input import render_analyze_input
    render_analyze_input(go_to)

elif page == "edit_result":
    from pages_logic.edit_result import render_edit_result
    render_edit_result(go_to)

elif page == "data_view":
    from pages_logic.data_view import render_data_view
    render_data_view(go_to)

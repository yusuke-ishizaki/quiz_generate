import streamlit as st

admin_user = st.secrets.ADMIN
admin_password = st.secrets.PASSWORD

def main():
    st.title("ログイン画面")
    
    # ユーザー名とパスワードの入力
    username = st.text_input("ユーザー名")
    password = st.text_input("パスワード", type="password")
    
    # 環境変数を使用した認証
    if st.button("ログイン"):
        if username == admin_user and password == admin_password:
            st.success("ログイン成功！")
        else:
            st.error("ユーザー名またはパスワードが間違っています。")

if __name__ == "__main__":
    main()
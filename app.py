import streamlit as st

def main():
    st.title("ログイン画面")
    
    # ユーザー名とパスワードの入力
    username = st.text_input("ユーザー名")
    password = st.text_input("パスワード", type="password")
    
    # シンプルな認証（本番環境では安全な認証方法を使用）
    if st.button("ログイン"):
        if username == "admin" and password == "password":
            st.success("Hello!")
        else:
            st.error("ユーザー名またはパスワードが間違っています。")

if __name__ == "__main__":
    main()

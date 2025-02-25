import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import SystemMessage, HumanMessage, AIMessage
import hashlib
import time

# 環境変数の設定
GEMINI_API_KEY = st.secrets.GEMINI_API_KEY
LOGIN_ID = st.secrets.ADMIN
LOGIN_PASSWORD = st.secrets.PASSWORD

# セッション状態の初期化
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "page" not in st.session_state:
    st.session_state.page = 1
if "file_content" not in st.session_state:
    st.session_state.file_content = ""
if "current_question" not in st.session_state:
    st.session_state.current_question = None
if "question_history" not in st.session_state:
    st.session_state.question_history = []
if "llm" not in st.session_state:
    st.session_state.llm = None

# LLMの初期化
def initialize_llm():
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-lite-preview-02-05",
            google_api_key=GEMINI_API_KEY,
            temperature=0.7
        )
        return llm
    except Exception as e:
        st.error(f"LLMの初期化エラー: {str(e)}")
        return None

# サイドバーメニューの設定
def setup_sidebar():
    with st.sidebar:
        st.title("学習システム")
        
        if st.session_state.authenticated:
            if st.button("初期化"):
                st.session_state.page = 2
                st.session_state.file_content = ""
                st.session_state.current_question = None
                st.session_state.question_history = []
                st.rerun()
                
            st.write("---")
            if st.button("ログアウト"):
                st.session_state.authenticated = False
                st.session_state.page = 1
                st.rerun()

# ページ1: ログイン認証
def login_page():
    st.title("ログイン")
    
    login_id = st.text_input("ログインID", key="login_id")
    password = st.text_input("パスワード", type="password", key="password")
    
    if st.button("ログイン"):
        if login_id == LOGIN_ID and password == LOGIN_PASSWORD:
            st.session_state.authenticated = True
            st.session_state.page = 2
            # LLMの初期化
            st.session_state.llm = initialize_llm()
            st.rerun()
        else:
            st.error("ログイン失敗")

# ページ2: ファイルアップロード
def upload_page():
    st.title("ファイルアップロード")
    
    uploaded_file = st.file_uploader("テキストファイルをアップロードしてください", type=["txt"])
    
    if uploaded_file is not None:
        try:
            file_content = uploaded_file.read().decode("utf-8")
            if st.button("送信"):
                st.session_state.file_content = file_content
                st.session_state.page = 3
                st.rerun()
        except Exception as e:
            st.error(f"ファイル読み込みエラー: {str(e)}")

# ページ3: 学習ページ
def learning_page():
    st.title("学習ページ")
    
    if not st.session_state.file_content:
        st.warning("ファイルがアップロードされていません。ファイルアップロードページに戻ります。")
        time.sleep(2)
        st.session_state.page = 2
        st.rerun()
    
    # 問題タイプの選択
    question_type = st.radio(
        "問題タイプを選択してください",
        ["穴埋め問題", "テキスト問題"],
        horizontal=True
    )
    
    # 新しい問題を生成
    if st.session_state.current_question is None:
        generate_new_question(question_type)
    
    # 現在の問題を表示
    if st.session_state.current_question:
        st.markdown("## 問題")
        st.markdown(st.session_state.current_question["question"])
        
        # 回答入力
        user_answer = st.text_input("あなたの回答を入力してください")
        
        if st.button("回答を提出"):
            check_answer(user_answer)

# 新しい問題の生成
def generate_new_question(question_type):
    try:
        llm = st.session_state.llm
        if llm is None:
            st.session_state.llm = initialize_llm()
            llm = st.session_state.llm
            
        system_msg = SystemMessage(content=f"""
        あなたは学習支援AIです。与えられたテキストコンテンツを元に学習者向けの質問を作成してください。
        質問は日本語で作成し、回答も日本語で評価してください。
        
        テキストコンテンツ:
        {st.session_state.file_content}
        """)
        
        msg_content = ""
        if question_type == "穴埋め問題":
            msg_content = """
            テキストの内容に基づいた穴埋め問題を1つ作成してください。
            以下の形式で返答してください:
            
            問題: [ここに問題文を入れる。重要な単語や概念を空欄にする]
            正解: [空欄に入るべき正解]
            説明: [なぜこれが正解なのか、テキストのどの部分に基づいているのかの説明]
            参照箇所: [テキストの関連部分を抜粋]
            """
        else:  # テキスト問題
            msg_content = """
            テキストの内容に基づいた記述式問題を1つ作成してください。
            以下の形式で返答してください:
            
            問題: [ここに問題文を入れる]
            正解例: [模範的な回答]
            キーワード: [回答に含まれるべき重要なキーワードをカンマ区切りで]
            説明: [評価基準と解説]
            参照箇所: [テキストの関連部分を抜粋]
            """
        
        human_msg = HumanMessage(content=msg_content)
        
        with st.spinner("問題を生成中..."):
            response = llm.invoke([system_msg, human_msg])
            
        response_content = response.content
        
        # 応答を解析
        lines = response_content.split('\n')
        question_data = {}
        
        current_key = None
        current_value = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if line.startswith("問題:"):
                current_key = "question"
                current_value = [line[3:].strip()]
            elif line.startswith("正解:") or line.startswith("正解例:"):
                if current_key:
                    question_data[current_key] = "\n".join(current_value)
                current_key = "answer"
                current_value = [line[3:].strip()]
            elif line.startswith("キーワード:"):
                if current_key:
                    question_data[current_key] = "\n".join(current_value)
                current_key = "keywords"
                current_value = [line[6:].strip()]
            elif line.startswith("説明:"):
                if current_key:
                    question_data[current_key] = "\n".join(current_value)
                current_key = "explanation"
                current_value = [line[3:].strip()]
            elif line.startswith("参照箇所:"):
                if current_key:
                    question_data[current_key] = "\n".join(current_value)
                current_key = "reference"
                current_value = [line[5:].strip()]
            else:
                if current_key:
                    current_value.append(line)
        
        if current_key:
            question_data[current_key] = "\n".join(current_value)
        
        # キーワードがある場合はリストに変換
        if "keywords" in question_data:
            question_data["keywords"] = [k.strip() for k in question_data["keywords"].split(',')]
        
        st.session_state.current_question = question_data
        st.session_state.question_type = question_type
        
    except Exception as e:
        st.error(f"問題生成エラー: {str(e)}")

# 回答のチェック
def check_answer(user_answer):
    if not user_answer:
        st.warning("回答を入力してください")
        return
        
    current_q = st.session_state.current_question
    question_type = st.session_state.question_type
    
    is_correct = False
    
    if question_type == "穴埋め問題":
        # 穴埋め問題の場合は完全一致
        is_correct = user_answer.strip() == current_q["answer"].strip()
    else:
        # テキスト問題の場合はキーワードが含まれているかチェック
        keywords = current_q.get("keywords", [])
        if keywords:
            matched_keywords = [k for k in keywords if k.lower() in user_answer.lower()]
            is_correct = len(matched_keywords) / len(keywords) >= 0.7  # 70%以上のキーワードが含まれていれば正解
        else:
            # キーワードがない場合はLLMで評価
            try:
                llm = st.session_state.llm
                
                system_msg = SystemMessage(content="""
                あなたは学習支援AIです。学習者の回答を評価してください。
                回答の正確さを0から10のスケールで評価し、スコアだけを返してください。
                """)
                
                human_msg = HumanMessage(content=f"""
                問題: {current_q["question"]}
                模範解答: {current_q["answer"]}
                学習者の回答: {user_answer}
                
                上記の学習者の回答を0から10のスケールで評価してください。7以上であれば十分正確と見なします。
                評価スコア（数字のみ）:
                """)
                
                with st.spinner("回答を評価中..."):
                    response = llm.invoke([system_msg, human_msg])
                    
                try:
                    score = int(response.content.strip())
                    is_correct = score >= 7
                except:
                    is_correct = False
            except:
                is_correct = False
    
    # 結果の表示
    if is_correct:
        st.success("正解です！")
        # 履歴に追加
        st.session_state.question_history.append({
            "question": current_q["question"],
            "user_answer": user_answer,
            "correct_answer": current_q["answer"],
            "is_correct": True
        })
        
        # 次の問題を生成
        time.sleep(2)
        st.session_state.current_question = None
        st.rerun()
    else:
        st.error("不正解です。")
        st.markdown("### 解説")
        st.markdown(current_q["explanation"])
        
        st.markdown("### 参照箇所")
        st.markdown(f"```\n{current_q['reference']}\n```")
        
        # 履歴に追加
        st.session_state.question_history.append({
            "question": current_q["question"],
            "user_answer": user_answer,
            "correct_answer": current_q["answer"],
            "is_correct": False
        })
        
        if st.button("次の問題へ"):
            st.session_state.current_question = None
            st.rerun()

# メイン関数
def main():
    setup_sidebar()
    
    if not st.session_state.authenticated:
        login_page()
    elif st.session_state.page == 2:
        upload_page()
    elif st.session_state.page == 3:
        learning_page()

if __name__ == "__main__":
    main()
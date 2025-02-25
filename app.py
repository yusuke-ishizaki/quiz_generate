import streamlit as st
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import SystemMessage, HumanMessage, AIMessage
import hashlib
import time
import random

# from dotenv import load_dotenv
# load_dotenv()
# # 環境変数の設定
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# LOGIN_ID = os.getenv("ADMIN")
# LOGIN_PASSWORD = os.getenv("PASSWORD")

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
if "previous_question_type" not in st.session_state:
    st.session_state.previous_question_type = None
if "user_input" not in st.session_state:
    st.session_state.user_input = ""
if "generation_attempts" not in st.session_state:
    st.session_state.generation_attempts = 0

# LLMの初期化
def initialize_llm():
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-lite-preview-02-05",
            google_api_key=GEMINI_API_KEY,
            temperature=0.9,  # 多様な質問を生成するために温度を上げる
            top_p=0.95,       # より多様な出力を許容
            top_k=40          # より多くの選択肢から次のトークンを選ぶ
        )
        return llm
    except Exception as e:
        st.error(f"LLMの初期化エラー: {str(e)}")
        return None

# ユーザー入力をクリアする関数
def clear_user_input():
    st.session_state.user_input = ""

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
                st.session_state.user_input = ""
                st.session_state.generation_attempts = 0
                st.rerun()
                
            st.write("---")
            if st.button("ログアウト"):
                st.session_state.authenticated = False
                st.session_state.page = 1
                st.session_state.user_input = ""
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
        horizontal=True,
        on_change=reset_question  # ラジオボタンが変更されたときに問題をリセット
    )
    
    # 新しい問題を生成
    if st.session_state.current_question is None:
        generate_new_question(question_type)
    
    # 現在の問題を表示
    if st.session_state.current_question:
        st.markdown("## 問題")
        st.markdown(st.session_state.current_question["question"])
        
        # 質問再生成ボタン
        if st.button("質問を再生成"):
            st.session_state.current_question = None
            st.session_state.user_input = ""  # ユーザー入力をクリア
            st.session_state.generation_attempts = 0  # 生成試行回数をリセット
            st.rerun()
        
        # 回答入力（textareaに変更）
        user_answer = st.text_area("あなたの回答を入力してください", 
                                    value=st.session_state.user_input,
                                    height=150,
                                    key="answer_input")
        
        if st.button("回答を提出"):
            st.session_state.user_input = user_answer  # 回答を保存
            check_answer(user_answer)

# 問題タイプが変更されたときに問題をリセットする関数
def reset_question():
    st.session_state.current_question = None
    st.session_state.user_input = ""  # ユーザー入力もクリア
    st.session_state.generation_attempts = 0  # 生成試行回数をリセット

# 質問が過去に出題されたものと同じかチェックする関数
def is_duplicate_question(question_text):
    for q in st.session_state.question_history:
        # 簡易的な比較：質問のテキストが80%以上一致していれば重複とみなす
        # より高度な方法としては、embeddings比較などが考えられる
        similarity = sum(1 for a, b in zip(question_text, q["question"]) if a == b) / max(len(question_text), len(q["question"]))
        if similarity > 0.8:
            return True
    return False

# 新しい問題の生成
def generate_new_question(question_type):
    # 最大試行回数（5回試行しても新しい問題が生成できなければ諦める）
    max_attempts = 5
    st.session_state.generation_attempts += 1
    
    if st.session_state.generation_attempts > max_attempts:
        st.warning("新しい問題の生成に失敗しました。別のタイプの問題を選択するか、別のファイルをアップロードしてみてください。")
        st.session_state.generation_attempts = 0
        return
    
    try:
        llm = st.session_state.llm
        if llm is None:
            st.session_state.llm = initialize_llm()
            llm = st.session_state.llm
            
        # テキストの分析と分割
        text_parts = split_text_content(st.session_state.file_content)
        
        # 前回と異なる部分を選択
        selected_part = select_text_part(text_parts)
            
        system_msg = SystemMessage(content=f"""
        あなたは学習支援AIです。与えられたテキストコンテンツを元に学習者向けの質問を作成してください。
        質問は日本語で作成し、回答も日本語で評価してください。
        
        同じ内容の質問を繰り返さないでください。毎回異なる視点や角度から質問を作成してください。
        テキストの異なる部分に焦点を当て、様々なレベルの理解度をテストする質問を作成してください。
        必ずテキスト内に根拠を持つ質問のみを作成し、回答者に曖昧な推測を行わせる質問は作成しないでください。
        
        今回はテキストの以下の部分に焦点を当てて質問を作成してください:
        {selected_part}
        """)
        
        msg_content = ""
        if question_type == "穴埋め問題":
            msg_content = """
            テキストの内容に基づいた穴埋め問題を1つ作成してください。
            これまでに出題した問題とは異なる内容を選んでください。
            以下の形式で返答してください:
            
            問題: [ここに問題文を入れる。重要な単語や概念を空欄にする]
            正解: [空欄に入るべき正解]
            説明: [なぜこれが正解なのか、テキストのどの部分に基づいているのかの説明]
            参照箇所: [テキストの関連部分を抜粋]
            """
        else:  # テキスト問題
            msg_content = """
            テキストの内容に基づいた記述式問題を1つ作成してください。
            これまでに出題した問題とは異なる内容を選んでください。
            以下の形式で返答してください:
            
            問題: [ここに問題文を入れる]
            正解例: [模範的な回答]
            キーワード: [回答に含まれるべき重要なキーワードをカンマ区切りで]
            説明: [評価基準と解説]
            参照箇所: [テキストの関連部分を抜粋]
            """
        
        # 質問履歴を追加して多様性を高める
        if st.session_state.question_history:
            msg_content += "\n\n以下の問題はすでに出題されているので、別の内容を選んでください:\n"
            for idx, q in enumerate(st.session_state.question_history[-5:]):  # 直近5問のみ参照
                msg_content += f"{idx+1}. {q['question']}\n"
        
        # 温度をランダム化して多様性を上げる
        temperature = 0.7 + (random.random() * 0.3)  # 0.7～1.0の間でランダム
        llm.temperature = temperature
        
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
        
        # 重複チェック
        if "question" in question_data and is_duplicate_question(question_data["question"]):
            # 重複が見つかった場合は再帰的に再生成
            return generate_new_question(question_type)
        
        st.session_state.current_question = question_data
        st.session_state.question_type = question_type
        st.session_state.generation_attempts = 0  # 成功したらカウンターをリセット
        
    except Exception as e:
        st.error(f"問題生成エラー: {str(e)}")
        # エラーが発生した場合も再試行
        time.sleep(1)
        return generate_new_question(question_type)

# テキストを複数のチャンクに分割する関数
def split_text_content(content):
    # 段落ごとに分割
    paragraphs = [p for p in content.split('\n\n') if p.strip()]
    
    # 短すぎる段落を結合
    chunks = []
    current_chunk = ""
    
    for p in paragraphs:
        if len(current_chunk) + len(p) < 500:  # 文字数制限
            current_chunk += p + "\n\n"
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = p + "\n\n"
    
    if current_chunk:
        chunks.append(current_chunk)
    
    # チャンクが少なすぎる場合は別の方法で分割
    if len(chunks) < 3:
        chunks = []
        sentences = content.replace('\n', ' ').split('。')
        current_chunk = ""
        
        for s in sentences:
            if len(current_chunk) + len(s) < 300:
                current_chunk += s + "。"
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = s + "。"
        
        if current_chunk:
            chunks.append(current_chunk)
    
    return chunks

# テキストの異なる部分を選択する関数
def select_text_part(text_parts):
    if not text_parts:
        return ""
        
    # 前回使用したチャンクを記録する状態変数を追加
    if "used_chunks" not in st.session_state:
        st.session_state.used_chunks = []
    
    # まだ使用していないチャンクがあれば、そこから選択
    unused_chunks = [i for i, _ in enumerate(text_parts) if i not in st.session_state.used_chunks]
    
    if unused_chunks:
        selected_idx = random.choice(unused_chunks)
        st.session_state.used_chunks.append(selected_idx)
    else:
        # すべてのチャンクを使い切った場合はリセット
        selected_idx = random.randrange(len(text_parts))
        st.session_state.used_chunks = [selected_idx]
    
    # 全テキストのコンテキストも少し与える
    if len(text_parts) > 1 and random.random() < 0.3:  # 30%の確率で隣接部分も追加
        context_idx = max(0, selected_idx - 1) if random.random() < 0.5 else min(len(text_parts) - 1, selected_idx + 1)
        return text_parts[selected_idx] + "\n\n追加コンテキスト:\n" + text_parts[context_idx]
    
    return text_parts[selected_idx]

# 回答のチェック
def check_answer(user_answer):
    if not user_answer:
        st.warning("回答を入力してください")
        return
        
    current_q = st.session_state.current_question
    question_type = st.session_state.question_type
    
    is_correct = False
    
    if question_type == "穴埋め問題":
        # 穴埋め問題の場合は複数の正解を許容
        correct_answers = [a.strip() for a in current_q["answer"].split('|')]
        is_correct = any(user_answer.strip() == answer for answer in correct_answers)
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
        st.session_state.user_input = ""  # 入力フィールドをクリア
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
        
        if st.button("次の問題へ", on_click=clear_user_input):
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
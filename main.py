import os
import datetime
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.sql_database import SQLDatabase
from langchain.agents import create_sql_agent
from langchain.memory import ConversationBufferMemory

from sqlalchemy import create_engine, MetaData, Table

# --- 데이터베이스 로깅 설정 ---
engine = None
query_history_table = None

def setup_logging():
    """로깅을 위한 데이터베이스 연결 및 테이블 객체를 초기화합니다."""
    global engine, query_history_table
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        print("경고: 로깅을 위한 DATABASE_URL이 .env에 설정되지 않았습니다. 로그가 기록되지 않습니다.")
        return
    
    engine = create_engine(DATABASE_URL)
    metadata = MetaData()
    # 데이터베이스에서 기존 테이블 정보를 읽어옵니다.
    query_history_table = Table('query_history', metadata, autoload_with=engine)

def log_interaction(user_query, generated_sql, status, final_response):
    """상호작용 내역을 query_history 테이블에 기록합니다."""
    if engine is None or query_history_table is None:
        return # 로깅 설정이 안되어 있으면 함수 종료

    with engine.connect() as connection:
        try:
            insert_stmt = query_history_table.insert().values(
                timestamp=datetime.datetime.utcnow(),
                user_query_nl=user_query,
                generated_sql=str(generated_sql),
                execution_status=status,
                final_response_nl=final_response
            )
            connection.execute(insert_stmt)
            connection.commit()
        except Exception as e:
            print(f"데이터베이스에 로그 기록 실패: {e}")

def main():
    """
    메인 실행 함수: 대화형 CLI를 처리하고 모든 상호작용을 기록합니다.
    """
    # 1. 환경 변수 로드
    load_dotenv()

    if not os.getenv("GOOGLE_API_KEY") or not os.getenv("DATABASE_URL"):
        raise ValueError(".env 파일에 GOOGLE_API_KEY 또는 DATABASE_URL이 설정되지 않았습니다.")

    print("환경 변수 로드 완료.")

    # 로깅을 위한 데이터베이스 연결 설정
    try:
        setup_logging()
        print("데이터베이스 로깅 기능 활성화 완료.")
    except Exception as e:
        print(f"경고: 데이터베이스 로깅 기능 활성화 실패. 로그가 기록되지 않습니다. 오류: {e}")

    # 2. LLM 초기화
    llm = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0)
    print("Gemini LLM 초기화 완료.")

    # 3. 에이전트용 데이터베이스 연결
    db = SQLDatabase.from_uri(os.getenv("DATABASE_URL"))
    print("에이전트용 데이터베이스 연결 완료.")

    # 4. 대화 메모리 설정
    memory = ConversationBufferMemory(memory_key="chat_history", input_key="input", return_messages=True)
    print("대화 메모리 생성 완료.")

    # 5. SQL 에이전트 생성 (메모리 및 중간 단계 반환 기능 추가)
    agent_executor = create_sql_agent(
        llm=llm,
        db=db,
        agent_type="zero-shot-react-description",
        verbose=True,
        memory=memory,
        handle_parsing_errors=True,
        return_intermediate_steps=True # 생성된 SQL을 얻기 위해 중간 단계 반환
    )
    print("SQL 에이전트 생성 완료. 이제 대화형 챗봇을 시작합니다.")
    print("종료하시려면 'exit' 또는 '종료'를 입력하세요.")

    # 6. 대화형 CLI 루프
    while True:
        user_input = input("\n[사용자]: ")
        if user_input.lower() in ["exit", "종료"]:
            print("챗봇을 종료합니다.")
            break
        
        generated_sql = "N/A"
        final_answer = "오류 발생"
        status = "Error"

        try:
            # 에이전트 실행
            response = agent_executor.invoke({"input": user_input})
            final_answer = response.get("output", "답변을 찾을 수 없습니다.")
            print("[챗봇]:", final_answer)

            # 중간 단계에서 SQL 추출
            if response.get("intermediate_steps"):
                for step in response["intermediate_steps"]:
                    if step[0].tool == 'sql_db_query':
                        generated_sql = step[0].tool_input
                        break
            status = "Success"

        except Exception as e:
            final_answer = f"오류가 발생했습니다: {e}"
            print(final_answer)
            status = "Error"
        
        # DB에 상호작용 기록
        log_interaction(
            user_query=user_input,
            generated_sql=generated_sql,
            status=status,
            final_response=final_answer
        )

if __name__ == "__main__":
    main()

알겠습니다. 요청하신 기능들을 포함한 **'LangChain & Gemini 기반 대화형 SQL 챗봇'** 프로젝트의 명세서를 체계적으로 정리해 드리겠습니다. 이 명세서는 프로젝트의 목표, 기능, 아키텍처, 개발 단계를 명확히 정의하여 실제 개발을 위한 청사진으로 사용할 수 있습니다.

-----

### **프로젝트 명세서: LangChain & Gemini 기반 대화형 SQL 챗봇**

#### **1. 프로젝트 개요**

본 프로젝트는 자연어(Natural Language)를 이해하여 SQL(Structured Query Language)로 변환하고, 이를 로컬 PostgreSQL 데이터베이스에서 실행하여 사용자에게 통찰력 있는 답변을 제공하는 대화형 챗봇 시스템을 구축하는 것을 목표로 한다. 사용자는 복잡한 SQL 구문을 몰라도 일상적인 언어로 데이터 관련 질문을 하고 답변을 받을 수 있다. 시스템은 LangChain 프레임워크를 기반으로 하며, Google의 Gemini API를 핵심 언어 모델로 사용한다. 모든 사용자 질문과 시스템의 답변은 자동으로 기록되어 추적 및 분석이 가능하다.

#### **2. 시스템 목표**

  * **직관적인 데이터 접근성:** 사용자가 자연어 질문을 통해 데이터베이스와 직접 상호작용할 수 있는 환경을 제공한다.
  * **대화의 연속성:** 단발성 질문-답변을 넘어, 이전 대화의 맥락(Context)을 기억하여 후속 질문에 효과적으로 대응하는 대화형 인터페이스를 구현한다.
  * **안정적인 데이터베이스 연동:** 로컬 PostgreSQL 서버에 안정적으로 연결하고, 생성된 SQL을 안전하게 실행하여 정확한 결과를 도출한다.
  * **상호작용 기록 관리:** 사용자의 모든 질의 내역과 챗봇의 응답 과정을 로그 파일 또는 데이터베이스에 저장하여 서비스 개선 및 감사 추적(Audit Trail)의 기반을 마련한다.

#### **3. 주요 기능 명세**

**3.1. 자연어-SQL 변환 (NL-to-SQL Conversion)**

  * **입력:** 사용자의 자연어 질문 (예: "지난달에 가장 많이 등록한 사용자 5명의 이메일은 뭐야?")
  * **처리:**
      * LangChain의 SQL 에이전트(`create_sql_agent`)를 사용하여 입력된 질문을 처리한다.
      * 에이전트는 PostgreSQL 데이터베이스 스키마(테이블, 컬럼, 관계) 정보를 동적으로 조회한다.
      * 조회된 스키마 정보와 사용자 질문을 Gemini API가 이해할 수 있는 형태의 프롬프트로 조합한다.
      * Gemini API는 해당 프롬프트를 기반으로 가장 적합한 PostgreSQL 구문의 SQL 쿼리를 생성한다.
  * **출력:** 실행 가능한 SQL 쿼리 문자열 (예: `SELECT email FROM users ORDER BY registration_date DESC LIMIT 5;`)

**3.2. SQL 실행 및 결과 처리 (SQL Execution & Result Handling)**

  * **입력:** 3.1에서 생성된 SQL 쿼리 문자열
  * **처리:**
      * LangChain 에이전트는 SQLAlchemy를 통해 로컬 PostgreSQL 데이터베이스에 쿼리를 실행한다.
      * 쿼리 실행 중 발생하는 모든 오류(예: 구문 오류, 권한 오류)를 감지하고 처리한다.
      * 성공적으로 실행된 경우, 결과 데이터를 가져온다. (예: `[('user1@test.com',), ('user2@test.com',), ...]`)
      * 추출된 결과 데이터와 원본 질문을 다시 Gemini API에 전달하여 사람이 이해하기 쉬운 자연어 답변을 생성하도록 요청한다.
  * **출력:** 최종 사용자에게 보여줄 자연어 답변 (예: "지난달 가장 많이 등록한 사용자 5명의 이메일은 user1@test.com, user2@test.com, ... 입니다.")

**3.3. 대화형 인터페이스 (Conversational Interface)**

  * **구현 방식:**
      * 세션(Session) 기반의 대화 메모리(`ConversationBufferMemory` 등)를 LangChain 에이전트에 통합한다.
      * 사용자가 "그럼 그 사용자들의 가입일은?"과 같은 후속 질문을 하면, 에이전트는 이전 대화("가장 많이 등록한 사용자 5명")의 맥락을 참조하여 "그 사용자들"이 누구인지 파악한다.
      * 사용자가 '종료' 또는 'exit'를 입력하기 전까지 대화 루프(Loop)가 지속되는 CLI(Command-Line Interface) 환경을 제공한다.

**3.4. 쿼리 히스토리 저장 (Query History Logging)**

  * **저장 시점:** 사용자의 질문 하나에 대한 답변이 완료될 때마다 기록된다.
  * **저장 내용:**
      * `Timestamp`: 질의가 발생한 시간 (ISO 8601 형식)
      * `User_Query_NL`: 사용자가 입력한 원본 자연어 질문
      * `Generated_SQL`: LLM이 생성한 SQL 쿼리
      * `Execution_Status`: 쿼리 실행 성공/실패 여부
      * `SQL_Result`: (선택적) 쿼리 실행 결과의 요약 또는 원본
      * `Final_Response_NL`: 사용자에게 제공된 최종 자연어 답변
  * **저장 방식:**
      * **1안 (파일 기반):** `chat_history.log` 또는 `history.csv` 파일에 구조화된 텍스트 형태로 누적 저장한다.
      * **2안 (DB 기반):** PostgreSQL 내부에 `query_history` 테이블을 생성하고, 위 항목들을 컬럼으로 하여 체계적으로 저장한다. (권장)

#### **4. 기술 스택 및 아키텍처**

  * **프레임워크:** LangChain, LangChain-Google-Gemini
  * **언어 모델(LLM):** Google Gemini API (예: `gemini-pro`)
  * **데이터베이스:** PostgreSQL (로컬 서버)
  * **DB 연결:** SQLAlchemy, `psycopg2-binary`
  * **개발 언어:** Python 3.9+
  * **환경 변수 관리:** `python-dotenv`

**시스템 아키텍처 흐름도:**

```
[사용자] <--> [CLI/UI]
   |
   V
[LangChain SQL Agent] <--> [대화 메모리 (Session History)]
   |
   | 1. NL Query + Schema -> [Gemini API] -> Generated SQL
   |
   V
[SQLAlchemy Engine] -> [PostgreSQL DB] (실행)
   |
   | 2. SQL Result -> [Gemini API] -> Final NL Response
   |
   V
[CLI/UI] (답변 출력)
   |
   +-----> [히스토리 로거] -> [로그 파일 or DB Table]
```

#### **5. 개발 단계 (Roadmap)**

  * **1단계: 환경 설정 및 DB 연동**

      * Python 가상환경 설정 및 필요 라이브러리 설치.
      * Gemini API 키 발급 및 `.env` 파일 설정.
      * SQLAlchemy를 사용하여 로컬 PostgreSQL DB와 연결을 확인하고, 샘플 데이터가 담긴 테이블 생성.

  * **2단계: 핵심 기능 구현 (단일 질의응답)**

      * LLM(Gemini) 및 DB 객체를 초기화한다.
      * `create_sql_agent`를 이용해 메모리가 없는 기본 SQL 에이전트를 생성한다.
      * 단일 자연어 질문에 대해 SQL 생성 및 실행, 자연어 답변까지의 흐름을 구현하고 검증한다.

  * **3. 단계: 대화 기능 및 인터페이스 구현**

      * 에이전트에 `ConversationBufferMemory`를 추가하여 대화의 맥락을 유지하도록 수정한다.
      * 사용자가 연속적으로 질문할 수 있는 `while` 루프 기반의 CLI를 개발한다.
      * 후속 질문이 정상적으로 처리되는지 테스트한다.

  * **4. 단계: 히스토리 저장 기능 구현**

      * 질의응답 사이클이 끝날 때마다 명세된 항목들을 로깅하는 함수를 구현한다.
      * 로그 저장 방식으로 파일 또는 DB 테이블 중 하나를 선택하여 적용한다.

  * **5. 단계: 안정화 및 고도화**

      * 오류 처리 로직(잘못된 SQL, DB 연결 실패 등)을 강화한다.
      * 보안 강화를 위해 DB 연결 계정을 읽기 전용(Read-only)으로 제한한다.
      * (선택) Streamlit 또는 Gradio를 사용하여 간단한 웹 UI를 구축한다.

#### **6. 사전 준비 및 요구사항**

  * Python 3.9 이상 설치
  * 로컬 환경에 PostgreSQL 서버 설치 및 실행
  * 데이터 쿼리를 테스트할 샘플 데이터베이스 및 테이블 사전 구성
  * Google Cloud 프로젝트 및 활성화된 Gemini API 키

-----

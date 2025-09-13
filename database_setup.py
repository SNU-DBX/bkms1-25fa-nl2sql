import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, Column, Integer, String, Float, DateTime, MetaData, Table
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from sqlalchemy.engine.url import make_url
import datetime

# --- Configuration ---
TEST_DATABASE_NAME = "testnl2sql"

# .env 파일에서 환경 변수 로드
load_dotenv()

# 기본 데이터베이스 연결 URL 가져오기 (DB 생성을 위해)
BASE_DATABASE_URL = os.getenv("DATABASE_URL")

if not BASE_DATABASE_URL:
    raise ValueError("DATABASE_URL 환경 변수가 설정되지 않았습니다. .env 파일을 확인하세요.")

def setup_database():
    """
    테스트용 데이터베이스와 테이블, 샘플 데이터를 설정합니다.
    1. 'testnl2sql' 데이터베이스를 생성합니다.
    2. 해당 데이터베이스에 'test_users', 'test_orders', 'query_history' 테이블을 생성합니다.
    3. 'test_users', 'test_orders'에 샘플 데이터를 삽입합니다.
    """
    try:
        base_url = make_url(BASE_DATABASE_URL)
        # 데이터베이스를 생성하려면 'postgres'와 같은 기본 DB에 연결해야 합니다.
        db_creation_url = base_url.set(database="postgres")
        
        engine = create_engine(db_creation_url, isolation_level="AUTOCOMMIT")
        with engine.connect() as connection:
            # 데이터베이스 존재 여부 확인
            result = connection.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{TEST_DATABASE_NAME}'"))
            db_exists = result.scalar() == 1
            
            if not db_exists:
                print(f"'{TEST_DATABASE_NAME}' 데이터베이스를 생성합니다...")
                connection.execute(text(f"CREATE DATABASE {TEST_DATABASE_NAME}"))
                print("데이터베이스 생성 완료.")
            else:
                print(f"'{TEST_DATABASE_NAME}' 데이터베이스가 이미 존재합니다.")

    except OperationalError as e:
        print(f"데이터베이스 연결 오류: {e}")
        print(".env 파일의 DATABASE_URL이 정확한지, PostgreSQL 서버가 실행 중인지 확인하세요.")
        return
    except Exception as e:
        print(f"데이터베이스 생성 중 오류 발생: {e}")
        return

    # 이제 새로 생성/확인된 testnl2sql 데이터베이스에 연결합니다.
    test_db_url = base_url.set(database=TEST_DATABASE_NAME)
    engine = create_engine(test_db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print(f"'{TEST_DATABASE_NAME}' 데이터베이스에 성공적으로 연결되었습니다.")
        
        metadata = MetaData()

        # 'test_users' 테이블 정의
        users_table = Table('test_users', metadata,
            Column('user_id', Integer, primary_key=True),
            Column('username', String(50), nullable=False),
            Column('email', String(100), unique=True, nullable=False),
            Column('registration_date', DateTime, default=datetime.datetime.utcnow)
        )

        # 'test_orders' 테이블 정의
        orders_table = Table('test_orders', metadata,
            Column('order_id', Integer, primary_key=True),
            Column('user_id', Integer, nullable=False),
            Column('amount', Float, nullable=False),
            Column('order_date', DateTime, default=datetime.datetime.utcnow)
        )

        # 'query_history' 테이블 정의 (이것은 실제 사용될 테이블)
        query_history_table = Table('query_history', metadata,
            Column('id', Integer, primary_key=True),
            Column('timestamp', DateTime, default=datetime.datetime.utcnow),
            Column('user_query_nl', String, nullable=False),
            Column('generated_sql', String, nullable=False),
            Column('execution_status', String(50), nullable=False),
            Column('final_response_nl', String, nullable=False)
        )

        metadata.create_all(engine)
        print("테이블('test_users', 'test_orders', 'query_history')이 성공적으로 생성되었습니다.")

        # 샘플 데이터 추가 (기존 데이터가 없을 경우)
        if session.query(users_table).count() == 0:
            sample_users = [
                {'user_id': 1, 'username': 'Alice', 'email': 'alice@example.com', 'registration_date': datetime.datetime(2023, 1, 15)},
                {'user_id': 2, 'username': 'Bob', 'email': 'bob@example.com', 'registration_date': datetime.datetime(2023, 2, 20)},
                {'user_id': 3, 'username': 'Charlie', 'email': 'charlie@example.com', 'registration_date': datetime.datetime(2023, 3, 25)},
            ]
            session.execute(users_table.insert(), sample_users)
            session.commit()
            print("샘플 'test_users' 데이터가 추가되었습니다.")
        else:
            print("'test_users' 테이블에 이미 데이터가 존재합니다.")

        if session.query(orders_table).count() == 0:
            sample_orders = [
                {'order_id': 1, 'user_id': 1, 'amount': 150.50, 'order_date': datetime.datetime(2023, 1, 20)},
                {'order_id': 2, 'user_id': 1, 'amount': 75.00, 'order_date': datetime.datetime(2023, 2, 25)},
                {'order_id': 3, 'user_id': 2, 'amount': 200.00, 'order_date': datetime.datetime(2023, 3, 1)},
                {'order_id': 4, 'user_id': 3, 'amount': 50.25, 'order_date': datetime.datetime(2023, 4, 5)},
            ]
            session.execute(orders_table.insert(), sample_orders)
            session.commit()
            print("샘플 'test_orders' 데이터가 추가되었습니다.")
        else:
            print("'test_orders' 테이블에 이미 데이터가 존재합니다.")

        print("\n✅ 테스트 데이터베이스 설정이 완료되었습니다.")
        print(f"데이터베이스 이름: {TEST_DATABASE_NAME}")
        print("이제 메인 애플리케이션에서는 .env 파일의 DATABASE_URL에 이 데이터베이스를 사용하도록 설정할 수 있습니다.")
        print(f"예: DATABASE_URL=postgresql://user:password@host:port/{TEST_DATABASE_NAME}")

    except Exception as e:
        print(f"테이블 생성 또는 데이터 삽입 중 오류 발생: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    setup_database()
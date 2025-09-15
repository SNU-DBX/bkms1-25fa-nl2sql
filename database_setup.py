import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, Column, Integer, String, Float, DateTime, MetaData, Table
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from sqlalchemy.engine.url import make_url
import datetime

# --- Configuration ---
TEST_DATABASE_NAME = "testnl2sql"

# Load environment variables from .env file
load_dotenv()

# Get the base database connection URL (for creating the DB)
BASE_DATABASE_URL = os.getenv("DATABASE_URL")

if not BASE_DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set. Please check your .env file.")

def setup_database():
    """
    Sets up the test database, tables, and sample data.
    1. Creates the 'testnl2sql' database.
    2. Creates 'test_users', 'test_orders', and 'query_history' tables in that database.
    3. Inserts sample data into 'test_users' and 'test_orders'.
    """
    try:
        base_url = make_url(BASE_DATABASE_URL)
        # To create a database, you need to connect to a default DB like 'postgres'.
        db_creation_url = base_url.set(database="postgres")
        
        engine = create_engine(db_creation_url, isolation_level="AUTOCOMMIT")
        with engine.connect() as connection:
            # Check if the database exists
            result = connection.execute(text(f"SELECT 1 FROM pg_database WHERE datname='{TEST_DATABASE_NAME}'"))
            db_exists = result.scalar() == 1
            
            if not db_exists:
                print(f"Creating database '{TEST_DATABASE_NAME}'...")
                connection.execute(text(f"CREATE DATABASE {TEST_DATABASE_NAME}"))
                print("Database created successfully.")
            else:
                print(f"Database '{TEST_DATABASE_NAME}' already exists.")

    except OperationalError as e:
        print(f"Database connection error: {e}")
        print("Please ensure the DATABASE_URL in your .env file is correct and the PostgreSQL server is running.")
        return
    except Exception as e:
        print(f"An error occurred during database creation: {e}")
        return

    # Now, connect to the newly created/verified testnl2sql database.
    test_db_url = base_url.set(database=TEST_DATABASE_NAME)
    engine = create_engine(test_db_url)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        print(f"Successfully connected to the '{TEST_DATABASE_NAME}' database.")
        
        metadata = MetaData()

        # Define 'test_users' table
        users_table = Table('test_users', metadata,
            Column('user_id', Integer, primary_key=True),
            Column('username', String(50), nullable=False),
            Column('email', String(100), unique=True, nullable=False),
            Column('registration_date', DateTime, default=datetime.datetime.utcnow)
        )

        # Define 'test_orders' table
        orders_table = Table('test_orders', metadata,
            Column('order_id', Integer, primary_key=True),
            Column('user_id', Integer, nullable=False),
            Column('amount', Float, nullable=False),
            Column('order_date', DateTime, default=datetime.datetime.utcnow)
        )

        # Define 'query_history' table (this is the table that will be actually used)
        query_history_table = Table('query_history', metadata,
            Column('id', Integer, primary_key=True),
            Column('timestamp', DateTime, default=datetime.datetime.utcnow),
            Column('user_query_nl', String, nullable=False),
            Column('generated_sql', String, nullable=False),
            Column('execution_status', String(50), nullable=False),
            Column('final_response_nl', String, nullable=False)
        )

        metadata.create_all(engine)
        print("Tables ('test_users', 'test_orders', 'query_history') created successfully.")

        # Add sample data (if it doesn't exist)
        if session.query(users_table).count() == 0:
            sample_users = [
                {'user_id': 1, 'username': 'Alice', 'email': 'alice@example.com', 'registration_date': datetime.datetime(2023, 1, 15)},
                {'user_id': 2, 'username': 'Bob', 'email': 'bob@example.com', 'registration_date': datetime.datetime(2023, 2, 20)},
                {'user_id': 3, 'username': 'Charlie', 'email': 'charlie@example.com', 'registration_date': datetime.datetime(2023, 3, 25)},
            ]
            session.execute(users_table.insert(), sample_users)
            session.commit()
            print("Sample 'test_users' data has been added.")
        else:
            print("Data already exists in the 'test_users' table.")

        if session.query(orders_table).count() == 0:
            sample_orders = [
                {'order_id': 1, 'user_id': 1, 'amount': 150.50, 'order_date': datetime.datetime(2023, 1, 20)},
                {'order_id': 2, 'user_id': 1, 'amount': 75.00, 'order_date': datetime.datetime(2023, 2, 25)},
                {'order_id': 3, 'user_id': 2, 'amount': 200.00, 'order_date': datetime.datetime(2023, 3, 1)},
                {'order_id': 4, 'user_id': 3, 'amount': 50.25, 'order_date': datetime.datetime(2023, 4, 5)},
            ]
            session.execute(orders_table.insert(), sample_orders)
            session.commit()
            print("Sample 'test_orders' data has been added.")
        else:
            print("Data already exists in the 'test_orders' table.")

        print("\n✅ Test database setup is complete.")
        print(f"Database Name: {TEST_DATABASE_NAME}")
        print("You can now set the DATABASE_URL in your .env file to use this database in the main application.")
        print(f"Example: DATABASE_URL=postgresql://user:password@host:port/{TEST_DATABASE_NAME}")

    except Exception as e:
        print(f"An error occurred during table creation or data insertion: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    setup_database()

import os
import datetime
import sys
from dotenv import load_dotenv

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.sql_database import SQLDatabase
from langchain.agents import create_sql_agent
from langchain.memory import ConversationBufferMemory
from langchain_core.rate_limiters import InMemoryRateLimiter


from sqlalchemy import create_engine, MetaData, Table
from sqlalchemy.engine.url import make_url

# Import function and variable from database_setup.py
from database_setup import setup_database as setup_test_database, TEST_DATABASE_NAME

# --- Database Logging Setup ---
# Logging is always recorded in the 'query_history' table of the test database.
LOGGING_DATABASE_NAME = TEST_DATABASE_NAME
engine = None
query_history_table = None

def setup_logging():
    """
    Initializes the connection to the dedicated logging database ('testnl2sql') and the table object.
    It gets connection info from the DATABASE_URL in .env but hardcodes the database name to 'testnl2sql'.
    """
    global engine, query_history_table
    BASE_DATABASE_URL = os.getenv("DATABASE_URL")
    if not BASE_DATABASE_URL:
        print(f"Warning: DATABASE_URL for logging is not set in .env. Logs for {LOGGING_DATABASE_NAME} will not be recorded.")
        return

    try:
        # Parse the URL and change only the database name to LOGGING_DATABASE_NAME
        base_url = make_url(BASE_DATABASE_URL)
        log_db_url = base_url.set(database=LOGGING_DATABASE_NAME)
        
        engine = create_engine(log_db_url)
        metadata = MetaData()
        # Load existing table information from the database.
        query_history_table = Table('query_history', metadata, autoload_with=engine)
        print(f"Connected to logging database '{engine.url.database}'.")
    except Exception as e:
        print(f"Warning: Logging database connection failed. Logs will not be recorded. Error: {e}")
        engine = None
        query_history_table = None

def log_interaction(user_query, generated_sql, status, final_response):
    """Logs the interaction details to the query_history table."""
    if engine is None or query_history_table is None:
        return # If logging is not set up, exit the function

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
            print(f"Failed to write log to database: {e}")

def main():
    """
    Main execution function: Handles the interactive CLI and logs all interactions.
    """
    # 1. Load environment variables
    load_dotenv()

    if not os.getenv("GOOGLE_API_KEY") or not os.getenv("DATABASE_URL"):
        raise ValueError("GOOGLE_API_KEY or DATABASE_URL is not set in the .env file.")

    print("Environment variables loaded successfully.")

    # 2. Select database to use
    print("\nWhich database would you like to connect to?")
    print(f"  1. Test Database ({TEST_DATABASE_NAME})")
    print("  2. Database specified in .env file")
    choice = input("Select (1 or 2): ")

    db_url_to_use = None
    base_db_url_str = os.getenv("DATABASE_URL")

    if choice == '1':
        print("\nChecking and preparing the test database...")
        setup_test_database() # Create/verify database and tables
        
        # Create URL for the test DB
        url_obj = make_url(base_db_url_str)
        test_db_url = url_obj.set(database=TEST_DATABASE_NAME)
        db_url_to_use = str(test_db_url)
        print(f"Using the test database '{TEST_DATABASE_NAME}'.")

    elif choice == '2':
        db_url_to_use = base_db_url_str
        print("Using the database specified in .env.")
    
    else:
        print("Invalid choice. Exiting program.", file=sys.stderr)
        sys.exit(1)

    # Set up logging database connection (uses testnl2sql regardless of choice)
    # If test DB was chosen, setup_test_database() was already called, so the logging DB is ready.
    setup_logging()

    # 3. Initialize LLM
    # llm = ChatTogether(model="deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free", temperature=0, max_retries=3)
    rate_limiter = InMemoryRateLimiter(
        requests_per_second=0.15,  # We can only make a request once every 6.67 seconds!!
        check_every_n_seconds=0.5,  # Wake up every 100 ms to check whether allowed to make a request,
        max_bucket_size=3,  # Controls the maximum burst size.
    )

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.5, max_retries=2, rate_limiter=rate_limiter)
    print("Gemini LLM initialized successfully.")

    # 4. Connect agent to the database (the one chosen by the user)
    db = SQLDatabase.from_uri(db_url_to_use)
    print(f"Agent connected to database '{db._engine.url.database}'.")

    # 5. Set up conversation memory
    memory = ConversationBufferMemory(memory_key="chat_history", input_key="input", return_messages=True)
    print("Conversation memory created successfully.")

    # 6. Create SQL Agent
    agent_executor = create_sql_agent(
        llm=llm,
        db=db,
        agent_type="tool-calling",
        verbose=True,
        memory=memory,
        handle_parsing_errors=True,
        return_intermediate_steps=True
    )
    print("\nSQL Agent created successfully. Starting the interactive chatbot now.")
    print("To exit, type 'exit'.")

    # 7. Interactive CLI loop
    while True:
        user_input = input("\n[User]: ")
        if user_input.lower() == "exit":
            print("Exiting the chatbot.")
            break
        
        generated_sql = "N/A"
        final_answer = "An error occurred"
        status = "Error"

        try:
            response = agent_executor.invoke({"input": user_input})
            final_answer = response.get("output", "Could not find an answer.")
            print("[Chatbot]:", final_answer)

            if response.get("intermediate_steps"):
                for step in response["intermediate_steps"]:
                    if step[0].tool == 'sql_db_query':
                        generated_sql = step[0].tool_input
                        break
            status = "Success"

        except Exception as e:
            final_answer = f"An error occurred: {e}"
            print(final_answer)
            status = "Error"
        
        log_interaction(
            user_query=user_input,
            generated_sql=generated_sql,
            status=status,
            final_response=final_answer
        )

if __name__ == "__main__":
    main()

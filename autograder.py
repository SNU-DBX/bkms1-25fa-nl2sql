
import os
import sys
import glob
import importlib.util
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text, inspect
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.sql_database import SQLDatabase
from langchain.agents import create_sql_agent

# --- Configuration ---
SUBMISSIONS_DIR = "/opt/pm883-1/dongkwang/ta/nl2sql/submissions"
SOLUTION_QUERIES_DIR = "/opt/pm883-1/dongkwang/ta/nl2sql/solution_queries"
RESULTS_DIR = "/opt/pm883-1/dongkwang/ta/nl2sql/autograder_results"
NL_QUERIES_VAR_NAME = "nlqueries"
TEST_DATABASE_NAME = "testnl2sql"

def execute_sql(engine, sql_query: str) -> tuple[str, str | None]:
    """Executes a SQL query and returns the result as a formatted string and a potential error."""
    if not sql_query or sql_query == "N/A":
        return "(No query to execute)", None
    try:
        with engine.connect() as connection:
            result = connection.execute(text(sql_query))
            rows = result.fetchall()
            if not rows:
                return "(No rows returned)", None
            
            headers = result.keys()
            # Format into a simple table
            header_str = " | ".join(map(str, headers))
            separator = "-" * len(header_str)
            row_strs = [" | ".join(map(str, row)) for row in rows]
            
            return f"\n{header_str}\n{separator}\n" + "\n".join(row_strs), None
    except Exception as e:
        return f"ERROR: {e}", str(e)

def main():
    """Main function to run the autograder."""
    # 1. Setup
    print("--- Starting Autograder ---")
    load_dotenv()

    if not os.getenv("GOOGLE_API_KEY") or not os.getenv("DATABASE_URL"):
        raise ValueError(".env file must contain GOOGLE_API_KEY and DATABASE_URL")

    # Force connection to the test database for grading
    base_db_url = os.getenv("DATABASE_URL")
    db_url_obj = make_url(base_db_url)
    test_db_url = db_url_obj.set(database=TEST_DATABASE_NAME)
    
    try:
        engine = create_engine(test_db_url)
        with engine.connect() as conn:
            # Check if DB is connectable
            pass
        print(f"Successfully connected to test database: {TEST_DATABASE_NAME}")
    except Exception as e:
        print(f"FATAL: Could not connect to test database '{TEST_DATABASE_NAME}'. Error: {e}", file=sys.stderr)
        sys.exit(1)

    llm = ChatGoogleGenerativeAI(model="gemini-pro", temperature=0)
    db_for_agent = SQLDatabase(engine=engine)
    agent_executor = create_sql_agent(
        llm=llm,
        db=db_for_agent,
        agent_type="zero-shot-react-description",
        verbose=False, # Set to True for debugging
        handle_parsing_errors=True,
        return_intermediate_steps=True
    )

    Path(RESULTS_DIR).mkdir(exist_ok=True)

    # 2. Find and process submissions
    submission_dirs = glob.glob(f"{SUBMISSIONS_DIR}/submission_*/")
    if not submission_dirs:
        print(f"Warning: No submission directories found in {SUBMISSIONS_DIR}")
        return

    print(f"Found {len(submission_dirs)} submissions to process.")

    for sub_dir in sorted(submission_dirs):
        submission_id = Path(sub_dir).name.split('_')[-1]
        print(f"\nProcessing submission: {submission_id}")

        # Create output directory for the submission
        output_dir = Path(RESULTS_DIR) / submission_id
        output_dir.mkdir(exist_ok=True)

        # Find the query file
        query_files = glob.glob(f"{sub_dir}/*queries*.py")
        if not query_files:
            print(f"  - ERROR: No '*queries.py' file found in {sub_dir}. Skipping.")
            continue
        
        query_file_path = query_files[0]

        # Load the queries list from the file
        try:
            spec = importlib.util.spec_from_file_location("nl_queries_module", query_file_path)
            queries_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(queries_module)
            nl_queries = getattr(queries_module, NL_QUERIES_VAR_NAME)
        except (AttributeError, FileNotFoundError, SyntaxError) as e:
            print(f"  - ERROR: Could not load '{NL_QUERIES_VAR_NAME}' from {query_file_path}. Error: {e}. Skipping.")
            continue

        # 3. Process each query
        for i, nl_query in enumerate(nl_queries, start=1):
            print(f"  - Grading query {i}...", end="")
            output_content = [f"--- Autograder Result for Submission {submission_id}, Query {i} ---\n"]
            output_content.append(f"[Natural Language Query]:\n{nl_query}\n")

            # A. Generate SQL from NL
            generated_sql = "N/A"
            try:
                response = agent_executor.invoke({"input": nl_query})
                if response.get("intermediate_steps"):
                    for step in response["intermediate_steps"]:
                        if step[0].tool == 'sql_db_query':
                            generated_sql = step[0].tool_input
                            break
            except Exception as e:
                generated_sql = f"Agent execution failed: {e}"
            
            output_content.append(f"[Generated SQL]:\n{generated_sql}\n")

            # B. Execute Generated SQL
            gen_result, _ = execute_sql(engine, generated_sql)
            output_content.append(f"[Result of Generated SQL]:{gen_result}\n")

            # C. Read and Execute Golden SQL
            golden_query_path = Path(SOLUTION_QUERIES_DIR) / f"query-{i}.sql"
            golden_sql = "N/A"
            golden_result = "(Golden query file not found)"
            if golden_query_path.exists():
                golden_sql = golden_query_path.read_text()
                golden_result, _ = execute_sql(engine, golden_sql)
            
            output_content.append(f"--- Golden Solution ---\n")
            output_content.append(f"[Golden SQL from {golden_query_path.name}]:\n{golden_sql}\n")
            output_content.append(f"[Result of Golden SQL]:{golden_result}\n")

            # D. Write output file
            output_file_path = output_dir / f"result-{i}.txt"
            output_file_path.write_text("\n".join(output_content))
            print("Done.")

    print("\n--- Autograder Finished ---")

if __name__ == "__main__":
    main()

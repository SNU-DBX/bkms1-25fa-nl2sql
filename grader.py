import os
import sys
import glob
import importlib.util
import ast
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

# --- Configuration ---
SUBMISSIONS_DIR = "/opt/pm883-1/dongkwang/ta/nl2sql/submissions"
SOLUTION_QUERIES_DIR = "/opt/pm883-1/dongkwang/ta/nl2sql/solution_queries"
RESULTS_DIR = "/opt/pm883-1/dongkwang/ta/nl2sql/grade_results"
TEST_DATABASE_NAME = "testnl2sql"

def execute_sql(engine, sql_query: str) -> tuple[str, str | None]:
    """Executes a SQL query and returns the result as a formatted string and a potential error."""
    if not sql_query or not sql_query.strip() or sql_query.strip() == "N/A":
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

def load_submitted_queries(file_path: Path) -> list[str] | None:
    """Loads submitted SQL queries from a file."""
    try:
        # First, try to evaluate the file content as a Python literal (e.g., a list of strings)
        content = file_path.read_text()
        queries = ast.literal_eval(content)
        if isinstance(queries, list) and all(isinstance(q, str) for q in queries):
            print(f"  - Successfully loaded queries using ast.literal_eval from {file_path.name}")
            return queries
    except (SyntaxError, ValueError):
        # If literal_eval fails, try importing as a module
        pass

    try:
        spec = importlib.util.spec_from_file_location("sql_queries_module", str(file_path))
        queries_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(queries_module)
        # Search for a list of strings in the imported module
        for var_name in dir(queries_module):
            if not var_name.startswith("__"):
                var = getattr(queries_module, var_name)
                if isinstance(var, list) and all(isinstance(item, str) for item in var):
                    print(f"  - Successfully loaded queries using importlib from variable '{var_name}' in {file_path.name}")
                    return var
    except Exception as e:
        print(f"  - ERROR: Failed to load queries via importlib from {file_path}. Error: {e}")

    return None


def main():
    """Main function to run the SQL grader."""
    # 1. Setup
    print("--- Starting SQL Grader ---")
    load_dotenv()

    if not os.getenv("DATABASE_URL"):
        raise ValueError(".env file must contain DATABASE_URL")

    base_db_url = os.getenv("DATABASE_URL")
    db_url_obj = make_url(base_db_url)
    test_db_url = db_url_obj.set(database=TEST_DATABASE_NAME)
    
    try:
        engine = create_engine(str(test_db_url))
        with engine.connect() as conn:
            pass
        print(f"Successfully connected to test database: {TEST_DATABASE_NAME}")
    except Exception as e:
        print(f"FATAL: Could not connect to test database '{TEST_DATABASE_NAME}'. Error: {e}", file=sys.stderr)
        sys.exit(1)

    Path(RESULTS_DIR).mkdir(exist_ok=True)

    # 2. Load solution queries
    solution_queries = {}
    solution_files = sorted(glob.glob(f"{SOLUTION_QUERIES_DIR}/query-*.sql"))
    for sol_file in solution_files:
        try:
            query_num = int(Path(sol_file).stem.split('-')[1])
            solution_queries[query_num] = Path(sol_file).read_text()
        except (ValueError, IndexError):
            print(f"Warning: Could not parse query number from solution file: {sol_file}")

    print(f"Loaded {len(solution_queries)} solution queries.")

    # 3. Find and process submissions
    submission_dirs = glob.glob(f"{SUBMISSIONS_DIR}/submission_*/")
    if not submission_dirs:
        print(f"Warning: No submission directories found in {SUBMISSIONS_DIR}")
        return

    print(f"Found {len(submission_dirs)} submissions to process.")

    for sub_dir in sorted(submission_dirs):
        submission_id = Path(sub_dir).name.split('_')[-1]
        print(f"\nProcessing submission: {submission_id}")

        output_dir = Path(RESULTS_DIR) / submission_id
        output_dir.mkdir(exist_ok=True)

        # Find a query file to grade
        query_file_path = None
        possible_files = ["sql_queries.py"]
        for filename in possible_files:
            if (Path(sub_dir) / filename).exists():
                query_file_path = Path(sub_dir) / filename
                break
        
        if not query_file_path:
            # If no specific file found, check for any *queries.py but prioritize sql
            all_query_files = glob.glob(f"{sub_dir}/*queries*.py")
            if all_query_files:
                sql_files = [f for f in all_query_files if 'sql' in f.lower()]
                if sql_files:
                    query_file_path = Path(sql_files[0])
                else:
                    query_file_path = Path(all_query_files[0]) # fallback to any other queries file
            
        if not query_file_path or not query_file_path.exists():
            print(f"  - INFO: No suitable query file found in {sub_dir}. Skipping.")
            continue
        
        print(f"  - Found query file: {query_file_path.name}")
        submitted_queries = load_submitted_queries(query_file_path)

        if not submitted_queries:
            print(f"  - ERROR: Could not load any queries from {query_file_path}. Skipping.")
            continue

        print(f"  - Loaded {len(submitted_queries)} submitted queries.")
        
        # 4. Process each query and print/save results
        for i, submitted_sql in enumerate(submitted_queries, start=1):
            print(f"  - Grading query {i}...")
            
            # Execute submitted query
            submitted_result, _ = execute_sql(engine, submitted_sql)
            
            # Get and execute solution query
            solution_sql = solution_queries.get(i, "N/A")
            solution_result, _ = execute_sql(engine, solution_sql)

            # Print to console for inspection
            print(f"\n--- Query {i} Results (Submission: {submission_id}) ---")
            print("--- Submitted Query Result ---")
            print(submitted_result)
            print("\n--- Solution Query Result ---")
            print(solution_result)
            print("--------------------------------------------------\n")

            # Save results to a file for the specific query
            output_content = [
                f"--- Autograder Result for Submission {submission_id}, Query {i} ---\n",
                f"[Submitted SQL from {query_file_path.name}]:\n{submitted_sql}\n",
                f"[Result of Submitted SQL]:{submitted_result}\n",
                "--- Golden Solution ---\n",
                f"[Golden SQL from query-{i}.sql]:\n{solution_sql}\n",
                f"[Result of Golden SQL]:{solution_result}\n"
            ]
            output_file_path = output_dir / f"result-{i}.txt"
            output_file_path.write_text("\n".join(output_content))
        
        print(f"  - Grading for submission {submission_id} complete. Results saved in {output_dir}")

    print("\n--- Grader Finished ---")

if __name__ == "__main__":
    main()

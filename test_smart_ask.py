import sys
import os
import asyncio

# Ensure core module is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.smart_analyze import SmartAnalyzer

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test", "20260102", "上轨下系100.xlsx")
QUERY = "请问其中年化收益大于5%的股票有多少？"

def main():
    print(f"Analyzing file: {FILE_PATH}")
    print(f"Query: {QUERY}")
    
    if not os.path.exists(FILE_PATH):
        print(f"Error: File not found at {FILE_PATH}")
        return

    if not DASHSCOPE_API_KEY:
        print("Error: DASHSCOPE_API_KEY env var is empty")
        return
    
    analyzer = SmartAnalyzer(DASHSCOPE_API_KEY)
    
    try:
        # Run analyze
        result = analyzer.analyze(FILE_PATH, QUERY)
        print("\n--- Result ---")
        if "error" in result:
            print(f"Error: {result['error']}")
        elif result.get("success") is False: # Check second implementation style just in case
            print(f"Error: {result.get('error')}")
        else:
            print(f"SQL: {result.get('sql')}")
            print(f"Answer: {result.get('answer')}")
            # print(f"Data Sample: {result.get('data')[:2]}")
    except Exception as e:
        print(f"Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

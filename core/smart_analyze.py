import sqlite3
import pandas as pd
import json
import urllib.request
import urllib.error
import re
import os
import csv
import tempfile
from typing import List, Dict, Any, Optional, Tuple

class SmartAnalyzer:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
        self.model = "qwen-plus"

    def analyze(self, file_path: str, query: str) -> Dict[str, Any]:
        """
        1. Load CSV/Excel into in-memory SQLite
        2. Get schema
        3. Ask LLM to generate SQL
        4. Execute SQL
        5. Ask LLM to explain result
        """
        table_name = "stock_data"

        p0 = str(file_path or "").strip()
        db_tmp_path: Optional[str] = None
        try:
            size = os.path.getsize(p0) if p0 and os.path.isfile(p0) else None
        except Exception:
            size = None

        use_disk_db = bool(size is not None and size >= 30 * 1024 * 1024)
        if use_disk_db:
            f = tempfile.NamedTemporaryFile(prefix="chhf_smart_", suffix=".sqlite", delete=False)
            db_tmp_path = f.name
            f.close()
            conn = sqlite3.connect(db_tmp_path)
        else:
            conn = sqlite3.connect(":memory:")
        try:
            try:
                conn.execute("PRAGMA journal_mode = OFF")
                conn.execute("PRAGMA synchronous = OFF")
                conn.execute("PRAGMA temp_store = MEMORY")
            except Exception:
                pass
            loaded = self._load_to_sqlite(conn, table_name, file_path)
            if loaded.get("error"):
                return loaded
            
            # Get schema info for LLM
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns_info = cursor.fetchall()
            schema_desc = ", ".join([f"{col[1]} ({col[2]})" for col in columns_info])
            
            # 3. Generate SQL
            sql_prompt = f"""
You are a data analyst. You have a table named '{table_name}' with columns: {schema_desc}.
The user asks: "{query}"
Please write a SQL query to answer this question.
Return ONLY the SQL query, no markdown, no explanation.
Ensure the SQL is compatible with SQLite.
"""
            sql_query = self._call_llm([
                {"role": "system", "content": "You are a SQL generator. Output only valid SQLite SQL."},
                {"role": "user", "content": sql_prompt}
            ]).strip()
            
            # Clean up SQL (remove markdown code blocks if any)
            sql_query = re.sub(r'```sql\s*', '', sql_query, flags=re.IGNORECASE)
            sql_query = re.sub(r'```\s*', '', sql_query).strip()
            
            # 4. Execute SQL
            try:
                result_df = pd.read_sql_query(sql_query, conn)
                result_data = result_df.to_dict(orient='records')
                # Limit result size
                if len(result_data) > 100:
                    result_data = result_data[:100]
            except Exception as e:
                return {
                    "sql": sql_query,
                    "error": f"SQL Execution failed: {str(e)}",
                    "data": []
                }

            # 5. Explain Result
            result_str = str(result_data[:5]) # Provide sample
            if len(result_data) > 5:
                result_str += f" ... (total {len(result_data)} rows)"
            
            explain_prompt = f"""
The user asked: "{query}"
The SQL query was: "{sql_query}"
The execution result is: {result_str}

Please briefly answer the user's question based on this result in natural language (Chinese).
"""
            explanation = self._call_llm([
                {"role": "user", "content": explain_prompt}
            ])

            return {
                "sql": sql_query,
                "data": result_data,
                "answer": explanation
            }

        finally:
            conn.close()
            if db_tmp_path:
                try:
                    os.remove(db_tmp_path)
                except Exception:
                    pass

    def _load_to_sqlite(self, conn: sqlite3.Connection, table_name: str, file_path: str) -> Dict[str, Any]:
        p = str(file_path or "").strip()
        if not p:
            return {"error": "文件路径为空"}
        if not os.path.exists(p):
            return {"error": f"文件不存在: {p}"}
        if not os.path.isfile(p):
            return {"error": f"不是文件: {p}"}

        ext = os.path.splitext(p)[1].lower()
        if ext not in {".csv", ".xls", ".xlsx"}:
            return {"error": "不支持的文件格式，仅支持 .csv / .xls / .xlsx"}

        try:
            size = os.path.getsize(p)
        except Exception:
            size = None

        try:
            if ext == ".csv":
                enc, sep = self._detect_csv_format(p)
                big = (size is not None and size >= 20 * 1024 * 1024)
                if not big:
                    chunksize = None
                else:
                    chunksize = 50_000 if (size is not None and size >= 100 * 1024 * 1024) else 100_000
                self._csv_to_sqlite(conn, table_name, p, enc, sep, chunksize=chunksize)
            else:
                if size is not None and size >= 30 * 1024 * 1024:
                    return {
                        "error": "Excel 文件过大，建议转换为 CSV 后再分析",
                        "detail": f"文件大小约 {round(size / 1024 / 1024, 2)} MB",
                        "hint": "CSV 建议使用 UTF-8/UTF-8-SIG 或 GBK 编码，分隔符支持逗号/制表符/分号",
                    }
                df = pd.read_excel(p)
                if df is None or df.shape[1] == 0:
                    return {"error": "Excel 文件为空或无可读列"}
                df.columns = [self._sanitize_col(c) for c in df.columns]
                df.to_sql(table_name, conn, index=False, if_exists="replace")
        except Exception as e:
            msg = str(e)
            extra_hint = ""
            lower = msg.lower()
            if "openpyxl" in lower or "xlrd" in lower:
                extra_hint = "Excel 解析依赖未安装（openpyxl/xlrd），建议安装依赖或另存为 CSV 后重试"
            return {
                "error": "文件加载失败",
                "detail": str(e),
                "hint": ("；".join([x for x in [
                    "CSV 建议使用 UTF-8/UTF-8-SIG 或 GBK 编码，分隔符支持逗号/制表符/分号",
                    extra_hint or None
                ] if x]) or "")
            }

        return {"ok": True}

    def _detect_csv_format(self, file_path: str) -> Tuple[str, str]:
        sample = b""
        with open(file_path, "rb") as f:
            sample = f.read(64 * 1024)

        enc_candidates = ["utf-8-sig", "utf-8", "utf-16", "utf-16le", "utf-16be", "gbk", "gb2312", "cp936", "latin1"]
        text = None
        used_enc = "utf-8-sig"
        for enc in enc_candidates:
            try:
                text = sample.decode(enc, errors="strict")
                used_enc = enc
                break
            except Exception:
                continue
        if text is None:
            text = sample.decode("utf-8", errors="replace")
            used_enc = "utf-8"

        sep = ","
        try:
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(text, delimiters=[",", "\t", ";", "|"])
            sep = getattr(dialect, "delimiter", ",") or ","
        except Exception:
            line = ""
            for ln in (text or "").splitlines():
                if ln and ln.strip():
                    line = ln
                    break
            if line:
                cands = [",", "\t", ";", "|"]
                best = ","
                best_n = -1
                for c in cands:
                    n = line.count(c)
                    if n > best_n:
                        best_n = n
                        best = c
                sep = best or ","
            else:
                sep = ","

        return used_enc, sep

    def _csv_to_sqlite(
        self,
        conn: sqlite3.Connection,
        table_name: str,
        file_path: str,
        encoding: str,
        sep: str,
        chunksize: Optional[int] = None,
    ) -> None:
        if not chunksize:
            df = pd.read_csv(file_path, encoding=encoding, sep=sep, low_memory=True)
            if df is None or df.shape[1] == 0:
                raise Exception("CSV 文件为空或无可读列")
            df.columns = [self._sanitize_col(c) for c in df.columns]
            df.to_sql(table_name, conn, index=False, if_exists="replace")
            return

        it = pd.read_csv(
            file_path,
            encoding=encoding,
            sep=sep,
            low_memory=True,
            chunksize=int(chunksize),
            iterator=True,
        )
        cols0: Optional[list[str]] = None
        first = True
        for chunk in it:
            if chunk is None or chunk.shape[1] == 0:
                continue
            chunk.columns = [self._sanitize_col(c) for c in chunk.columns]
            if cols0 is None:
                cols0 = list(chunk.columns)
            else:
                if list(chunk.columns) != cols0:
                    chunk = chunk.reindex(columns=cols0)

            chunk.to_sql(
                table_name,
                conn,
                index=False,
                if_exists="replace" if first else "append",
            )
            first = False

        if cols0 is None:
            raise Exception("CSV 文件为空或无可读列")

    def _sanitize_col(self, col: str) -> str:
        # Replace non-alphanumeric with underscore, keep simple
        s = str(col).strip()
        s = re.sub(r'[^a-zA-Z0-9_\u4e00-\u9fa5]', '_', s)
        if not s: return "col"
        return s

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "stream": False
        }
        
        try:
            req = urllib.request.Request(
                self.base_url,
                data=json.dumps(payload).encode('utf-8'),
                headers=headers,
                method="POST"
            )
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    res_body = response.read()
                    res_json = json.loads(res_body)
                    return res_json['choices'][0]['message']['content']
                else:
                    raise Exception(f"API Error: {response.status}")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8')
            raise Exception(f"HTTP Error {e.code}: {err_body}")
        except Exception as e:
            raise Exception(f"LLM Call Failed: {str(e)}")

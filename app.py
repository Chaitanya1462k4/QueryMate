import streamlit as st
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
try:
    from langchain_community.utilities import SQLDatabase
except ImportError:
    from langchain_classic.utilities import SQLDatabase
from langchain_huggingface import HuggingFaceEndpoint, ChatHuggingFace
from langchain_core.runnables import RunnablePassthrough
from dotenv import load_dotenv
import tempfile
import os
import time

# ── Load environment ──
load_dotenv()
# Support Streamlit Cloud Secrets
if "HF_TOKEN" not in os.environ and hasattr(st, "secrets") and "HF_TOKEN" in st.secrets:
    os.environ["HF_TOKEN"] = st.secrets["HF_TOKEN"]

# ── Page config ──
st.set_page_config(
    page_title="SQL Query Assistant",
    page_icon="🗃️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
    }
    .main-header h1 { margin: 0; font-size: 1.8rem; font-weight: 700; }
    .main-header p { margin: 0.3rem 0 0 0; opacity: 0.85; font-size: 0.95rem; }

    .step-label {
        font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
        letter-spacing: 0.05em; color: #6b7280; margin-bottom: 0.25rem;
    }
    .table-chip {
        display: inline-block; background: #ede9fe; color: #6d28d9;
        padding: 0.25rem 0.65rem; border-radius: 20px;
        font-size: 0.8rem; font-weight: 500; margin: 0.15rem;
    }
    .db-status {
        padding: 0.6rem 0.8rem; border-radius: 8px; font-size: 0.85rem;
        margin-top: 0.5rem;
    }
    .db-connected {
        background: #f0fdf4; border: 1px solid #86efac; color: #166534;
    }
    .db-disconnected {
        background: #fef2f2; border: 1px solid #fca5a5; color: #991b1b;
    }
    .stButton > button { text-align: left; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)


# ── Model setup (cached) ──
@st.cache_resource
def init_model():
    llm = HuggingFaceEndpoint(
        repo_id="openai/gpt-oss-120b",
        task="text-generation",
    )
    return ChatHuggingFace(llm=llm)


# ── Database helpers ──
@st.cache_resource
def connect_db_from_uri(uri: str):
    """Connect to a database using a SQLAlchemy URI."""
    return SQLDatabase.from_uri(uri, sample_rows_in_table_info=0)


def connect_db_from_upload(uploaded_file):
    """Save uploaded .db file to a temp location and connect."""
    # Create a persistent temp directory per session
    if "db_temp_dir" not in st.session_state:
        st.session_state.db_temp_dir = tempfile.mkdtemp()

    db_path = os.path.join(st.session_state.db_temp_dir, uploaded_file.name)
    with open(db_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return SQLDatabase.from_uri(f"sqlite:///{db_path}", sample_rows_in_table_info=0)


def get_schema(db: SQLDatabase) -> str:
    return db.get_table_info()


def clean_sql(query: str) -> str:
    """Clean markdown code fences, backticks, and extra keywords from LLM output."""
    cleaned = query.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    if cleaned.lower().startswith("sql"):
        cleaned = cleaned[3:].strip()
    return cleaned


def run_query(db: SQLDatabase, query: str) -> str:
    """Execute SQL query safely, splitting multi-statement queries to prevent sqlite3 ProgrammingError."""
    cleaned = clean_sql(query)
    # Split statements by semicolon while ignoring empty ones
    statements = [stmt.strip() for stmt in cleaned.split(";") if stmt.strip()]

    if not statements:
        return "No valid SQL query found."

    # If single statement, execute directly
    if len(statements) == 1:
        return db.run(statements[0])

    # If multiple statements, execute each independently and combine results
    combined_results = []
    for i, stmt in enumerate(statements, 1):
        try:
            res = db.run(stmt)
            combined_results.append(f"Result {i} ({stmt[:40]}...):\n{res}")
        except Exception as e:
            combined_results.append(f"Result {i} Error: {e}")
    return "\n\n".join(combined_results)


# ── Chain builders ──
def build_sql_chain(model, db):
    template = """Based on the table schema below, write a SQL query that would answer the user's question:
    {schema}

    Question: {question}
    SQL Query:"""

    prompt = ChatPromptTemplate.from_messages([
        ("system",
         "You are an expert SQL assistant. Given an input question and schema, write a single valid SQL query.\n"
         "CRITICAL RULES:\n"
         "1. Return ONLY the raw SQL query with no markdown formatting, no backticks (```), and no explanation.\n"
         "2. Return only ONE single SQL statement. Never generate multiple queries separated by semicolons.\n"
         "3. If querying data across tables, use JOIN or UNION operations inside a single query.\n"
         "4. Only generate read-only SELECT queries."),
        ("human", template)
    ])

    return (
        RunnablePassthrough.assign(schema=lambda x: get_schema(db))
        | prompt
        | model
        | StrOutputParser()
        | clean_sql
    )


# ── Initialize model ──
model = init_model()

# ──────────────────────────────────────────────
# SIDEBAR
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🗄️ Database Connection")

    # ── Connection method selector ──
    db_method = st.radio(
        "How would you like to connect?",
        ["📁 Upload a SQLite file", "🔗 Enter a connection URI"],
        index=0,
        horizontal=True,
    )

    db = None  # will be set below

    if db_method == "📁 Upload a SQLite file":
        uploaded_file = st.file_uploader(
            "Upload a `.db` / `.sqlite` / `.sqlite3` file",
            type=["db", "sqlite", "sqlite3"],
            help="Drag and drop your SQLite database file here.",
        )
        if uploaded_file is not None:
            # Only reconnect if the file changed
            file_key = f"{uploaded_file.name}_{uploaded_file.size}"
            if st.session_state.get("db_file_key") != file_key:
                try:
                    db = connect_db_from_upload(uploaded_file)
                    st.session_state.db = db
                    st.session_state.db_file_key = file_key
                    st.session_state.db_name = uploaded_file.name
                    st.session_state.messages = []  # reset chat for new DB
                except Exception as e:
                    st.error(f"❌ Failed to connect: {e}")
            else:
                db = st.session_state.get("db")
        else:
            # Check if there's a previously loaded DB in session
            db = st.session_state.get("db")

    else:  # Connection URI
        uri = st.text_input(
            "Database URI",
            placeholder="sqlite:///mydb.db  or  postgresql://user:pass@host/db",
            help="Any SQLAlchemy-compatible connection string.",
        )
        if uri:
            uri_key = uri.strip()
            if st.session_state.get("db_uri_key") != uri_key:
                try:
                    with st.spinner("Connecting..."):
                        db = connect_db_from_uri(uri_key)
                    st.session_state.db = db
                    st.session_state.db_uri_key = uri_key
                    st.session_state.db_name = uri_key.split("/")[-1] or uri_key
                    st.session_state.messages = []  # reset chat for new DB
                except Exception as e:
                    st.error(f"❌ Failed to connect: {e}")
            else:
                db = st.session_state.get("db")
        else:
            db = st.session_state.get("db")

    st.markdown("---")

    # ── Connection status ──
    if db is not None:
        db_name = st.session_state.get("db_name", "Database")
        st.markdown(
            f'<div class="db-status db-connected">✅ Connected to <b>{db_name}</b></div>',
            unsafe_allow_html=True,
        )

        # Show tables
        st.markdown("---")
        st.markdown("### 📋 Tables")
        table_names = db.get_usable_table_names()
        chips_html = "".join(f'<span class="table-chip">📋 {t}</span>' for t in table_names)
        st.markdown(f'<div>{chips_html}</div>', unsafe_allow_html=True)

        st.markdown("")

        # Schema viewer
        with st.expander("📐 View Full Schema", expanded=False):
            st.code(get_schema(db), language="sql")

        # Clear chat button
        if st.button("🗑️ Clear Chat History", use_container_width=True):
            st.session_state.messages = []
            st.rerun()
    else:
        st.markdown(
            '<div class="db-status db-disconnected">⚠️ No database connected</div>',
            unsafe_allow_html=True,
        )
        st.markdown("")
        st.info("👆 Upload a SQLite file or enter a connection URI to get started.")

    st.markdown("---")

    # How it works
    st.markdown("## ⚙️ How It Works")
    st.markdown("""
    1. **Upload / connect** your database
    2. **Ask** a question in plain English
    3. **LLM** reads the schema & generates SQL
    4. **SQL runs** against your database
    5. **LLM** converts results into a friendly answer
    """)

    st.markdown("---")
    st.caption("Powered by LangChain · HuggingFace · Streamlit")


# ──────────────────────────────────────────────
# MAIN AREA
# ──────────────────────────────────────────────
db_display_name = st.session_state.get("db_name", "your database")
st.markdown(f"""
<div class="main-header">
    <h1>🗃️ SQL Query Assistant</h1>
    <p>Ask questions about <b>{db_display_name}</b> in plain English</p>
</div>
""", unsafe_allow_html=True)

# ── Guard: no DB connected ──
if db is None:
    st.markdown("---")
    st.warning("👈 **Connect a database** from the sidebar to start querying.")
    st.markdown("""
    **Supported databases:**
    - 📁 **Upload**: Drag & drop any `.db`, `.sqlite`, or `.sqlite3` file
    - 🔗 **URI**: Enter any SQLAlchemy connection string, e.g.
      - `sqlite:///path/to/mydb.db`
      - `postgresql://user:pass@localhost:5432/mydb`
      - `mysql+pymysql://user:pass@host/db`
    """)
    st.stop()

# ── Chat history ──
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display past messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"], avatar="🧑‍💻" if msg["role"] == "user" else "🤖"):
        st.markdown(msg["content"], unsafe_allow_html=True)

# ── Example questions (only shown when chat is empty) ──
if not st.session_state.messages:
    st.markdown("#### 💡 Try asking something like:")
    examples = [
        "List the names of all tables in this database",
        "What are the top 5 records by highest amount or value?",
        "Show 5 sample records from the main table",
        "How many total records exist across the primary table?",
    ]
    cols = st.columns(2)
    for i, example in enumerate(examples):
        with cols[i % 2]:
            if st.button(f"📝 {example}", key=f"ex_{i}", use_container_width=True):
                st.session_state["prefill_question"] = example
                st.rerun()

# ── Chat input ──
prefill = st.session_state.pop("prefill_question", None)
user_question = st.chat_input("Ask a question about the database...") or prefill

if user_question:
    # Add user message
    st.session_state.messages.append({"role": "user", "content": user_question})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(user_question)

    # Generate response
    with st.chat_message("assistant", avatar="🤖"):
        status = st.status("🔄 Processing your question...", expanded=True)

        try:
            with status:
                # Step 1 — Generate SQL
                st.markdown('<div class="step-label">Step 1 — Generating SQL Query</div>', unsafe_allow_html=True)
                step1_placeholder = st.empty()
                step1_placeholder.markdown("⏳ Thinking...")

                start = time.time()
                sql_chain = build_sql_chain(model, db)
                sql_query = sql_chain.invoke({"question": user_question})
                t1 = time.time() - start

                step1_placeholder.empty()
                st.code(sql_query.strip(), language="sql")
                st.caption(f"✅ Generated in {t1:.1f}s")

                # Step 2 — Execute SQL
                st.markdown('<div class="step-label">Step 2 — Executing Query</div>', unsafe_allow_html=True)
                step2_placeholder = st.empty()
                step2_placeholder.markdown("⏳ Running against database...")

                start = time.time()
                raw_response = run_query(db, sql_query)
                t2 = time.time() - start

                step2_placeholder.empty()
                st.code(raw_response, language="text")
                st.caption(f"✅ Executed in {t2:.1f}s")

                # Step 3 — Natural language answer
                st.markdown('<div class="step-label">Step 3 — Generating Answer</div>', unsafe_allow_html=True)
                step3_placeholder = st.empty()
                step3_placeholder.markdown("⏳ Composing response...")

                template = """Based on the table schema below, question, sql query, and sql response, write a natural language response:
    {schema}

    Question: {question}
    SQL Query: {query}
    SQL Response: {response}"""

                prompt = ChatPromptTemplate.from_messages([
                    ("system",
                     "Given an input question and SQL response, convert it to a natural language answer. No pre-amble."),
                    ("human", template)
                ])

                start = time.time()
                answer_chain = prompt | model | StrOutputParser()
                answer = answer_chain.invoke({
                    "schema": get_schema(db),
                    "question": user_question,
                    "query": sql_query,
                    "response": raw_response,
                })
                t3 = time.time() - start

                step3_placeholder.empty()
                st.caption(f"✅ Answered in {t3:.1f}s")

            status.update(label=f"✅ Done in {t1 + t2 + t3:.1f}s", state="complete", expanded=False)

            # Final answer
            st.markdown("---")
            st.markdown(answer)

            # Save to chat history
            history_content = f"""**Answer:** {answer}

<details>
<summary>🔍 View pipeline details</summary>

**SQL Query:**
```sql
{sql_query.strip()}
```

**Raw Result:**
```
{raw_response}
```
</details>"""
            st.session_state.messages.append({"role": "assistant", "content": history_content})

        except Exception as e:
            status.update(label="❌ Error occurred", state="error", expanded=True)
            with status:
                st.error(f"**Error:** {str(e)}")
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"❌ Sorry, an error occurred: `{str(e)}`"
            })

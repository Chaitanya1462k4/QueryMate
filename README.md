# 🗃️ QueryMate — Natural Language to SQL Assistant

🚀 **Live Demo:** [Try QUERYMATE](https://querymateio.streamlit.app/)

**QueryMate** is an interactive LLM-powered assistant that lets you query relational databases using natural English language. Ask questions, view the generated SQL queries in real time, inspect the execution results, and receive friendly natural language summaries — all packaged within a clean Streamlit interface.

---

## 🌟 Key Features

- **🗣️ Natural Language to SQL (NL2SQL):** Ask questions in plain English without writing a single line of SQL.
- **📁 Dynamic Database Connection:**
  - **Upload SQLite DB:** Drag & drop any `.db`, `.sqlite`, or `.sqlite3` file directly via the UI.
  - **Connection URI:** Connect to any SQLAlchemy-compatible database (e.g., SQLite, PostgreSQL, MySQL) using connection strings.
- **🔍 Transparent 3-Step Pipeline:**
  1. **SQL Generation:** Extracts database schema and uses Hugging Face models to draft precise SQL.
  2. **Query Execution:** Runs the generated query against your database and shows raw results.
  3. **Synthesis & Answer:** Translates raw database rows into a clear, concise natural language answer.
- **📊 Schema Explorer & Table Inspector:** Browse database tables, columns, and full schemas dynamically in the sidebar.
- **💬 Interactive Chat History:** Retains chat context with collapsible execution details for full transparency.

---

## 🏗️ Architecture

```
User Prompt (Natural Language)
              │
              ▼
   ┌──────────────────────┐
   │    Language Model    │ ◄─── Database Schema (Table structures, keys)
   └──────────┬───────────┘
              │ Generates
              ▼
       ┌──────────────┐
       │  SQL Query   │ ───► Executes against Database
       └──────┬───────┘
              │ Query Results
              ▼
   ┌──────────────────────┐
   │    Language Model    │
   └──────────┬───────────┘
              │ Synthesizes
              ▼
    Friendly English Answer
```

---

## 🚀 Quickstart

### 1. Prerequisites

- Python 3.10+
- Hugging Face Account & API Token ([Get one here](https://huggingface.co/settings/tokens))

### 2. Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd QueryMate
   ```

2. **Create and activate a virtual environment:**
   ```bash
   # Windows (CMD / PowerShell)
   python -m venv .venv
   .venv\Scripts\activate

   # macOS / Linux
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### 3. Configure Environment Variables

Create a `.env` file in the root directory:

```env
HF_TOKEN=your_huggingface_api_token_here
```

### 4. Run the Application

```bash
streamlit run app.py
```

The app will open automatically at `http://localhost:8501`.

---

## 📂 Project Structure

```
QueryMate/
├── app.py           # Streamlit application with LangChain pipeline
├── Chinook.db       # Sample SQLite database (Music store)
├── .env.example     # Template for environment variables
├── .gitignore       # Git ignore rules
└── README.md        # Project documentation
```

---

## 💡 Example Queries

If you're using the bundled sample **Chinook.db**:
- *"How many tracks are in the database?"*
- *"List the top 5 artists with the most albums."*
- *"What is the total revenue from all invoices?"*
- *"Show me all genres available in the store."*
- *"Which employee has handled the most customers?"*

---

## 🛡️ License

This project is licensed under the MIT License.

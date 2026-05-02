# ── Windows / Streamlit signal fix ───────────────────────────────────────────
import signal as _signal_module
import threading as _threading_module

_real_signal_fn = _signal_module.signal

def _safe_signal(sig, handler):
    if _threading_module.current_thread() is _threading_module.main_thread():
        return _real_signal_fn(sig, handler)

_signal_module.signal = _safe_signal

import os
os.environ["CREWAI_DISABLE_TELEMETRY"] = "true"
os.environ["OTEL_SDK_DISABLED"] = "true"
os.environ.setdefault("OPENAI_API_KEY", "dummy-not-used")

import streamlit as st
import shutil
import tempfile
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import BaseTool
from pydantic import Field
import pdfplumber
from sentence_transformers import SentenceTransformer
import chromadb

load_dotenv()

st.set_page_config(page_title="Project X - Financial Auditor", layout="wide")

st.markdown(
    """
    <style>
      @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
      html, body, [class*='css'] { font-family: 'IBM Plex Sans', sans-serif; }
      h1, h2, h3 { font-family: 'IBM Plex Mono', monospace; }
      .stApp { background: #0d1117; color: #e6edf3; }
      .block-container { padding: 2rem 3rem; }
      .result-box {
        background: #161b22;
        border: 1px solid #30363d;
        border-left: 4px solid #58a6ff;
        border-radius: 6px;
        padding: 1.5rem;
        margin-top: 1rem;
        font-size: 0.92rem;
        line-height: 1.7;
      }
      .agent-header {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 0.75rem;
        color: #58a6ff;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 0.4rem;
        margin-top: 1.5rem;
      }
      .stButton > button {
        background: #238636; color: #fff; border: none;
        border-radius: 6px; font-family: 'IBM Plex Mono', monospace;
        font-size: 0.85rem; padding: 0.6rem 1.5rem; transition: background 0.2s;
      }
      .stButton > button:hover { background: #2ea043; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Shield Project X: Autonomous Financial Auditor")
st.caption("Powered by CrewAI · Groq Llama 3 · HuggingFace Embeddings")

groq_api_key = os.getenv("GROQ_API_KEY")
if not groq_api_key:
    st.error("GROQ_API_KEY not found. Add GROQ_API_KEY=your_key to your .env file.")
    st.stop()

llm = LLM(model="groq/llama-3.3-70b-versatile", api_key=groq_api_key, temperature=0)


class PDFQueryTool(BaseTool):
    name: str = "search_financial_pdf"
    description: str = (
        "Search the uploaded financial PDF for specific information. "
        "Input a plain-English question or keyword, e.g. total revenue 2023."
    )
    pdf_path: str = Field(..., description="Path to the PDF file")

    def _run(self, query: str) -> str:
        chunks = []
        with pdfplumber.open(self.pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                words = text.split()
                for i in range(0, max(1, len(words) - 30), 40):
                    chunk = " ".join(words[i:i+50])
                    if chunk.strip():
                        chunks.append(chunk)

        if not chunks:
            return "No readable text found in the PDF."

        embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        chunk_embeddings = embedder.encode(chunks, show_progress_bar=False).tolist()

        client = chromadb.Client()
        col_name = "pdf_chunks"
        try:
            client.delete_collection(col_name)
        except Exception:
            pass
        collection = client.create_collection(col_name)
        collection.add(
            documents=chunks,
            embeddings=chunk_embeddings,
            ids=[f"chunk_{i}" for i in range(len(chunks))]
        )

        query_embedding = embedder.encode([query], show_progress_bar=False).tolist()
        results = collection.query(query_embeddings=query_embedding, n_results=min(5, len(chunks)))
        top_chunks = results["documents"][0] if results["documents"] else []

        if not top_chunks:
            return "No relevant content found for that query."

        return "\n\n---\n\n".join(top_chunks)


uploaded_file = st.file_uploader("Upload Financial Report (PDF)", type="pdf")

if uploaded_file:
    tmp_dir = tempfile.gettempdir()
    pdf_path = os.path.join(tmp_dir, "audit_report.pdf")
    vector_store_path = os.path.join(tmp_dir, "audit_vector_store")

    with open(pdf_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    st.success(f"Uploaded: {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")

    if st.button("Run Audit"):
        if os.path.exists(vector_store_path):
            shutil.rmtree(vector_store_path)

        with st.spinner("Agents are analysing the document... this may take a minute."):
            try:
                pdf_tool = PDFQueryTool(pdf_path=pdf_path)

                researcher = Agent(
                    role="Financial Researcher",
                    goal=(
                        "Extract key financial metrics from the uploaded PDF: "
                        "revenue, net income, EBITDA, total debt, cash flow, and YoY changes."
                    ),
                    backstory=(
                        "A forensic accountant with 15 years of experience dissecting "
                        "corporate filings. Known for precision and exhaustive extraction."
                    ),
                    tools=[pdf_tool],
                    llm=llm,
                    verbose=True,
                    allow_delegation=False,
                )

                compliance = Agent(
                    role="Compliance & Risk Officer",
                    goal=(
                        "Using the researcher extracted metrics, identify financial risks, "
                        "flag anomalies, check regulatory red flags, and assign a risk rating."
                    ),
                    backstory=(
                        "A seasoned Big-4 auditor specialising in SOX compliance, IFRS, "
                        "and fraud detection. Provides clear, actionable risk reports."
                    ),
                    llm=llm,
                    verbose=True,
                    allow_delegation=False,
                )

                t1 = Task(
                    description=(
                        "Search the uploaded financial PDF and extract ALL key metrics: "
                        "revenue, net income, EBITDA, total assets, total liabilities, debt, "
                        "operating cash flow, and any year-over-year percentage changes. "
                        "Present your findings as a clean, structured markdown table."
                    ),
                    agent=researcher,
                    expected_output=(
                        "A markdown table with columns: Metric | Value | Period | YoY Change. "
                        "Include a short paragraph noting any data gaps or caveats."
                    ),
                )

                t2 = Task(
                    description=(
                        "Using the financial metrics from Task 1, perform a thorough risk analysis. "
                        "Identify: (1) liquidity risks, (2) solvency concerns, "
                        "(3) revenue quality issues, (4) anomalies or red flags. "
                        "Assign an overall risk rating: LOW / MEDIUM / HIGH / CRITICAL."
                    ),
                    agent=compliance,
                    expected_output=(
                        "A structured risk report with: executive summary, numbered risk findings "
                        "(each with severity label), and a final overall risk rating with justification."
                    ),
                    context=[t1],
                )

                crew = Crew(
                    agents=[researcher, compliance],
                    tasks=[t1, t2],
                    process=Process.sequential,
                    verbose=True,
                )

                result = crew.kickoff()

                st.divider()
                st.subheader("Audit Results")

                if hasattr(result, "tasks_output") and result.tasks_output:
                    labels = ["Financial Metrics Extraction", "Risk Analysis Report"]
                    for i, task_out in enumerate(result.tasks_output):
                        label = labels[i] if i < len(labels) else f"Task {i+1}"
                        st.markdown(
                            f'<div class="agent-header">Agent Output: {label}</div>',
                            unsafe_allow_html=True,
                        )
                        st.markdown(task_out.raw)
                        st.write()
                else:
                    raw_text = result.raw if hasattr(result, "raw") else str(result)
                    st.markdown(raw_text)

            except Exception as e:
                st.error(f"Audit failed: {e}")
                st.exception(e)
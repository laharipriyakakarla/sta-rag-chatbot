# STA Timing Analysis Chatbot

A **Retrieval-Augmented Generation (RAG)** chatbot that answers natural language questions about Static Timing Analysis (STA) reports from an **ibex RISC-V core** implemented on the **ASAP7 7nm PDK** using OpenROAD.

![Python](https://img.shields.io/badge/Python-3.12-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.57-red)
![ChromaDB](https://img.shields.io/badge/ChromaDB-vector--store-green)
![Claude](https://img.shields.io/badge/Claude-Anthropic-orange)

---

## Demo

Ask questions like:
- *"Which path has the worst setup slack and why?"*
- *"Are there any hold violations in the design?"*
- *"How does the worst slack change from resizer to finish stage?"*
- *"Show me violated paths in the core_clock group"*

The chatbot retrieves the most relevant timing paths from a vector database and uses Claude to generate expert STA analysis grounded in your actual report data.

---

## Architecture

```
OpenROAD Timing Reports (.rpt)
        │
        ▼
   chunker.py          ← Parses paths into structured objects
        │               (startpoint, endpoint, slack, path group, stage)
        ▼
   embedder.py         ← Embeds paths using sentence-transformers
        │               → Stores in ChromaDB (local vector store)
        ▼
 rag_pipeline.py       ← Retrieves top-k relevant paths per query
        │               → Sends context + question to Claude API
        ▼
    app.py             ← Streamlit chat UI
```

---

## Design Under Analysis

| Parameter | Value |
|-----------|-------|
| Design | ibex RISC-V Core |
| PDK | ASAP7 7nm |
| Tool | OpenROAD |
| Clock | core_clock @ 1 GHz (1000 ps) |
| Paths indexed | 44 paths across 4 stages |

### Stages in database
| Stage | Description |
|-------|-------------|
| `3_resizer` | Post-resizer timing |
| `4_cts_final` | Post-CTS timing |
| `5_global_route` | Post-global route timing |
| `6_finish` | Final signoff timing |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| LLM | Claude (Anthropic API) |
| Embeddings | `all-MiniLM-L6-v2` (sentence-transformers) |
| Vector Store | ChromaDB (local, persistent) |
| UI | Streamlit |
| Report Parsing | Custom Python parser (`chunker.py`) |

---

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/laharipriyakakarla/sta-rag-chatbot.git
cd sta-rag-chatbot
```

### 2. Install dependencies
```bash
pip install chromadb sentence-transformers anthropic streamlit
```

### 3. Add your timing reports
Place your OpenROAD `.rpt` files in the `reports/` directory:
```
reports/
  3_resizer.rpt
  4_cts_final.rpt
  5_global_route.rpt
  6_finish.rpt
```

### 4. Build the vector store
```bash
python embedder.py
```

### 5. Set your Anthropic API key
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 6. Run the chatbot
```bash
streamlit run app.py
# or
python3 -m streamlit run app.py
```

Open `http://localhost:8501` in your browser.

---

## Project Structure

```
sta-rag-chatbot/
├── chunker.py        # Parses OpenROAD .rpt files into TimingPath objects
├── embedder.py       # Embeds paths into ChromaDB vector store
├── rag_pipeline.py   # RAG pipeline: retrieval + Claude API call
├── app.py            # Streamlit chat UI
├── reports/          # Place your .rpt timing report files here
├── chroma_db/        # Auto-generated vector store (gitignored)
├── LICENSE
└── README.md
```

---

## Key Features

- **Real timing data** — ingests actual OpenROAD path reports, not synthetic data
- **Semantic search** — finds relevant paths by meaning, not just keyword match
- **Expert STA reasoning** — Claude explains slack values, path types, CTS effects
- **Multi-stage awareness** — tracks timing closure across resizer → CTS → route → finish
- **Interactive UI** — example questions, adjustable retrieval count, retrieved path viewer

---

## Background

This project was built as a methodology tool to demonstrate AI-assisted EDA workflows. The ibex RISC-V core was implemented through a full RTL-to-GDSII flow using OpenROAD on the ASAP7 7nm PDK, achieving 870 MHz with 45% utilization.

The chatbot was designed to show how RAG can make timing closure data queryable in natural language — a practical tool for physical design and STA engineers.

---

## Author

**Lahari Priya Kakarla**  
MS Electrical Engineering, Arizona State University  
Specialization: ASIC Physical Design & Static Timing Analysis

# Multi-Agent AI Task Automation System — Specialized Agent Expansion (Pre-V8)

Welcome to the **Pre-V8 Specialized Agent Expansion** of the Multi-Agent AI Task Automation System!

This release significantly expands the agent architecture beyond linear LLM calls into a true multi-agent system coordinated by a dynamic Supervisor. It introduces **7 specialized domain agents**, a **least-privilege tool permission model**, **sandboxed code execution**, **read-only database safety**, **human-in-the-loop authorization**, and **checkpoint-resilient workflows**.

---

## 📌 Architecture Capability Map

```text
                           USER
                             │
                             ▼
                          FastAPI [POST /chat]
                             │
                             ▼
                      LangGraph State (Checkpointed)
                             │
                             ▼
                         SUPERVISOR (Dynamic Planning)
                             │
          ┌──────────────────┼──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
      RESEARCH           ANALYSIS           CODING
       AGENT               AGENT             AGENT
          │                  │                  │
          ▼                  ▼                  ▼
       RAG + MCP       Cross-Agent Data    AST Validator + Sandbox
                                                │
                                                ▼
                                             DATABASE
                                              AGENT
                                                │
                                                ▼
                                           Read-Only SQL
                                               
          ┌──────────────────┬──────────────────┐
          │                  │                  │
          ▼                  ▼                  ▼
      DOCUMENT            EMAIL             CALENDAR
       AGENT              AGENT               AGENT
          │                  │                  │
          ▼                  ▼                  ▼
    Artifact Store       Draft / Send*       Schedule / Events*
    (.md, .txt)        (*Confirmation)     (*Confirmation)

                             │
                             ▼
                           WRITER
                             │
                             ▼
                         VALIDATOR (Multi-Domain Audit)
                             │
                     ┌───────┴───────┐
                     ▼               ▼
                   PASS             FAIL
                     │               │
                     ▼               ▼
                    END       Writer Revision Loop (<= MAX_RETRIES)
```

> **Note**: This is a **capability map, NOT a fixed sequential pipeline**. The Supervisor dynamically plans the required agents, order, and dependencies per request.

---

# Specialized Agents

The system features 7 specialized domain agents alongside the Supervisor, Writer, and Validator:

| Agent | Responsibility | Core Tools & Permissions |
| :--- | :--- | :--- |
| **Research** | Web research and local knowledge retrieval | `web_search`, `calculator`, Local RAG Retriever |
| **Analysis** | Comparative analysis, pattern finding, reasoning | `calculator`, Cross-agent analytical synthesis |
| **Coding** | Code generation, debugging, refactoring, review | `validate_python_code` (AST), `execute_sandboxed_python` |
| **Database** | Schema inspection, SQL query generation, safe execution | `list_tables`, `describe_table`, `execute_read_query`, `get_sample_rows` (Read-only) |
| **Document** | Document authoring, structured reporting, artifact export | Document parser, artifact filesystem exporter (`data/documents/`) |
| **Email** | Email search, retrieval, drafting, confirmed dispatch | `search_emails`, `get_email`, `draft_email`, `send_email` (*Requires confirmation*) |
| **Calendar** | Schedule lookup, free-slot discovery, event coordination | `list_events`, `get_event`, `find_free_time`, `create_event`, `update_event`, `delete_event` (*Requires confirmation*) |
| **Writer** | Final synthesis, structured report compilation | Multi-agent context aggregation, revision drafting |
| **Validator** | Multi-domain policy auditing and quality gating | Factual grounding, AST code checks, SQL safety checks, date/time audits |

---

## 🎯 Supervisor Dynamic Routing Logic

The Supervisor does **not** hardcode a single static pipeline. Instead, it inspects the request and formulates a dynamic plan:

```text
Supervisor
    ↓
Agent Selection (e.g., Coding -> Database -> Coding)
    ↓
Dependency Planning (database depends on coding output)
    ↓
Dynamic Execution (nodes yield back to supervisor after each step)
    ↓
Validator Audit (checks correctness across domain checklists)
```

### Dynamic Plan Structure

```json
{
  "intent": "research_and_document",
  "agents": ["research", "analysis", "document"],
  "dependencies": {
    "analysis": ["research"],
    "document": ["analysis"]
  },
  "requires_confirmation": false,
  "plan": [
    "1. Research Agent gathers factual data from web and RAG",
    "2. Analysis Agent evaluates patterns and trade-offs",
    "3. Document Agent formats and exports publication report"
  ]
}
```

---

## 🔒 Security & Safety Principles

### 1. Tool Permission Model (Least Privilege)
Agents only receive the tools matching their assigned domain:
- Research Agent **cannot** write to databases or schedule events.
- Email Agent **cannot** run arbitrary code or access database schemas.
- Database Agent is strictly configured for **read-only operations** (`DATABASE_READ_ONLY=true`). Destructive commands (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`) are blocked by security policy.

### 2. Sandboxed Code Execution
- Python code generated by the Coding Agent is first audited via Python's `ast` parser.
- Disallowed modules (`os`, `sys`, `subprocess`, `shutil`, `socket`, `pty`, `ctypes`) and dangerous calls (`eval`, `exec`, `open`, `__import__`) are strictly rejected.
- Safe execution runs inside an isolated namespace with restricted builtins, strict timeout enforcement (`CODE_EXECUTION_TIMEOUT=5`), and stdout/stderr capture.

### 3. Human-in-the-Loop Confirmation
Destructive or external side-effect actions halt execution and request user approval:
- **Email Dispatch**: Drafting is automatic; sending (`send_email`) triggers `confirmation_required: true` and sets workflow state to `awaiting_confirmation`.
- **Calendar Event Modification**: Reading schedule is automatic; booking (`create_event`) or modifying events triggers `confirmation_required: true`.
- **Workflow Pausing & Resumption**: When confirmation is pending, LangGraph saves the checkpoint and pauses. The user resumes via `POST /chat` with `"confirm_action": true` (or `"false"` to safely reject).

---

## 🧩 Updated LangGraph Workflow State

The workflow state (`GraphState`) supports all domain artifacts seamlessly:

```python
class GraphState(TypedDict):
    thread_id: str
    user_query: str
    messages: List[Dict[str, Any]]
    
    # Dynamic Planning & Orchestration
    tasks: Optional[List[str]]
    current_task: Optional[str]
    current_agent: Optional[str]
    next_agent: Optional[str]
    execution_plan: Optional[Dict[str, Any]]
    agent_history: List[Dict[str, Any]]
    agent_logs: List[Dict[str, Any]]
    
    # Specialized Agent Results
    research_results: Optional[Dict[str, Any]]
    analysis: Optional[str]
    code_results: Optional[Dict[str, Any]]
    database_results: Optional[Dict[str, Any]]
    document_results: Optional[Dict[str, Any]]
    email_results: Optional[Dict[str, Any]]
    calendar_results: Optional[Dict[str, Any]]
    
    # Knowledge & Tools
    rag_context: Optional[str]
    retrieved_documents: Optional[List[Dict[str, Any]]]
    tool_results: Optional[List[Dict[str, Any]]]
    
    # Human-in-the-loop Confirmation
    pending_action: Optional[Dict[str, Any]]
    confirmation_required: bool
    confirmation_status: str  # "NONE" | "PENDING" | "APPROVED" | "REJECTED"
    
    # Synthesis & Validation Loop
    draft: Optional[str]
    validation_result: Optional[Dict[str, Any]]
    validation_feedback: Optional[str]
    final_report: Optional[str]
    response: str
    workflow_status: str
    retry_count: int
    iteration_count: int
```

---

## 💡 Multi-Agent Workflow Examples

### Workflow 1: Research, Analysis, & Document Authoring
> **User**: *"Research RAG architectures and generate a technical report."*
```text
Supervisor ──► Research Agent (RAG + Web) ──► Analysis Agent (Trade-offs) ──► Document Agent (Markdown export) ──► Validator (PASS) ──► END
```

### Workflow 2: Database Query & Analysis
> **User**: *"Analyze this database and explain the top customers."*
```text
Supervisor ──► Database Agent (Safe SELECT query) ──► Analysis Agent (Trends) ──► Writer (Summary) ──► Validator ──► END
```

### Workflow 3: Iterative Coding & Database Integration
> **User**: *"Create a Python FastAPI endpoint that queries PostgreSQL."*
```text
Supervisor ──► Coding Agent (Draft API) ──► Database Agent (Schema check) ──► Coding Agent (Integrated code) ──► Validator ──► END
```

### Workflow 4: Schedule Lookup & Email Drafting (Safe)
> **User**: *"Check tomorrow's meetings and draft an email summary."*
```text
Supervisor ──► Calendar Agent (list_events) ──► Analysis Agent (Summarize) ──► Email Agent (draft_email) ──► END (No confirmation needed)
```

### Workflow 5: Calendar Check & Confirmed Email Sending
> **User**: *"Check tomorrow's meetings and email me the summary."*
```text
Supervisor ──► Calendar Agent ──► Analysis Agent ──► Email Agent (draft_email)
                  │
                  ▼
         [Pause for Confirmation]
                  │
          User: confirm_action = true
                  │
                  ▼
         Email Agent (send_email) ──► Validator ──► END
```

---

## 🚀 API Usage Examples

### 1. Standard Multi-Agent Chat
```bash
curl -X POST "http://127.0.0.1:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "thread_demo_01",
    "message": "Find the top 5 customers in the database and analyze their spend."
  }'
```

### 2. Action Requiring Confirmation
```bash
curl -X POST "http://127.0.0.1:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "thread_schedule_01",
    "message": "Schedule a meeting with client tomorrow at 4 PM"
  }'
```
Response:
```json
{
  "thread_id": "thread_schedule_01",
  "status": "awaiting_confirmation",
  "confirmation_required": true,
  "pending_action": {
    "action": "create_calendar_event",
    "agent": "calendar",
    "details": {
      "title": "Interview Meeting",
      "start_time": "2026-10-01T14:00:00"
    }
  }
}
```

### 3. Approving Pending Action
```bash
curl -X POST "http://127.0.0.1:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "thread_id": "thread_schedule_01",
    "message": "Yes, please confirm and schedule.",
    "confirm_action": true
  }'
```

---

## 🧪 Comprehensive Verification Suite

Run the full regression and specialized agent test suite:

```powershell
.\venv\Scripts\python.exe -m pytest tests/test_calculator.py tests/test_key_rotation.py tests/test_mcp_client.py tests/test_mcp_server.py tests/test_tool_calling.py tests/test_web_search.py tests/test_rag.py tests/test_retrieval.py tests/test_validator.py tests/test_checkpoint.py tests/test_api.py tests/test_multi_agent_workflows.py tests/test_confirmation_workflow.py tests/test_specialized_agents.py
```

**Results:**
```text
======================= 87 passed in 167.90s (0:02:47) ========================
```
- **87 tests collected, 87 passed, 0 failures**.
- 100% regression stability across all legacy and expanded agent capabilities.

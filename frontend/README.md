# Multi-Agent AI — Frontend UI (Next.js + TypeScript + Tailwind CSS)

A minimalist, high-performance web interface for the **Multi-Agent AI Task Automation System** (FastAPI + LangGraph + Groq + SQLite Checkpoints + RAG).

---

## 🌟 Key Features

1. **Light Mode & Black Dark Mode**:
   - **Light Mode**: Clean white/very light gray backgrounds, subtle gray borders, near-black typography, and minimal styling.
   - **Black Dark Mode**: True black (`#000000`) background, deep sidebar (`#080808`), `#111111` cards, and `#222222` borders.
   - **Theme Persistence**: Preserves selection in `localStorage` and detects system preference (`prefers-color-scheme`) on first visit with zero layout/theme flash.

2. **Autonomous Multi-Agent Workflow Tracker**:
   - Real-time workflow status indicators: `✓ Completed`, `⟳ Running`, `○ Pending`, `✕ Failed`.
   - Expandable agent pipeline details covering the full lifecycle: `Supervisor ➔ Research Agent ➔ Analysis Agent ➔ Writer Agent ➔ Validator Agent`.

3. **Markdown & Code Highlighting**:
   - GitHub Flavored Markdown rendering with headings, bulleted/numbered lists, blockquotes, and tables.
   - Syntax-highlighted code blocks with a one-click **Copy Code** button.

4. **Human-in-the-Loop Confirmation**:
   - Clean action confirmation banner for sensitive operations (email dispatch, calendar appointments).
   - Interactive **Approve & Execute** and **Reject / Cancel** controls.

5. **RAG Knowledge Base Document Manager**:
   - Instant document upload (`.pdf`, `.txt`, `.md`) to the local SQLite vector database.
   - Document chunk count tracking and document deletion.

6. **Thread Persistence & Switcher**:
   - Live synchronization with backend SQLite checkpoints.
   - Conversation switcher in sidebar with inline **Rename** and **Delete** actions.

7. **Configurable Settings Area**:
   - Theme toggle (Light / Black Dark).
   - Chat behavior configuration (*Enter sends message / Shift+Enter for new line*).
   - API Server URL override (`NEXT_PUBLIC_API_URL`) with a live **Test Connection** ping.

---

## 🏗️ Component Structure

```text
frontend/
├── app/
│   ├── page.tsx            # Main workspace coordinator
│   ├── layout.tsx          # Root layout with anti-flash theme script
│   └── globals.css         # Tailwind directives & monochrome theme variables
│
├── components/
│   ├── chat/
│   │   ├── TopBar.tsx       # Minimal header (branding, theme toggle, settings)
│   │   ├── ChatWindow.tsx   # Message stream with auto-scrolling & error retry
│   │   ├── Message.tsx      # User bubbles & AI responses with Markdown
│   │   ├── MessageInput.tsx # Auto-growing textarea with file upload status
│   │   └── EmptyState.tsx   # Capabilities list and clickable prompt cards
│   │
│   ├── sidebar/
│   │   ├── Sidebar.tsx          # Responsive two-column sidebar & mobile drawer
│   │   ├── ConversationList.tsx # Thread list with inline rename & delete
│   │   └── NewChatButton.tsx    # "+ New Chat" button (Ctrl+N shortcut)
│   │
│   ├── agents/
│   │   └── AgentActivity.tsx    # Concise high-level agent stage indicator
│   │
│   ├── documents/
│   │   ├── DocumentUpload.tsx   # Drag-and-drop file uploader
│   │   └── KnowledgeBase.tsx    # Document manager modal with chunk statistics
│   │
│   ├── sources/
│   │   └── Sources.tsx          # Collapsible citations with chunk metadata
│   │
│   ├── settings/
│   │   └── Settings.tsx         # Modal for theme, chat behavior, and API config
│   │
│   └── theme/
│       └── ThemeToggle.tsx      # Sun / Moon theme switch
│
└── lib/
    ├── api.ts              # Clean REST & SSE API integration layer
    └── types.ts            # TypeScript data contracts
```

---

## 🚀 How to Run

### 1. Start the FastAPI Backend
From the root directory:
```powershell
cd "d:\Multi-Agent System\backend"
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Start the Next.js Frontend
From the `frontend/` directory:
```powershell
cd "d:\Multi-Agent System\frontend"
npm run dev
```

Open your browser at: **`http://localhost:3000`**

### 3. Production Build
```powershell
npm run build
npm run start
```

---

## ⚙️ Environment Configuration

Set the FastAPI backend URL in `frontend/.env.local`:
```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```
Alternatively, configure and test the API URL at runtime via the in-app **⚙️ Settings** modal.

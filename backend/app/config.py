"""
Configuration module for Multi-Agent AI Task Automation System (Version 1).
Loads environment variables securely using python-dotenv.
"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Resolve project root (multi-agent-ai directory)
BASE_DIR = Path(__file__).resolve().parent.parent

# Initial load of .env file from project root
load_dotenv(dotenv_path=BASE_DIR / ".env")


class Settings:
    """Application settings and configuration parameters."""

    PROJECT_NAME: str = "Multi-Agent AI Task Automation API"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = (
        "Version 1: Foundation REST API connecting FastAPI to an open-source "
        "LLM via the Groq API."
    )

    _groq_api_keys_override: Optional[list[str]] = None
    _openai_api_keys_override: Optional[list[str]] = None
    _openrouter_api_keys_override: Optional[list[str]] = None
    _grok_api_keys_override: Optional[list[str]] = None
    _ollama_base_url_override: Optional[str] = None
    _ollama_model_override: Optional[str] = None
    _llm_provider_override: Optional[str] = None

    @property
    def LLM_PROVIDER(self) -> str:
        """Provider strategy: 'ollama' / 'local', 'round_robin', 'groq', 'openai', 'openrouter', or 'grok'."""
        if self._llm_provider_override is not None:
            return self._llm_provider_override
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("LLM_PROVIDER", "round_robin").strip().lower()

    @LLM_PROVIDER.setter
    def LLM_PROVIDER(self, val: str) -> None:
        self._llm_provider_override = val

    @property
    def GROQ_API_KEYS(self) -> list[str]:
        """Dynamically read list of Groq API keys for round-robin rotation."""
        if self._groq_api_keys_override is not None:
            return self._groq_api_keys_override
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        raw = os.getenv("GROQ_API_KEYS", "").strip()
        if raw:
            keys = [k.strip() for k in raw.split(",") if k.strip() and k.strip() != "your_api_key_here"]
            if keys:
                return keys
        single = os.getenv("GROQ_API_KEY", "").strip()
        if single and single != "your_api_key_here":
            return [single]
        return []

    @GROQ_API_KEYS.setter
    def GROQ_API_KEYS(self, keys: list[str]) -> None:
        """Allow runtime override of API keys (useful for testing)."""
        self._groq_api_keys_override = keys

    @property
    def GROQ_API_KEY(self) -> str:
        """Dynamically read GROQ_API_KEY to detect updates to .env in real-time."""
        keys = self.GROQ_API_KEYS
        return keys[0] if keys else ""

    @property
    def GROQ_MODEL(self) -> str:
        """Dynamically read GROQ_MODEL to allow model switching without restart."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()

    @property
    def OPENAI_API_KEYS(self) -> list[str]:
        """Dynamically read list of OpenAI API keys for round-robin rotation."""
        if self._openai_api_keys_override is not None:
            return self._openai_api_keys_override
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        raw = os.getenv("OPENAI_API_KEYS", "").strip()
        if raw:
            keys = [k.strip() for k in raw.split(",") if k.strip() and k.strip() != "your_api_key_here"]
            if keys:
                return keys
        single = os.getenv("OPENAI_API_KEY", "").strip()
        if single and single != "your_api_key_here":
            return [single]
        return []

    @OPENAI_API_KEYS.setter
    def OPENAI_API_KEYS(self, keys: list[str]) -> None:
        self._openai_api_keys_override = keys

    @property
    def OPENAI_API_KEY(self) -> str:
        keys = self.OPENAI_API_KEYS
        return keys[0] if keys else ""

    @property
    def OPENAI_MODEL(self) -> str:
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()

    @property
    def OPENROUTER_API_KEYS(self) -> list[str]:
        """Dynamically read list of OpenRouter API keys for round-robin rotation."""
        if self._openrouter_api_keys_override is not None:
            return self._openrouter_api_keys_override
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        raw = os.getenv("OPENROUTER_API_KEYS", "").strip()
        if raw:
            keys = [k.strip() for k in raw.split(",") if k.strip() and k.strip() != "your_api_key_here"]
            if keys:
                return keys
        single = os.getenv("OPENROUTER_API_KEY", "").strip()
        if single and single != "your_api_key_here":
            return [single]
        return []

    @OPENROUTER_API_KEYS.setter
    def OPENROUTER_API_KEYS(self, keys: list[str]) -> None:
        self._openrouter_api_keys_override = keys

    @property
    def OPENROUTER_API_KEY(self) -> str:
        keys = self.OPENROUTER_API_KEYS
        return keys[0] if keys else ""

    @property
    def OPENROUTER_MODEL(self) -> str:
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini").strip()

    @property
    def GROK_API_KEYS(self) -> list[str]:
        """Dynamically read list of Grok (xAI) API keys for round-robin rotation."""
        if self._grok_api_keys_override is not None:
            return self._grok_api_keys_override
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        raw = os.getenv("GROK_API_KEYS", os.getenv("XAI_API_KEYS", "")).strip()
        if raw:
            keys = [k.strip() for k in raw.split(",") if k.strip() and k.strip() != "your_api_key_here"]
            if keys:
                return keys
        single = os.getenv("GROK_API_KEY", os.getenv("XAI_API_KEY", "")).strip()
        if single and single != "your_api_key_here":
            return [single]
        return []

    @GROK_API_KEYS.setter
    def GROK_API_KEYS(self, keys: list[str]) -> None:
        self._grok_api_keys_override = keys

    @property
    def GROK_API_KEY(self) -> str:
        keys = self.GROK_API_KEYS
        return keys[0] if keys else ""

    @property
    def GROK_MODEL(self) -> str:
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("GROK_MODEL", os.getenv("XAI_MODEL", "grok-beta")).strip()

    @property
    def OLLAMA_BASE_URL(self) -> str:
        """Local Ollama endpoint URL (defaults to http://127.0.0.1:11434)."""
        if self._ollama_base_url_override is not None:
            return self._ollama_base_url_override
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").strip()

    @OLLAMA_BASE_URL.setter
    def OLLAMA_BASE_URL(self, url: str) -> None:
        self._ollama_base_url_override = url

    @property
    def OLLAMA_MODEL(self) -> str:
        """Local Ollama model name (defaults to qwen3.5:4b)."""
        if self._ollama_model_override is not None:
            return self._ollama_model_override
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("OLLAMA_MODEL", "qwen3.5:4b").strip()

    @OLLAMA_MODEL.setter
    def OLLAMA_MODEL(self, model: str) -> None:
        self._ollama_model_override = model

    @property
    def SEARCH_PROVIDER(self) -> str:
        """Search provider selection: 'auto', 'duckduckgo', 'tavily', or 'serper'."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("SEARCH_PROVIDER", "auto").strip().lower()

    @property
    def TAVILY_API_KEY(self) -> str:
        """Tavily search API key."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("TAVILY_API_KEY", "").strip()

    @property
    def SERPER_API_KEY(self) -> str:
        """Serper (Google Search) API key."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("SERPER_API_KEY", "").strip()

    @property
    def MCP_SERVER_URL(self) -> str:
        """MCP server URL for SSE transport (default: http://127.0.0.1:8001/sse)."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8001/sse").strip()

    @property
    def MCP_TRANSPORT(self) -> str:
        """MCP transport protocol: 'auto', 'sse', 'stdio', or 'direct'."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("MCP_TRANSPORT", "auto").strip().lower()

    @property
    def DATA_DIR(self) -> Path:
        """Base directory for persistent storage."""
        data_path = BASE_DIR / "data"
        data_path.mkdir(parents=True, exist_ok=True)
        return data_path

    @property
    def DOCUMENTS_DIR(self) -> Path:
        """Directory for uploaded documents."""
        docs_path = self.DATA_DIR / "documents"
        docs_path.mkdir(parents=True, exist_ok=True)
        return docs_path

    @property
    def CHECKPOINT_DB_PATH(self) -> str:
        """SQLite database path for LangGraph persistent workflow checkpointing."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        default_path = str(self.DATA_DIR / "checkpoints.db")
        return os.getenv("CHECKPOINT_DB_PATH", default_path).strip()

    @property
    def VECTOR_DB_PATH(self) -> str:
        """Persistent storage path for local vector database."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        default_path = str(self.DATA_DIR / "vector_store.json")
        return os.getenv("VECTOR_DB_PATH", default_path).strip()

    @property
    def MAX_RETRIES(self) -> int:
        """Maximum retry cycles for Validator rejection to prevent infinite loops."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        try:
            return int(os.getenv("MAX_RETRIES", "2").strip())
        except ValueError:
            return 2

    @property
    def CHUNK_SIZE(self) -> int:
        """Target character size per document chunk for RAG ingestion."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        try:
            return int(os.getenv("CHUNK_SIZE", "500").strip())
        except ValueError:
            return 500

    @property
    def CHUNK_OVERLAP(self) -> int:
        """Character overlap between consecutive chunks for RAG ingestion."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        try:
            return int(os.getenv("CHUNK_OVERLAP", "50").strip())
        except ValueError:
            return 50

    @property
    def TOP_K(self) -> int:
        """Default number of top relevant chunks to retrieve during RAG search."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        try:
            return int(os.getenv("TOP_K", "5").strip())
        except ValueError:
            return 5

    @property
    def EMBEDDING_MODEL(self) -> str:
        """Local open-source embedding model name."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5").strip()

    @property
    def DATABASE_PATH(self) -> str:
        """SQLite database path for Database Agent queries."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        default_path = str(self.DATA_DIR / "app_database.db")
        return os.getenv("DATABASE_PATH", default_path).strip()

    @property
    def DATABASE_READ_ONLY(self) -> bool:
        """Enforces read-only safety for Database Agent (rejects non-SELECT/destructive queries)."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        val = os.getenv("DATABASE_READ_ONLY", "true").strip().lower()
        return val in ("1", "true", "yes", "on")

    @property
    def CODE_EXECUTION_SANDBOX(self) -> bool:
        """Enforces restricted AST sandboxing and limits for Python execution."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        val = os.getenv("CODE_EXECUTION_SANDBOX", "true").strip().lower()
        return val in ("1", "true", "yes", "on")

    @property
    def CODE_EXECUTION_TIMEOUT(self) -> int:
        """Maximum execution timeout in seconds for sandboxed code."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        try:
            return int(os.getenv("CODE_EXECUTION_TIMEOUT", "5").strip())
        except ValueError:
            return 5

    @property
    def EMAIL_STORAGE_PATH(self) -> str:
        """Storage path for local Email Agent mock/store."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        default_path = str(self.DATA_DIR / "emails.json")
        return os.getenv("EMAIL_STORAGE_PATH", default_path).strip()

    @property
    def CALENDAR_STORAGE_PATH(self) -> str:
        """Storage path for local Calendar Agent mock/store."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        default_path = str(self.DATA_DIR / "calendar.json")
        return os.getenv("CALENDAR_STORAGE_PATH", default_path).strip()

    # SMTP Configuration for live email dispatch
    @property
    def SMTP_HOST(self) -> str:
        """SMTP server host (e.g. smtp.gmail.com)."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("SMTP_HOST", "").strip()

    @property
    def SMTP_PORT(self) -> int:
        """SMTP server port (e.g. 587 for TLS, 465 for SSL)."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        try:
            return int(os.getenv("SMTP_PORT", "587").strip())
        except ValueError:
            return 587

    @property
    def SMTP_USER(self) -> str:
        """SMTP username or sending email address."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("SMTP_USER", "").strip()

    @property
    def SMTP_PASSWORD(self) -> str:
        """SMTP app password or secret."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("SMTP_PASSWORD", "").strip()

    @property
    def SMTP_FROM_EMAIL(self) -> str:
        """Display sender email address (defaults to SMTP_USER)."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        from_addr = os.getenv("SMTP_FROM_EMAIL", "").strip()
        return from_addr or self.SMTP_USER

    @property
    def SMTP_USE_TLS(self) -> bool:
        """Whether to use STARTTLS (default True for port 587)."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        val = os.getenv("SMTP_USE_TLS", "true").strip().lower()
        return val in ("1", "true", "yes", "on")

    # IMAP Configuration for live email reading (inbox search/fetch)
    @property
    def IMAP_HOST(self) -> str:
        """IMAP server host (defaults to imap.gmail.com)."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("IMAP_HOST", "imap.gmail.com").strip()

    @property
    def IMAP_PORT(self) -> int:
        """IMAP server port (defaults to 993 for SSL)."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        try:
            return int(os.getenv("IMAP_PORT", "993").strip())
        except ValueError:
            return 993

    @property
    def IMAP_USER(self) -> str:
        """IMAP username (defaults to SMTP_USER)."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("IMAP_USER", "").strip() or self.SMTP_USER

    @property
    def IMAP_PASSWORD(self) -> str:
        """IMAP password (defaults to SMTP_PASSWORD)."""
        load_dotenv(dotenv_path=BASE_DIR / ".env", override=True)
        return os.getenv("IMAP_PASSWORD", "").strip() or self.SMTP_PASSWORD


settings = Settings()

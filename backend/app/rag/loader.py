"""
Document Loader module for RAG ingestion (Version 7).

Provides modular document parsing for:
- PDF (.pdf) with page-level extraction
- Plain Text (.txt)
- Markdown (.md)

Designed with an extensible parser registry to easily accommodate future formats
(e.g., DOCX, HTML, CSV).
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Type

logger = logging.getLogger(__name__)


class BaseDocumentParser(ABC):
    """Abstract base class for document format parsers."""

    @abstractmethod
    def parse(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Parse file into a list of page/section dictionaries.

        Returns:
            List[Dict[str, Any]]: Each item has 'text' (str), 'page' (int), and 'filename' (str).
        """
        pass


class PDFParser(BaseDocumentParser):
    """Extracts text page by page from PDF files using pypdf."""

    def parse(self, file_path: Path) -> List[Dict[str, Any]]:
        from pypdf import PdfReader

        pages_data: List[Dict[str, Any]] = []
        try:
            reader = PdfReader(str(file_path))
            total_pages = len(reader.pages)
            logger.info("Parsing PDF '%s' with %d pages...", file_path.name, total_pages)

            for page_num, page in enumerate(reader.pages, start=1):
                extracted = page.extract_text() or ""
                cleaned = extracted.strip()
                if cleaned:
                    pages_data.append(
                        {
                            "text": cleaned,
                            "page": page_num,
                            "filename": file_path.name,
                        }
                    )

            if not pages_data:
                logger.warning("PDF '%s' contains no extractable text.", file_path.name)
        except Exception as err:
            logger.error("Failed to parse PDF '%s': %s", file_path.name, err)
            raise ValueError(f"Error extracting text from PDF '{file_path.name}': {err}") from err

        return pages_data


class TextParser(BaseDocumentParser):
    """Extracts text from plain text (.txt) files."""

    def parse(self, file_path: Path) -> List[Dict[str, Any]]:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception as err:
            logger.error("Failed to read text file '%s': %s", file_path.name, err)
            raise ValueError(f"Error reading text file '{file_path.name}': {err}") from err

        if not content:
            logger.warning("Text file '%s' is empty.", file_path.name)
            return []

        return [
            {
                "text": content,
                "page": 1,
                "filename": file_path.name,
            }
        ]


class MarkdownParser(BaseDocumentParser):
    """Extracts text from Markdown (.md) files."""

    def parse(self, file_path: Path) -> List[Dict[str, Any]]:
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception as err:
            logger.error("Failed to read markdown file '%s': %s", file_path.name, err)
            raise ValueError(f"Error reading markdown file '{file_path.name}': {err}") from err

        if not content:
            logger.warning("Markdown file '%s' is empty.", file_path.name)
            return []

        return [
            {
                "text": content,
                "page": 1,
                "filename": file_path.name,
            }
        ]


class DocumentLoader:
    """
    Modular document loader with parser registry.
    """

    _registry: Dict[str, Type[BaseDocumentParser]] = {
        ".pdf": PDFParser,
        ".txt": TextParser,
        ".text": TextParser,
        ".md": MarkdownParser,
        ".markdown": MarkdownParser,
    }

    @classmethod
    def register_parser(cls, extension: str, parser_cls: Type[BaseDocumentParser]) -> None:
        """Register a new parser for a custom file extension."""
        ext = extension.lower() if extension.startswith(".") else f".{extension.lower()}"
        cls._registry[ext] = parser_cls
        logger.info("Registered custom parser for extension: %s", ext)

    @classmethod
    def load(cls, file_path: Path) -> List[Dict[str, Any]]:
        """
        Load and extract text from supported document types.

        Args:
            file_path (Path): Path to document file.

        Returns:
            List[Dict[str, Any]]: Extracted pages/sections with text and page metadata.

        Raises:
            FileNotFoundError: If file does not exist.
            ValueError: If file format is unsupported.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Document file not found: {file_path}")

        ext = file_path.suffix.lower()
        parser_cls = cls._registry.get(ext)
        if not parser_cls:
            supported = ", ".join(cls._registry.keys())
            raise ValueError(
                f"Unsupported file type '{ext}'. Supported formats: {supported}"
            )

        parser = parser_cls()
        return parser.parse(file_path)

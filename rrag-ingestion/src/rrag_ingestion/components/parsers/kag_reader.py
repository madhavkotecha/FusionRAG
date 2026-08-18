from __future__ import annotations

import csv
import json
import logging
import os
import uuid

from rrag_ingestion.components.parsers.base import BaseParser
from rrag_ingestion.core.base import ComponentResult, register_component
from rrag_ingestion.models.document import Document

logger = logging.getLogger(__name__)


@register_component
class KAGFileReader(BaseParser):
    name = "kag.file_reader"
    version = "0.1.0"
    description = "KAG-style file reader for structured/unstructured data (CSV, JSON, TXT, MD, PDF)"
    config_schema = {
        "content_field": {"type": "string", "default": "content", "description": "Field name for content in JSON/CSV"},
        "id_field": {"type": "string", "default": "id", "description": "Field name for document ID"},
    }

    async def invoke(self, input_data: ComponentResult, config: dict) -> ComponentResult:
        file_paths = input_data.data.get("file_paths", [])
        existing_docs = input_data.data.get("documents", [])
        content_field = config.get("content_field", "content")
        id_field = config.get("id_field", "id")

        documents = list(existing_docs)
        errors = []

        for fp in file_paths:
            ext = os.path.splitext(fp)[1].lower().lstrip(".")
            try:
                if ext == "json":
                    docs = self._read_json(fp, content_field, id_field)
                elif ext == "csv":
                    docs = self._read_csv(fp, content_field, id_field)
                elif ext == "pdf":
                    text = self._read_pdf(fp)
                    docs = [Document(
                        id=str(uuid.uuid4()),
                        filename=os.path.basename(fp),
                        content_type="application/pdf",
                        raw_text=text,
                        file_path=fp,
                        metadata={"parser": self.name},
                    )]
                elif ext in ("txt", "md", "markdown"):
                    with open(fp, "r", encoding="utf-8") as f:
                        text = f.read()
                    docs = [Document(
                        id=str(uuid.uuid4()),
                        filename=os.path.basename(fp),
                        content_type="text/plain",
                        raw_text=text,
                        file_path=fp,
                        metadata={"parser": self.name},
                    )]
                else:
                    errors.append(f"Unsupported format for KAG reader: {ext}")
                    continue
                documents.extend(docs)
            except Exception as e:
                errors.append(f"Failed to read {fp}: {e}")

        return ComponentResult(
            data={"documents": documents},
            metadata={"read_count": len(documents)},
            errors=errors,
        )

    def _read_pdf(self, file_path: str) -> str:
        try:
            import fitz  # pymupdf
            doc = fitz.open(file_path)
            pages = []
            for page in doc:
                pages.append(page.get_text())
            doc.close()
            return "\n\n".join(pages)
        except ImportError:
            logger.warning("pymupdf not installed, reading PDF as binary placeholder")
            return f"[PDF content from {os.path.basename(file_path)} - install pymupdf for parsing]"

    def _read_json(self, file_path: str, content_field: str, id_field: str) -> list[Document]:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = [data]
        else:
            return []

        docs = []
        for item in items:
            content = item.get(content_field, json.dumps(item))
            doc_id = str(item.get(id_field, uuid.uuid4()))
            docs.append(Document(
                id=doc_id,
                filename=os.path.basename(file_path),
                content_type="application/json",
                raw_text=content,
                file_path=file_path,
                metadata={"parser": self.name, "source_item": item},
            ))
        return docs

    def _read_csv(self, file_path: str, content_field: str, id_field: str) -> list[Document]:
        docs = []
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                content = row.get(content_field, str(row))
                doc_id = str(row.get(id_field, uuid.uuid4()))
                docs.append(Document(
                    id=doc_id,
                    filename=os.path.basename(file_path),
                    content_type="text/csv",
                    raw_text=content,
                    file_path=file_path,
                    metadata={"parser": self.name, "row": dict(row)},
                ))
        return docs

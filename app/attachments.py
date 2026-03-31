from __future__ import annotations

from pathlib import Path
from typing import Any

from docx import Document
from pypdf import PdfReader


MAX_CHARS_PER_ATTACHMENT = 18000
TEXT_EXTENSIONS = {
    ".bat",
    ".c",
    ".cpp",
    ".css",
    ".csv",
    ".env",
    ".go",
    ".h",
    ".hpp",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".log",
    ".md",
    ".ps1",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".tex",
    ".toml",
    ".ts",
    ".tsx",
    ".tsv",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def _decode_text_bytes(raw_bytes: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="replace")


def _clean_text(text: str) -> str:
    lines = [line.rstrip() for line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip()


def _extract_text_from_plain_file(file_path: Path) -> str:
    raw_bytes = file_path.read_bytes()
    if b"\x00" in raw_bytes:
        raise ValueError("This looks like a binary file, not a readable text document.")
    return _clean_text(_decode_text_bytes(raw_bytes))


def _extract_text_from_pdf(file_path: Path) -> str:
    reader = PdfReader(str(file_path))
    chunks: list[str] = []
    for page in reader.pages:
        chunks.append(page.extract_text() or "")
    return _clean_text("\n\n".join(chunks))


def _extract_text_from_docx(file_path: Path) -> str:
    document = Document(str(file_path))
    paragraphs = [paragraph.text for paragraph in document.paragraphs]
    return _clean_text("\n".join(paragraphs))


def _extract_attachment_text(file_path: Path, content_type: str) -> tuple[str, str]:
    extension = file_path.suffix.lower()
    normalized_content_type = (content_type or "").lower()

    if extension == ".pdf" or normalized_content_type == "application/pdf":
        return _extract_text_from_pdf(file_path), "pdf"

    if extension == ".docx" or normalized_content_type.endswith(
        "wordprocessingml.document"
    ):
        return _extract_text_from_docx(file_path), "docx"

    if extension in TEXT_EXTENSIONS or normalized_content_type.startswith("text/"):
        return _extract_text_from_plain_file(file_path), "text"

    raise ValueError("This file type is not supported for local text extraction.")


def enrich_attachments_for_ollama(
    file_paths: list[Path],
    attachment_metadata: list[dict[str, Any]],
    logger,
) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []

    for metadata, file_path in zip(attachment_metadata, file_paths, strict=False):
        attachment = dict(metadata)
        attachment["ollama_supported"] = False
        attachment["ollama_source_type"] = ""
        attachment["ollama_text"] = ""
        attachment["ollama_text_chars"] = 0
        attachment["ollama_truncated"] = False
        attachment["ollama_error"] = ""

        try:
            extracted_text, source_type = _extract_attachment_text(
                file_path,
                str(attachment.get("content_type") or ""),
            )
            if not extracted_text:
                raise ValueError("No readable text could be extracted from this file.")

            attachment["ollama_supported"] = True
            attachment["ollama_source_type"] = source_type
            attachment["ollama_text_chars"] = len(extracted_text)
            if len(extracted_text) > MAX_CHARS_PER_ATTACHMENT:
                attachment["ollama_text"] = extracted_text[:MAX_CHARS_PER_ATTACHMENT].rstrip()
                attachment["ollama_truncated"] = True
            else:
                attachment["ollama_text"] = extracted_text

            logger.info(
                "Extracted %s characters from attachment '%s' for Ollama.",
                attachment["ollama_text_chars"],
                attachment.get("name") or file_path.name,
            )
        except Exception as exc:
            attachment["ollama_error"] = str(exc)
            logger.warning(
                "Unable to extract attachment '%s' for Ollama: %s",
                attachment.get("name") or file_path.name,
                exc,
            )

        enriched.append(attachment)

    return enriched


def build_ollama_attachment_context(attachments: list[dict[str, Any]] | None) -> str:
    normalized_attachments = list(attachments or [])
    readable = [attachment for attachment in normalized_attachments if attachment.get("ollama_supported") and attachment.get("ollama_text")]
    skipped = [attachment for attachment in normalized_attachments if not attachment.get("ollama_supported")]

    if not readable and not skipped:
        return ""

    sections = [
        "The attached file contents have already been extracted locally for the model below.",
        "Use that extracted text as the actual attachment content and do not say that you cannot access uploaded files.",
        "Attached file context for the local model:",
    ]

    for attachment in readable:
        header = f"[File: {attachment.get('name') or 'Attachment'}]"
        body = str(attachment.get("ollama_text") or "").strip()
        if attachment.get("ollama_truncated"):
            body = f"{body}\n\n[Content truncated for local model after {MAX_CHARS_PER_ATTACHMENT} characters.]"
        sections.append(f"{header}\n{body}")

    if skipped:
        skipped_lines = []
        for attachment in skipped:
            reason = str(attachment.get("ollama_error") or "Unsupported file type.")
            skipped_lines.append(f"- {attachment.get('name') or 'Attachment'}: {reason}")
        sections.append("Files not readable by the local model:\n" + "\n".join(skipped_lines))

    return "\n\n".join(section.strip() for section in sections if section.strip())


def build_ollama_user_content(message: str, attachments: list[dict[str, Any]] | None) -> str:
    context = build_ollama_attachment_context(attachments)
    clean_message = str(message or "").strip()

    if clean_message and context:
        return f"{clean_message}\n\n{context}"
    if context:
        return context
    return clean_message

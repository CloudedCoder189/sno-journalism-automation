import html
from pathlib import Path

from docx import Document


BASE_DIR = Path(__file__).resolve().parent
ARTICLES_DIR = BASE_DIR / "articles"


def load_article(filename):
    path = ARTICLES_DIR / filename

    if not path.exists():
        raise FileNotFoundError(f"Could not find article file: {path}")

    suffix = path.suffix.lower()

    if suffix == ".txt":
        return _load_txt(path)

    if suffix == ".docx":
        return _load_docx(path)

    raise ValueError("Unsupported file type. Use .txt or .docx.")


def _load_txt(path):
    text = path.read_text(encoding="utf-8").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if not lines:
        return path.stem.replace("_", " ").title(), "", ""

    title = lines[0]
    body_lines = lines[1:]
    plain_text = "\n\n".join(body_lines)
    html_content = _paragraphs_to_html(body_lines)

    return title, html_content, plain_text


def _load_docx(path):
    doc = Document(path)
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    if not paragraphs:
        return path.stem.replace("_", " ").title(), "", ""

    title = paragraphs[0]
    body_paragraphs = paragraphs[1:]
    plain_text = "\n\n".join(body_paragraphs)
    html_content = _paragraphs_to_html(body_paragraphs)

    return title, html_content, plain_text


def _paragraphs_to_html(paragraphs):
    return "\n".join(f"<p>{html.escape(paragraph)}</p>" for paragraph in paragraphs)

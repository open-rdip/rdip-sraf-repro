# rag_pipeline/chunker.py
"""
Splits a research paper PDF into text chunks suitable for embedding.
Attempts to isolate the Methods/Experimental section first,
then falls back to chunking the full paper body.
"""

import re
from pathlib import Path
from pypdf import PdfReader
from sympy import python


# Section headings that typically contain reproducibility metadata
METHODS_PATTERNS = [
    r"^\d[\.\s]+(experimental\s+setup|experimental\s+design)",
    r"^\d[\.\s]+(implementation\s+details?)",
    r"^\d[\.\s]+(methodology|methods?)",
    r"^\d[\.\s]+(experiments?)",
    r"^\d[\.\s]+(setup\s+and\s+implementation)",
    r"(experimental\s+setup|implementation\s+details?|methodology)",
]

# Sections that signal end of methods — stop extracting here
END_PATTERNS = [
    r"^\d[\.\s]+(results?|evaluation|conclusion|discussion|related\s+work)",
    r"^(references|bibliography|acknowledgements?)",
]


def extract_text(pdf_path: str) -> str:
    """
    Extract full text from a PDF file.
    Returns concatenated text from all pages.
    """
    path = Path(pdf_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    reader = PdfReader(str(path))
    pages  = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)

    return "\n".join(pages)


def extract_methods_section(full_text: str) -> str:
    """
    Attempt to isolate the Methods / Experimental Setup section.
    Returns the section text if found, otherwise returns
    the middle 50% of the paper (where methods typically appear).
    """
    lines        = full_text.splitlines()
    start_line   = None
    end_line     = None

    for i, line in enumerate(lines):
        stripped = line.strip().lower()
        if not stripped:
            continue

        # Look for methods section start
        if start_line is None:
            for pattern in METHODS_PATTERNS:
                if re.search(pattern, stripped, re.IGNORECASE):
                    start_line = i
                    break

        # Look for end of methods section
        elif end_line is None:
            for pattern in END_PATTERNS:
                if re.search(pattern, stripped, re.IGNORECASE):
                    end_line = i
                    break

        if start_line and end_line:
            break

    if start_line is not None:
        end = end_line if end_line else min(start_line + 200, len(lines))
        section = "\n".join(lines[start_line:end])
        if len(section.split()) > 100:
            return section

    # Fallback: middle 50% of the paper
    quarter = len(lines) // 4
    return "\n".join(lines[quarter: quarter * 3])


def chunk_text(text: str,
               chunk_size: int = 400,
               overlap: int = 50) -> list[str]:
    """
    Split text into overlapping word-level chunks.
    chunk_size: words per chunk
    overlap:    words shared between adjacent chunks
    Returns list of chunk strings.
    """
    words  = text.split()
    chunks = []
    step   = chunk_size - overlap

    for i in range(0, len(words), step):
        chunk = " ".join(words[i: i + chunk_size])
        if len(chunk.split()) >= 30:   # skip very short trailing chunks
            chunks.append(chunk)

    return chunks


def load_paper(pdf_path: str,
               methods_only: bool = True) -> list[str]:
    """
    Main entry point — load a PDF and return a list of text chunks.

    Args:
        pdf_path:     path to the PDF file
        methods_only: if True, try to extract methods section first
                      before chunking (recommended for reproducibility
                      metadata extraction)
    Returns:
        list of text chunk strings
    """
    full_text = extract_text(pdf_path)

    if methods_only:
        section = extract_methods_section(full_text)
    else:
        section = full_text

    chunks = chunk_text(section, chunk_size=200, overlap=25)
    print(f"[Chunker] {Path(pdf_path).name}: "
          f"{len(full_text.split())} words → "
          f"{len(chunks)} chunks "
          f"({'methods section' if methods_only else 'full text'})")

    return chunks

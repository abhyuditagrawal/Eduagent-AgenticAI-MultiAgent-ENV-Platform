import fitz


def extract_text_from_pdf(file_path: str) -> list[dict]:
    doc = fitz.open(file_path)
    pages = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        text = page.get_text()
        if text.strip():
            pages.append({"text": text, "page_number": page_num + 1})
    doc.close()
    return pages


def chunk_text(
    pages: list[dict],
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[dict]:
    full_text = ""
    page_boundaries = []

    for page in pages:
        start = len(full_text)
        full_text += page["text"] + "\n"
        end = len(full_text)
        page_boundaries.append(
            {"start": start, "end": end, "page_number": page["page_number"]}
        )

    words = full_text.split()
    chunks = []
    chunk_index = 0
    i = 0

    while i < len(words):
        chunk_words = words[i : i + chunk_size]
        chunk_text_str = " ".join(chunk_words)

        chunk_start = full_text.find(chunk_words[0], max(0, i - 1))
        page_num = 1
        for boundary in page_boundaries:
            if chunk_start >= boundary["start"] and chunk_start < boundary["end"]:
                page_num = boundary["page_number"]
                break

        chunks.append(
            {
                "text": chunk_text_str,
                "page": page_num,
                "chunk_index": chunk_index,
            }
        )

        chunk_index += 1
        i += chunk_size - overlap

    return chunks

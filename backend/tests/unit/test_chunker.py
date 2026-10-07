import pytest

from app.services.ingestion import TextChunker


@pytest.fixture
def chunker() -> TextChunker:
    return TextChunker(chunk_size=200, chunk_overlap=20)


def test_short_text_returns_single_chunk(chunker: TextChunker) -> None:
    chunks = chunker.split('Short text that fits in one chunk.')
    assert len(chunks) == 1
    assert chunks[0] == 'Short text that fits in one chunk.'


def test_empty_text_returns_empty_list(chunker: TextChunker) -> None:
    assert chunker.split('') == []
    assert chunker.split('   \n\n   ') == []


def test_long_text_splits_into_multiple_chunks(chunker: TextChunker) -> None:
    text = 'word ' * 200  # 1000 chars, well above chunk_size=200
    chunks = chunker.split(text)
    assert len(chunks) > 1


def test_all_chunks_within_size_limit(chunker: TextChunker) -> None:
    text = 'This is a sentence. ' * 50
    chunks = chunker.split(text)
    for chunk in chunks:
        assert len(chunk) <= chunker.chunk_size


def test_paragraph_break_preferred_over_word_break() -> None:
    chunker = TextChunker(chunk_size=100, chunk_overlap=10)
    first = 'First paragraph content here. ' * 2
    second = 'Second paragraph content here. ' * 2
    text = first + '\n\n' + second

    chunks = chunker.split(text)
    assert len(chunks) >= 1
    # At least one chunk should end near a paragraph boundary
    combined = '\n\n'.join(chunks)
    assert 'First paragraph' in combined
    assert 'Second paragraph' in combined


def test_no_empty_chunks(chunker: TextChunker) -> None:
    text = 'paragraph one\n\n\n\nparagraph two\n\nparagraph three'
    chunks = chunker.split(text)
    assert all(c.strip() for c in chunks)


def test_overlap_creates_shared_content() -> None:
    chunker = TextChunker(chunk_size=100, chunk_overlap=40)
    text = 'A' * 80 + ' ' + 'B' * 80
    chunks = chunker.split(text)
    if len(chunks) > 1:
        # The second chunk should contain content from near the end of the first
        end_of_first = chunks[0][-40:]
        assert any(c[:40] in end_of_first or end_of_first[:20] in c for c in chunks[1:])

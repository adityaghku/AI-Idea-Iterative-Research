from utils.embeddings import cosine_similarity, idea_to_text, text_to_embedding


def test_identical_idea_embeddings_are_duplicate_level_similar():
    text = idea_to_text("A", "B", "C", "D")
    e1 = text_to_embedding(text)
    e2 = text_to_embedding(text)
    assert cosine_similarity(e1, e2) >= 0.95


def test_different_idea_embeddings_are_not_highly_similar():
    a = text_to_embedding(
        idea_to_text(
            "Dog walking app",
            "Users need walkers",
            "Pet owners",
            "Book walkers near me",
        )
    )
    b = text_to_embedding(
        idea_to_text(
            "Invoice OCR app",
            "Bookkeepers process receipts",
            "SMB finance teams",
            "Extract line items to accounting systems",
        )
    )
    assert cosine_similarity(a, b) < 0.95

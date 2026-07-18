

import sentence_transformers

from app.data.postgres import get_connection, ensure_embedding_column

MODEL_NAME = "intfloat/multilingual-e5-small"
BATCH_SIZE = 32


def main():
    ensure_embedding_column()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, description FROM beer WHERE embedding IS NULL")
    rows = cursor.fetchall()
    cursor.close()

    total = len(rows)
    print(f"{total} beers missing an embedding")
    if total == 0:
        conn.close()
        return

    # Beers with no (or blank) description just stay NULL — nothing to embed.
    to_embed = [(id_, desc) for id_, desc in rows if desc and desc.strip()]
    empty_ids = [id_ for id_, desc in rows if not (desc and desc.strip())]
    print(f"{len(to_embed)} have a description to embed, {len(empty_ids)} are empty")

    model = None
    cursor = conn.cursor()

    for start in range(0, len(to_embed), BATCH_SIZE):
        batch = to_embed[start : start + BATCH_SIZE]
        if model is None:
            print(f"Loading {MODEL_NAME}...")
            model = sentence_transformers.SentenceTransformer(MODEL_NAME)

        texts = [f"passage: {desc}" for _, desc in batch]
        embeddings = model.encode(texts, normalize_embeddings=True)

        for (id_, _), embedding in zip(batch, embeddings):
            cursor.execute(
                "UPDATE beer SET embedding = %s WHERE id = %s",
                (embedding.tolist(), id_),
            )
        conn.commit()
        print(f"{min(start + BATCH_SIZE, len(to_embed))}/{len(to_embed)} embedded")

    cursor.close()
    conn.close()
    print("Done")


if __name__ == "__main__":
    main()

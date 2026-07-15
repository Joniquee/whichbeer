from app.data.postgres import get_names, get_embedding
import numpy as np

# Embeddings are precomputed offline by app/data/compute_embeddings.py and
# read straight from Postgres here — no sentence-transformers/PyTorch model
# loaded in the request path, which is what was OOM-killing the app on
# memory-constrained hosts (e.g. Railway).

def sigmoid(x):
    return 1 / (1 + np.exp(-5 * x))



def similarity(drink, user_favs):
    return np.dot(user_favs, drink)

def get_user_embeddings(*args) -> list:
    user_favs = []
    names = get_names()
    for name in args:
        if name in names:
            embedding = get_embedding(name)
            if embedding:
                user_favs.append(embedding)

    return user_favs

def get_drink_embedding(drink_name):
    embedding = get_embedding(drink_name)
    return embedding if embedding else []

def get_similarities(*args, drink_name):
    drink_embedding = get_drink_embedding(drink_name)
    user_embeddings = get_user_embeddings(*args)
    if  len(user_embeddings) == 0 or len(drink_embedding) == 0:
        return []

    similarities = [similarity(drink_embedding, user_emb) for user_emb in user_embeddings]
    return similarities


if __name__ == "__main__":
    embeds = get_user_embeddings('Тройная ИПА с хмелями цитра мозаика амарилло', "House of Deamon's: Specimen No. 1")
    print(embeds)

    drink_embedding = get_drink_embedding("House of Deamon's: Specimen No. 1")


    sims = get_similarities(drink_embedding, embeds)
    probs = [sigmoid(sim) for sim in sims]
    print(probs)

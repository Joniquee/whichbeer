from app.data.postgres import get_names, get_description
import numpy as np
import sentence_transformers

# Loaded lazily on first use instead of at import time: this module is
# imported by main.py, so eager-loading here would download/load the
# ~1GB model before uvicorn even binds to the port, causing boot-time
# timeouts/OOM kills on memory-constrained hosts (e.g. Railway).
_st = None

def _get_model():
    global _st
    if _st is None:
        _st = sentence_transformers.SentenceTransformer('intfloat/multilingual-e5-base')
    return _st

def sigmoid(x):
    return 1 / (1 + np.exp(-5 * x))



def similarity(drink, user_favs):
    return np.dot(user_favs, drink)

def get_user_embeddings(*args) -> list:
    user_favs = []
    names = get_names()
    for name in args:
        if name in names:
            desc = get_description(name)
            if desc:
                user_favs.append(f"passage: {desc}")
    
    if not user_favs:
        return []
    
    user_embeddings = _get_model().encode(user_favs, normalize_embeddings=True)
    return user_embeddings

def get_drink_embedding(drink_name):
    desc = get_description(drink_name)
    if not desc:
        return []
    drink_embedding = _get_model().encode(f"query: {desc}", normalize_embeddings=True)
    return drink_embedding

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
    
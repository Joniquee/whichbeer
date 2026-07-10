from app.data.data import get_row, get_names
from app.data.scrape_untappd_descriptions import parse_beer_by_name
import numpy as np
import pandas as pd
import math
import requests
from app.main.descriptions_matching import get_similarities

session = requests.Session()
WEIGHT_PARAMS= 0.5
WEIGHT_DESCRIPTIONS = 0.5

def probability(sim):
    prob = 1 - sim / 100
    if prob < 0:
        prob = 0
    if prob > 1:
        prob = 1
    return prob

def final_probability(similarity_nondesc, similarities_desc):
    prob_nondesc = probability(similarity_nondesc)
    prob_desc = sum(similarities_desc) / len(similarities_desc) if len(similarities_desc) > 0 else 0
    if prob_desc == 0:
        final_prob = prob_nondesc
        return final_prob * 100
    final_prob = WEIGHT_PARAMS * prob_nondesc + WEIGHT_DESCRIPTIONS * prob_desc
    return final_prob *100



def sigmoid(x):
    return 1 / (1 + np.exp(-5 * x))

def get_weight_vector(*args, decay=1.) -> list:
    length = len(args)
    raw = [(length - i) ** decay for i in range(length)]
    total = sum(raw)
    return [w / total for w in raw]

def similarity_euclidean(drink_vector, user_vector) -> float:
    sim = math.dist(drink_vector, user_vector)
    return sim


def get_user_nondesc_vector(*args) -> list:
    user_favs = []

    names = get_names()
    weights = get_weight_vector(*args)
    user_df = pd.DataFrame(None, columns=['id', 'brewery_name', 'beer_name', 'beer_style', 'abv', 'ibu', 'description'])

    for i,name in enumerate(args):
        if name in names:
            user_favs.append(name)
            concat_df = pd.DataFrame([get_row(name)], columns=user_df.columns)
            #print(concat_df)
            user_df = pd.concat([user_df, concat_df], axis=0)
    
    user_df = user_df.drop(columns=['beer_name', 'brewery_name', 'id', 'beer_style', 'description'])
    for col in user_df.columns:
        values = user_df[col].values
        weighted_mean = sum(v * w for v, w in zip(values, weights))
        user_df[col] = weighted_mean
    #print(user_df)
    return user_df.iloc[0].tolist()


if __name__ == '__main__':
    drink_name = "House of Deamon's: Specimen No. 1"
    drink_vector = get_row(drink_name)[4:6]
    print(drink_vector)
    user_vector = get_user_nondesc_vector('Daily Horror', 'Mexican Chocolate Pie With Chipotle And Rum')
    print(user_vector)
    similarities_nondesc = similarity_euclidean(drink_vector, user_vector)
    porbabilities_nondesc = probability(similarities_nondesc)
    similarities_desc = get_similarities('Daily Horror', 'Mexican Chocolate Pie With Chipotle And Rum', drink_name=drink_name)
    final_prob = final_probability(similarities_nondesc, similarities_desc)
    print(f"similarities_nondesc: {similarities_nondesc}")
    print(f"porbabilities_nondesc: {porbabilities_nondesc}")
    print(f"similarities_desc: {similarities_desc}")
    print(f"final_prob: {final_prob}")
    print(parse_beer_by_name(session, drink_name))
    


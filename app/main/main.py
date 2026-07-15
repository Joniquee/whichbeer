from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from app.data.scrape_untappd_descriptions import parse_beers_by_name
#from app.data.data import get_row, get_description
from app.data.postgres import get_row, get_description, get_connection
from app.main.system import get_user_nondesc_vector, similarity_euclidean, probability, final_probability, get_similarities
import pydantic
#"brewery_name", "beer_name", "beer_style", "abv", "ibu", "description"
from fastapi.staticfiles import StaticFiles

class Beer(pydantic.BaseModel):
    brewery: str
    name:str
    style: str
    abv: float
    ibu: float
    description: str

class ProbabilityRequest(pydantic.BaseModel):
    beer_name: str
    comparisons: list[str]

session = requests.Session()
app = FastAPI()

# the frontend is served from a different origin (static file server on a
# different port), so the browser needs this to allow the fetch() calls.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/search_beers")
async def search_beers(beer_name: str):
    hits = parse_beers_by_name(session, beer_name)
    hits.sort(key=lambda x: x.get('popularity'), reverse=True)
    return {"beers": hits}

@app.get("/api/beer_description")
async def beer_description(beer_name: str):
    return {"description": get_description(beer_name)}

@app.post("/api/add_beer")
async def add_beer(beer: Beer):
    beer_data = {
        "brewery_name": beer.brewery,
        "beer_name": beer.name,
        "beer_style": beer.style,
        "abv": beer.abv,
        "ibu": beer.ibu,
        "description": beer.description
    }
    from app.data.data import add_beer, is_beer_in_db

    if is_beer_in_db(beer_data["beer_name"]):
        return {"message": "Beer already exists"}

    add_beer(beer_data)
    return {"message": "Beer added successfully"}

@app.post("/api/probability")
async def get_probability(request: ProbabilityRequest):
    beer_name = request.beer_name
    comparisons = request.comparisons
    drink_vector = get_row(beer_name)[4:6]
    user_vector = get_user_nondesc_vector(*comparisons)
    similarities_nondesc = similarity_euclidean(drink_vector, user_vector)
    similarities_desc = get_similarities(*comparisons, drink_name=beer_name)
    final_prob = final_probability(similarities_nondesc, similarities_desc)
    return {"probability": float(final_prob)}

app.mount("/", StaticFiles(directory="frontend", html=True), name="static")

"""
Adds an untappd beer description column to app/data/beer_updated-2.csv.

For each unique (brewery_name, beer_name) pair the script:
  1. Queries Untappd's public Algolia search index (the same search-only key
     the untappd.com search page ships to every visitor's browser) to find
     the matching beer's id/slug.
  2. Fetches the beer's untappd.com page and extracts the full description
     text (the "beer-descrption-read-less" block).

Results are cached to a checkpoint file keyed by (brewery_name, beer_name)
so the run can be interrupted and resumed without re-doing work.
"""

import argparse
import difflib
import json
import os
import re
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests

ALGOLIA_APP_ID = "9WBO4RQ3HO"
ALGOLIA_SEARCH_KEY = "1d347324d67ec472bb7132c66aead485"
ALGOLIA_URL = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/beer/query"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

# untappd.com sits behind Cloudflare, which fingerprints the TLS handshake
# and blocks plain `requests`/urllib3 with a JS challenge even when the
# User-Agent header claims to be a browser. curl_cffi impersonates a real
# Chrome TLS fingerprint, which gets through.
_PAGE_SESSION = curl_requests.Session(impersonate="chrome124")

MATCH_THRESHOLD = 0.6


def normalize(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a, b):
    return difflib.SequenceMatcher(None, normalize(a), normalize(b)).ratio()


HIGH_CONFIDENCE = 0.85


def _algolia_query(session, query, hits_per_page=10):
    body = {"query": query, "hitsPerPage": hits_per_page}
    resp = session.post(
        ALGOLIA_URL,
        headers={
            "X-Algolia-API-Key": ALGOLIA_SEARCH_KEY,
            "X-Algolia-Application-Id": ALGOLIA_APP_ID,
            "Content-Type": "application/json",
        },
        data=json.dumps(body),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json().get("hits", [])


def _score_hit(hit, brewery_name, beer_name):
    brewery_score = similarity(brewery_name, hit.get("brewery_name", ""))
    beer_score = similarity(beer_name, hit.get("beer_name", ""))
    return 0.4 * brewery_score + 0.6 * beer_score


def search_beer(session, brewery_name, beer_name):
    # Untappd's Algolia index requires (most) query words to be present, so
    # a combined "brewery + beer" query can return zero hits when the
    # brewery name is punctuated/abbreviated differently on Untappd (e.g.
    # "B.A.D. BREWERY" vs "BAD Brew"). Try the most specific query first and
    # fall back to broader ones, keeping whichever candidate scores best.
    queries = [beer_name, f"{brewery_name} {beer_name}", brewery_name]

    best_hit, best_score = None, 0.0
    for query in queries:
        hits = _algolia_query(session, query)
        for hit in hits:
            score = _score_hit(hit, brewery_name, beer_name)
            if score > best_score:
                best_hit, best_score = hit, score
        if best_score >= HIGH_CONFIDENCE:
            break

    if best_hit is not None and best_score >= MATCH_THRESHOLD:
        return best_hit, best_score
    return None, best_score


def extract_description(html):
    soup = BeautifulSoup(html, "html.parser")
    desc_div = soup.find("div", class_="beer-descrption-read-less")
    if desc_div is None:
        desc_div = soup.find("div", class_="beer-descrption-read-more")
    if desc_div is None:
        return None

    for link in desc_div.find_all("a"):
        link.decompose()

    for br in desc_div.find_all("br"):
        br.replace_with("\n")

    text = desc_div.get_text()
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() or None


def fetch_description(bid):
    # /beer/{bid} redirects to the canonical /b/{slug}/{bid} page; some
    # Algolia hits are missing beer_slug, so bid alone is the reliable key.
    url = f"https://untappd.com/beer/{bid}"
    resp = _PAGE_SESSION.get(url, timeout=15)
    if resp.status_code != 200:
        return None
    return extract_description(resp.text)


def parse_beer_by_name(session, beer_name, hits_per_page=20):
    """Look up a beer by name alone and return a CSV-shaped record for the
    most popular matching result on the Untappd search page."""
    hits = _algolia_query(session, beer_name, hits_per_page)
    if not hits:
        return None

    best_hit = max(hits, key=lambda h: h.get("popularity") or 0)
    description = fetch_description(best_hit["bid"])

    return {
        "brewery_name": best_hit.get("brewery_name"),
        "beer_name": best_hit.get("beer_name"),
        "beer_style": best_hit.get("type_name"),
        "abv": best_hit.get("beer_abv"),
        "ibu": best_hit.get("beer_ibu"),
        "description": description,
    }

def parse_beers_by_name(session, beer_name, hits_per_page=20):
    """Look up a beer by name alone and return a CSV-shaped record for the
    most popular matching result on the Untappd search page."""
    hits = _algolia_query(session, beer_name, hits_per_page)
    if not hits:
        return None

    return hits


def load_checkpoint(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_checkpoint(path, data):
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp_path, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input", default="app/data/beer_updated-2.csv",
    )
    parser.add_argument(
        "--output", default="app/data/temp.csv",
    )
    parser.add_argument(
        "--checkpoint", default="app/data/description_checkpoint.json",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Only process the first N unique beers (for testing).",
    )
    parser.add_argument(
        "--delay", type=float, default=0.5,
        help="Seconds to sleep between beers to stay polite to untappd.com.",
    )
    parser.add_argument(
        "--save-every", type=int, default=25,
        help="How many newly-processed beers between checkpoint saves.",
    )
    parser.add_argument(
        "--beer-name",
        help=(
            "Skip the bulk CSV run and look up a single beer by name, "
            "taking the most popular match on the search page. Prints the "
            "result (brewery, name, style, abv, ibu, description); pass "
            "--output to also append it as a row to that CSV."
        ),
    )
    args = parser.parse_args()

    if args.beer_name:
        session = requests.Session()
        record = parse_beer_by_name(session, args.beer_name)
        if record is None:
            print(f"No results for {args.beer_name!r}")
            return

        for field in ("brewery_name", "beer_name", "beer_style", "abv", "ibu", "description"):
            print(f"{field}: {record[field]}")

        if args.output:
            columns = ["brewery_name", "beer_name", "beer_style", "abv", "ibu", "description"]
            row_df = pd.DataFrame([record], columns=columns)
            if os.path.exists(args.output):
                existing = pd.read_csv(args.output, index_col=0)
                next_index = existing.index.max() + 1 if len(existing) else 0
                row_df.index = [next_index]
                row_df = pd.concat([existing, row_df])
            row_df.to_csv(args.output)
            print(f"Appended to {args.output}")
        return

    args.output = args.output or "app/data/beer_with_description.csv"

    df = pd.read_csv(args.input, index_col=0)
    unique_beers = df[["brewery_name", "beer_name"]].drop_duplicates(
        subset=["brewery_name", "beer_name"]
    )
    if args.limit:
        unique_beers = unique_beers.head(args.limit)

    cache = load_checkpoint(args.checkpoint)
    session = requests.Session()

    processed_since_save = 0
    total = len(unique_beers)
    interrupted = False
    try:
        for i, (_, row) in enumerate(unique_beers.iterrows(), start=1):
            key = f"{row['brewery_name']}␟{row['beer_name']}"
            if key in cache:
                continue

            try:
                hit, score = search_beer(session, row["brewery_name"], row["beer_name"])
                description = None
                if hit is not None:
                    description = fetch_description(hit["bid"])
                cache[key] = {
                    "description": description,
                    "match_score": round(score, 3),
                    "bid": hit["bid"] if hit else None,
                }
            except (requests.RequestException, curl_requests.exceptions.RequestException) as exc:
                # Transient network error: don't cache, so a resumed run retries it.
                print(f"[{i}/{total}] ERROR {row['brewery_name']} - {row['beer_name']}: {exc}")
                time.sleep(args.delay)
                continue

            status = "OK" if cache[key]["description"] else "no-match"
            print(f"[{i}/{total}] {status}: {row['brewery_name']} - {row['beer_name']}")

            processed_since_save += 1
            if processed_since_save >= args.save_every:
                save_checkpoint(args.checkpoint, cache)
                processed_since_save = 0

            time.sleep(args.delay)
    except KeyboardInterrupt:
        # curl_cffi blocks inside a C call during a request, so Ctrl+C can
        # take a moment (up to the request timeout) to land here. Once it
        # does, save what we have instead of losing the in-progress batch.
        interrupted = True
        print("\nInterrupted, saving progress...")

    save_checkpoint(args.checkpoint, cache)

    def lookup(row):
        key = f"{row['brewery_name']}␟{row['beer_name']}"
        entry = cache.get(key)
        return entry["description"] if entry else None

    df["description"] = df.apply(lookup, axis=1)
    df.to_csv(args.output)
    print(f"Wrote {args.output}")
    matched = df["description"].notna().sum()
    print(f"Matched descriptions: {matched}/{len(df)}")
    if interrupted:
        print("Run the same command again to resume from the checkpoint.")


if __name__ == "__main__":
    main()

from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
import re
import json

app = Flask(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9"
}

TIMEOUT = 20


def get_page(url):
    try:
        r = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        r.raise_for_status()
        return r.text

    except Exception as e:
        print("Fetch error:", url, e)
        return None


def clean_text(value):
    if not value:
        return ""

    value = BeautifulSoup(str(value), "html.parser").get_text(" ", strip=True)

    return re.sub(r"\s+", " ", value).strip()


def absolute_url(base, link):
    if not link:
        return ""

    return urljoin(base, link)


def make_item(
    title="",
    description="",
    prize="",
    category="",
    deadline="",
    eligibility="",
    link="",
    source=""
):
    return {
        "title": clean_text(title),
        "description": clean_text(description),
        "prize": clean_text(prize),
        "category": clean_text(category),
        "deadline": clean_text(deadline),
        "eligibility": clean_text(eligibility),
        "link": link,
        "source": source
    }


# ---------------------------------------------------------
# Generic JSON-LD extractor
# ---------------------------------------------------------

def extract_jsonld_items(html, source, base_url):
    items = []

    if not html:
        return items

    soup = BeautifulSoup(html, "html.parser")

    scripts = soup.find_all(
        "script",
        attrs={"type": "application/ld+json"}
    )

    for script in scripts:

        try:
            data = json.loads(script.string or script.get_text())
        except Exception:
            continue

        if isinstance(data, dict):
            data = [data]

        if not isinstance(data, list):
            continue

        for obj in data:

            if not isinstance(obj, dict):
                continue

            title = (
                obj.get("name")
                or obj.get("headline")
                or ""
            )

            description = obj.get("description", "")

            link = (
                obj.get("url")
                or obj.get("@id")
                or ""
            )

            link = absolute_url(base_url, link)

            if title or description or link:

                items.append(
                    make_item(
                        title=title,
                        description=description,
                        link=link,
                        source=source
                    )
                )

    return items


# ---------------------------------------------------------
# OpenGraph fallback
# ---------------------------------------------------------

def extract_meta(html, source, url):
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")

    title = ""

    og_title = soup.find(
        "meta",
        property="og:title"
    )

    if og_title:
        title = og_title.get("content", "")

    if not title:
        if soup.title:
            title = soup.title.get_text(strip=True)

    description = ""

    og_description = soup.find(
        "meta",
        property="og:description"
    )

    if og_description:
        description = og_description.get("content", "")

    if not description:
        meta_description = soup.find(
            "meta",
            attrs={"name": "description"}
        )

        if meta_description:
            description = meta_description.get(
                "content",
                ""
            )

    return [
        make_item(
            title=title,
            description=description,
            link=url,
            source=source
        )
    ]


# ---------------------------------------------------------
# UNSTOP
# ---------------------------------------------------------

def fetch_unstop():

    source = "Unstop"

    url = "https://unstop.com/hackathons"

    html = get_page(url)

    if not html:
        return []

    items = extract_jsonld_items(
        html,
        source,
        url
    )

    if items:
        return items

    return extract_meta(
        html,
        source,
        url
    )


# ---------------------------------------------------------
# DEVFOLIO
# ---------------------------------------------------------

def fetch_devfolio():

    source = "Devfolio"

    url = "https://devfolio.co/hackathons"

    html = get_page(url)

    if not html:
        return []

    items = extract_jsonld_items(
        html,
        source,
        url
    )

    if items:
        return items

    return extract_meta(
        html,
        source,
        url
    )


# ---------------------------------------------------------
# HACKEREARTH
# ---------------------------------------------------------

def fetch_hackerearth():

    source = "HackerEarth"

    url = "https://www.hackerearth.com/challenges/"

    html = get_page(url)

    if not html:
        return []

    items = extract_jsonld_items(
        html,
        source,
        url
    )

    if items:
        return items

    return extract_meta(
        html,
        source,
        url
    )


# ---------------------------------------------------------
# HACK2SKILL
# ---------------------------------------------------------

def fetch_hack2skill():

    source = "Hack2Skill"

    url = "https://hack2skill.com/"

    html = get_page(url)

    if not html:
        return []

    items = extract_jsonld_items(
        html,
        source,
        url
    )

    if items:
        return items

    return extract_meta(
        html,
        source,
        url
    )


# ---------------------------------------------------------
# DEVPOST
# ---------------------------------------------------------

def fetch_devpost():

    source = "Devpost"

    url = "https://devpost.com/hackathons"

    html = get_page(url)

    if not html:
        return []

    items = extract_jsonld_items(
        html,
        source,
        url
    )

    if items:
        return items

    return extract_meta(
        html,
        source,
        url
    )


# ---------------------------------------------------------
# MLH
# ---------------------------------------------------------

def fetch_mlh():

    source = "MLH"

    url = "https://mlh.io/seasons/2026/events"

    html = get_page(url)

    if not html:
        return []

    items = extract_jsonld_items(
        html,
        source,
        url
    )

    if items:
        return items

    return extract_meta(
        html,
        source,
        url
    )


# ---------------------------------------------------------
# KAGGLE
# ---------------------------------------------------------

def fetch_kaggle():

    source = "Kaggle"

    url = "https://www.kaggle.com/competitions"

    html = get_page(url)

    if not html:
        return []

    items = extract_jsonld_items(
        html,
        source,
        url
    )

    if items:
        return items

    return extract_meta(
        html,
        source,
        url
    )


# ---------------------------------------------------------
# DORAHACKS
# ---------------------------------------------------------

def fetch_dorahacks():

    source = "DoraHacks"

    url = "https://dorahacks.io/hackathon"

    html = get_page(url)

    if not html:
        return []

    items = extract_jsonld_items(
        html,
        source,
        url
    )

    if items:
        return items

    return extract_meta(
        html,
        source,
        url
    )


# ---------------------------------------------------------
# ALL PLATFORMS
# ---------------------------------------------------------

def fetch_all():

    all_items = []

    fetchers = [
        fetch_unstop,
        fetch_devfolio,
        fetch_hackerearth,
        fetch_hack2skill,
        fetch_devpost,
        fetch_mlh,
        fetch_kaggle,
        fetch_dorahacks
    ]

    for fetcher in fetchers:

        try:

            data = fetcher()

            if data:
                all_items.extend(data)

        except Exception as e:

            print(
                "Platform error:",
                fetcher.__name__,
                e
            )

    return all_items


# ---------------------------------------------------------
# API
# ---------------------------------------------------------

@app.route("/")
def home():

    return "Hackathon Python API is working!"


@app.route("/api/test")
def test():

    return jsonify({
        "status": "success",
        "message": "Python API is running on Render"
    })


@app.route("/api/hackathons")
def hackathons():

    data = fetch_all()

    return jsonify(data)


# ---------------------------------------------------------
# START
# ---------------------------------------------------------

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )

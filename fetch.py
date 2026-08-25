from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
import re

app = Flask(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 30

DEVFOLIO_LISTING_URL = "https://devfolio.co/hackathons"


# ---------------------------------------------------------
# REQUEST
# ---------------------------------------------------------

def get_page(url):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT
        )

        response.raise_for_status()

        return response.text

    except Exception as e:

        print("REQUEST ERROR:", url)
        print(e)

        return None


# ---------------------------------------------------------
# CLEAN TEXT
# ---------------------------------------------------------

def clean_text(value):

    if not value:
        return ""

    text = BeautifulSoup(
        str(value),
        "html.parser"
    ).get_text(
        " ",
        strip=True
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ---------------------------------------------------------
# ABSOLUTE URL
# ---------------------------------------------------------

def absolute_url(base_url, link):

    if not link:
        return ""

    return urljoin(
        base_url,
        link
    )


# ---------------------------------------------------------
# EXTRACT PRIZE
# ---------------------------------------------------------

def extract_prize(text):

    if not text:
        return ""

    patterns = [
        r"(?:₹|Rs\.?|INR)\s?[\d,]+(?:\.\d+)?",
        r"\$\s?[\d,]+(?:\.\d+)?",
        r"€\s?[\d,]+(?:\.\d+)?",
        r"£\s?[\d,]+(?:\.\d+)?"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            return clean_text(
                match.group(0)
            )

    return ""


# ---------------------------------------------------------
# EXTRACT DEVFOLIO DETAIL LINKS
# ---------------------------------------------------------

def extract_devfolio_links(html):

    links = []

    if not html:
        return links

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    for anchor in soup.find_all("a", href=True):

        href = anchor.get("href", "").strip()

        if not href:
            continue

        full_url = absolute_url(
            DEVFOLIO_LISTING_URL,
            href
        )

        # Devfolio hackathon detail pages
        if "/hackathons/" not in full_url:
            continue

        # Remove query/hash
        full_url = full_url.split("?")[0]
        full_url = full_url.split("#")[0]

        # Avoid duplicates
        if full_url not in links:
            links.append(full_url)

    return links


# ---------------------------------------------------------
# FIND TITLE
# ---------------------------------------------------------

def extract_title(soup):

    # OpenGraph title
    tag = soup.find(
        "meta",
        property="og:title"
    )

    if tag and tag.get("content"):
        return clean_text(
            tag.get("content")
        )

    # Twitter title
    tag = soup.find(
        "meta",
        attrs={"name": "twitter:title"}
    )

    if tag and tag.get("content"):
        return clean_text(
            tag.get("content")
        )

    # HTML title
    if soup.title:
        title = soup.title.get_text(
            " ",
            strip=True
        )

        title = re.sub(
            r"\s*\|\s*Devfolio.*$",
            "",
            title,
            flags=re.IGNORECASE
        )

        return clean_text(title)

    # H1
    h1 = soup.find("h1")

    if h1:
        return clean_text(
            h1.get_text(" ", strip=True)
        )

    return ""


# ---------------------------------------------------------
# FIND DESCRIPTION
# ---------------------------------------------------------

def extract_description(soup):

    # OpenGraph description
    tag = soup.find(
        "meta",
        property="og:description"
    )

    if tag and tag.get("content"):
        return clean_text(
            tag.get("content")
        )

    # Meta description
    tag = soup.find(
        "meta",
        attrs={"name": "description"}
    )

    if tag and tag.get("content"):
        return clean_text(
            tag.get("content")
        )

    return ""


# ---------------------------------------------------------
# FIND IMAGE
# ---------------------------------------------------------

def extract_image(soup):

    tag = soup.find(
        "meta",
        property="og:image"
    )

    if tag and tag.get("content"):
        return tag.get("content")

    tag = soup.find(
        "meta",
        attrs={"name": "twitter:image"}
    )

    if tag and tag.get("content"):
        return tag.get("content")

    return ""


# ---------------------------------------------------------
# EXTRACT DETAIL PAGE
# ---------------------------------------------------------

def extract_devfolio_detail(url):

    html = get_page(url)

    if not html:
        return None

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    title = extract_title(
        soup
    )

    description = extract_description(
        soup
    )

    image = extract_image(
        soup
    )

    page_text = clean_text(
        soup.get_text(
            " ",
            strip=True
        )
    )

    # -----------------------------------------------------
    # Theme
    # -----------------------------------------------------

    category = ""

    theme_match = re.search(
        r"Theme\s+(.{1,150}?)(?:Image|Online|Offline|Open|Upcoming|Ended|Starts|Apply now|Remind me)",
        page_text,
        re.IGNORECASE
    )

    if theme_match:

        category = clean_text(
            theme_match.group(1)
        )

    # -----------------------------------------------------
    # Mode
    # -----------------------------------------------------

    mode = ""

    if re.search(
        r"\bOnline\b",
        page_text,
        re.IGNORECASE
    ):
        mode = "Online"

    elif re.search(
        r"\bOffline\b",
        page_text,
        re.IGNORECASE
    ):
        mode = "Offline"

    # -----------------------------------------------------
    # Status
    # -----------------------------------------------------

    status = ""

    for value in [
        "Open",
        "Upcoming",
        "Live",
        "Ended"
    ]:

        if re.search(
            r"\b" + re.escape(value) + r"\b",
            page_text,
            re.IGNORECASE
        ):

            status = value
            break

    # -----------------------------------------------------
    # Start / Open Date
    # -----------------------------------------------------

    start_date = ""

    date_match = re.search(
        r"(?:Starts|Opens)\s+"
        r"(\d{1,2}/\d{1,2}/\d{2})",
        page_text,
        re.IGNORECASE
    )

    if date_match:

        start_date = date_match.group(1)

    # -----------------------------------------------------
    # Participants
    # -----------------------------------------------------

    participants = ""

    participant_match = re.search(
        r"\+?([\d,]+)\s+participat",
        page_text,
        re.IGNORECASE
    )

    if participant_match:

        participants = participant_match.group(1)

    # -----------------------------------------------------
    # Prize
    # -----------------------------------------------------

    prize = extract_prize(
        page_text
    )

    # -----------------------------------------------------
    # Return
    # -----------------------------------------------------

    return {
        "title": title,
        "description": description,
        "prize": prize,
        "category": category,
        "deadline": "",
        "eligibility": "",
        "link": url,
        "source": "Devfolio",
        "image": image,
        "mode": mode,
        "status": status,
        "start_date": start_date,
        "participants": participants
    }


# ---------------------------------------------------------
# DEVFOLIO FETCHER
# ---------------------------------------------------------

def fetch_devfolio():

    print(
        "Fetching Devfolio..."
    )

    listing_html = get_page(
        DEVFOLIO_LISTING_URL
    )

    if not listing_html:

        print(
            "Unable to fetch Devfolio listing"
        )

        return []

    links = extract_devfolio_links(
        listing_html
    )

    print(
        "Devfolio links found:",
        len(links)
    )

    results = []

    # Safety limit
    # First 50 current listings
    for index, link in enumerate(
        links[:50]
    ):

        print(
            "Fetching:",
            index + 1,
            link
        )

        try:

            item = extract_devfolio_detail(
                link
            )

            if item and item.get("title"):

                results.append(
                    item
                )

        except Exception as e:

            print(
                "DETAIL ERROR:",
                link,
                e
            )

    return results


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

    data = fetch_devfolio()

    return jsonify(
        data
    )


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

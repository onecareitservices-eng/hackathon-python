```python
from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os
import re

app = Flask(__name__)

# ---------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------

DEVFOLIO_URL = "https://devfolio.co/hackathons"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 30


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

        print("REQUEST ERROR:", url, e)

        return ""


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
# URL
# ---------------------------------------------------------

def absolute_url(base, value):

    if not value:
        return ""

    return urljoin(
        base,
        value
    )


# ---------------------------------------------------------
# FIND IMAGE
# ---------------------------------------------------------

def get_image(card):

    img = card.find("img")

    if not img:
        return ""

    value = (
        img.get("src")
        or img.get("data-src")
        or img.get("data-lazy-src")
        or ""
    )

    return absolute_url(
        DEVFOLIO_URL,
        value
    )


# ---------------------------------------------------------
# FIND THEME
# ---------------------------------------------------------

def get_theme(card):

    text = clean_text(
        card.get_text(
            " ",
            strip=True
        )
    )

    # Devfolio card normally contains:
    #
    # Theme
    # AI
    # Blockchain
    # Hardware
    #
    # We stop when the next known card field begins.

    match = re.search(
        r"\bTheme\b\s+(.*?)(?="
        r"\+\d[\d,]*\s+participat"
        r"|\bOnline\b"
        r"|\bOffline\b"
        r"\bOpen\b"
        r"\bUpcoming\b"
        r"\bEnded\b"
        r"\bLive\b"
        r"\bStarts\b"
        r"\bOpens\b"
        r"$"
        r")",
        text,
        re.IGNORECASE
    )

    if not match:
        return ""

    theme = clean_text(
        match.group(1)
    )

    return theme


# ---------------------------------------------------------
# PARTICIPANTS
# ---------------------------------------------------------

def get_participants(card):

    text = clean_text(
        card.get_text(
            " ",
            strip=True
        )
    )

    match = re.search(
        r"\+?[\d,]+\s+(?:participated|participating)",
        text,
        re.IGNORECASE
    )

    if match:
        return clean_text(
            match.group(0)
        )

    return ""


# ---------------------------------------------------------
# MODE
# ---------------------------------------------------------

def get_mode(card):

    text = clean_text(
        card.get_text(
            " ",
            strip=True
        )
    )

    if re.search(
        r"\bOnline\b",
        text,
        re.IGNORECASE
    ):
        return "Online"

    if re.search(
        r"\bOffline\b",
        text,
        re.IGNORECASE
    ):
        return "Offline"

    return ""


# ---------------------------------------------------------
# STATUS
# ---------------------------------------------------------

def get_status(card):

    text = clean_text(
        card.get_text(
            " ",
            strip=True
        )
    )

    # Check more specific values first.

    if re.search(
        r"\bEnded\b",
        text,
        re.IGNORECASE
    ):
        return "Ended"

    if re.search(
        r"\bUpcoming\b",
        text,
        re.IGNORECASE
    ):
        return "Upcoming"

    if re.search(
        r"\bOpen\b",
        text,
        re.IGNORECASE
    ):
        return "Open"

    if re.search(
        r"\bLive\b",
        text,
        re.IGNORECASE
    ):
        return "Live"

    return ""


# ---------------------------------------------------------
# START / OPEN DATE
# ---------------------------------------------------------

def get_date(card):

    text = clean_text(
        card.get_text(
            " ",
            strip=True
        )
    )

    # Example:
    #
    # Starts 25/09/26
    # Opens 01/09/26

    match = re.search(
        r"\b(?:Starts|Opens)\s+"
        r"(\d{1,2}/\d{1,2}/\d{2,4})",
        text,
        re.IGNORECASE
    )

    if match:
        return match.group(1)

    return ""


# ---------------------------------------------------------
# TITLE
# ---------------------------------------------------------

def get_title(anchor, card):

    title = clean_text(
        anchor.get_text(
            " ",
            strip=True
        )
    )

    if title:
        return title

    heading = card.find(
        [
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6"
        ]
    )

    if heading:

        return clean_text(
            heading.get_text(
                " ",
                strip=True
            )
        )

    return ""


# ---------------------------------------------------------
# FIND CARD
# ---------------------------------------------------------

def find_card(anchor):

    current = anchor

    for _ in range(10):

        if not current.parent:
            break

        current = current.parent

        text = clean_text(
            current.get_text(
                " ",
                strip=True
            )
        )

        # Actual Devfolio card usually contains
        # Hackathon + Theme + mode/status information.

        if (
            re.search(
                r"\bHackathon\b",
                text,
                re.IGNORECASE
            )
            and
            re.search(
                r"\bTheme\b",
                text,
                re.IGNORECASE
            )
            and
            len(text) < 2500
        ):

            return current

    return anchor.parent


# ---------------------------------------------------------
# EXTRACT ACTUAL DEVFOLIO LINKS
# ---------------------------------------------------------

def get_hackathon_links(soup):

    links = []

    blocked = {
        "https://devfolio.co/hackathons",
        "https://devfolio.co/hackathons/open",
        "https://devfolio.co/hackathons/upcoming",
        "https://devfolio.co/hackathons/past",
        "https://devfolio.co/hackathons/applied"
    }

    for anchor in soup.find_all(
        "a",
        href=True
    ):

        href = anchor.get(
            "href",
            ""
        ).strip()

        if not href:
            continue

        full_url = absolute_url(
            DEVFOLIO_URL,
            href
        )

        full_url = full_url.split("?")[0]
        full_url = full_url.split("#")[0]

        # -------------------------------------------------
        # Do not accept Devfolio category pages
        # -------------------------------------------------

        if full_url in blocked:
            continue

        # -------------------------------------------------
        # We need actual hackathon pages.
        #
        # Devfolio hackathon pages normally use
        # subdomains such as:
        #
        # https://something.devfolio.co/
        #
        # -------------------------------------------------

        if not re.match(
            r"^https?://[^/]+\.devfolio\.co/?$",
            full_url,
            re.IGNORECASE
        ):

            continue

        if full_url not in links:

            links.append(
                (
                    anchor,
                    full_url
                )
            )

    return links


# ---------------------------------------------------------
# FETCH DEVFOLIO
# ---------------------------------------------------------

def fetch_devfolio():

    print(
        "Fetching:",
        DEVFOLIO_URL
    )

    html = get_page(
        DEVFOLIO_URL
    )

    if not html:

        return []

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    links = get_hackathon_links(
        soup
    )

    print(
        "Devfolio actual links found:",
        len(links)
    )

    results = []

    seen = set()

    for anchor, link in links:

        if link in seen:
            continue

        seen.add(link)

        card = find_card(
            anchor
        )

        title = get_title(
            anchor,
            card
        )

        if not title:
            continue

        # Do not accidentally include navigation.

        if title.lower() in {
            "open",
            "upcoming",
            "past",
            "applied",
            "hackathons"
        }:
            continue

        category = get_theme(
            card
        )

        participants = get_participants(
            card
        )

        mode = get_mode(
            card
        )

        status = get_status(
            card
        )

        start_date = get_date(
            card
        )

        image = get_image(
            card
        )

        item = {
            "title": title,
            "description": "",
            "prize": "",
            "category": category,
            "deadline": "",
            "eligibility": "",
            "link": link,
            "source": "Devfolio",
            "image": image,
            "mode": mode,
            "status": status,
            "start_date": start_date,
            "participants": participants
        }

        results.append(
            item
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
```

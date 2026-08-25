from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
import re
import json
import time

app = Flask(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

TIMEOUT = 20

CACHE = {
    "time": 0,
    "data": []
}

CACHE_SECONDS = 300


# =========================================================
# COMMON
# =========================================================

def get_page(url):

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
            allow_redirects=True
        )

        response.raise_for_status()

        return response.text

    except Exception as e:

        print("FETCH ERROR:", url, e)

        return ""


def clean_text(value):

    if value is None:
        return ""

    text = BeautifulSoup(
        str(value),
        "html.parser"
    ).get_text(
        " ",
        strip=True
    )

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def absolute_url(base, value):

    if not value:
        return ""

    return urljoin(
        base,
        value
    )


def make_item(
    title="",
    description="",
    prize="",
    category="",
    deadline="",
    eligibility="",
    link="",
    source="",
    image="",
    mode="",
    participants="",
    status="",
    start_date=""
):

    return {
        "title": clean_text(title),
        "description": clean_text(description),
        "prize": clean_text(prize),
        "category": clean_text(category),
        "deadline": clean_text(deadline),
        "eligibility": clean_text(eligibility),
        "link": link,
        "source": source,
        "image": image,
        "mode": clean_text(mode),
        "participants": clean_text(participants),
        "status": clean_text(status),
        "start_date": clean_text(start_date)
    }


# =========================================================
# IMAGE
# =========================================================

def clean_image(value):

    if not value:
        return ""

    value = value.strip()

    if value.startswith("data:image"):
        return ""

    if "/users/" in value.lower():
        return ""

    if "avatar" in value.lower():
        return ""

    return value


def get_card_image(card, base_url):

    if not card:
        return ""

    candidates = []

    # IMG
    for img in card.find_all("img"):

        for attr in [
            "src",
            "data-src",
            "data-lazy-src",
            "data-original",
            "data-image"
        ]:

            value = img.get(attr)

            if value:
                candidates.append(value)

        srcset = img.get("srcset")

        if srcset:

            for part in srcset.split(","):

                value = (
                    part.strip()
                    .split(" ")[0]
                )

                if value:
                    candidates.append(value)

    # SOURCE
    for source in card.find_all("source"):

        for attr in [
            "srcset",
            "data-srcset"
        ]:

            value = source.get(attr)

            if value:

                for part in value.split(","):

                    image = (
                        part.strip()
                        .split(" ")[0]
                    )

                    if image:
                        candidates.append(image)

    # Prefer actual hackathon/competition assets
    for value in candidates:

        value = clean_image(value)

        if not value:
            continue

        low = value.lower()

        if (
            "/hackathons/" in low
            or "/hackathon/" in low
            or "/cover/" in low
            or "cover" in low
            or "competition" in low
        ):

            return absolute_url(
                base_url,
                value
            )

    # Any non-avatar image
    for value in candidates:

        value = clean_image(value)

        if value:

            return absolute_url(
                base_url,
                value
            )

    return ""


# =========================================================
# JSON-LD
# =========================================================

def extract_jsonld(
    html,
    source,
    base_url
):

    results = []

    if not html:
        return results

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    scripts = soup.find_all(
        "script",
        attrs={
            "type": "application/ld+json"
        }
    )

    for script in scripts:

        try:

            raw = (
                script.string
                or script.get_text()
            )

            data = json.loads(raw)

        except Exception:
            continue

        objects = []

        if isinstance(data, dict):

            if isinstance(
                data.get("@graph"),
                list
            ):

                objects.extend(
                    data["@graph"]
                )

            else:

                objects.append(data)

        elif isinstance(data, list):

            objects.extend(data)

        for obj in objects:

            if not isinstance(obj, dict):
                continue

            title = (
                obj.get("name")
                or obj.get("headline")
                or ""
            )

            description = obj.get(
                "description",
                ""
            )

            link = (
                obj.get("url")
                or obj.get("@id")
                or ""
            )

            image = obj.get(
                "image",
                ""
            )

            if isinstance(image, list):

                image = (
                    image[0]
                    if image
                    else ""
                )

            if isinstance(image, dict):

                image = image.get(
                    "url",
                    ""
                )

            if not title:
                continue

            results.append(
                make_item(
                    title=title,
                    description=description,
                    link=absolute_url(
                        base_url,
                        link
                    ),
                    source=source,
                    image=absolute_url(
                        base_url,
                        image
                    )
                )
            )

    return results


# =========================================================
# CARD
# =========================================================

def get_card(anchor):

    # Prefer article
    article = anchor.find_parent("article")

    if article:
        return article

    # Prefer li
    li = anchor.find_parent("li")

    if li:

        text = clean_text(
            li.get_text(
                " ",
                strip=True
            )
        )

        if len(text) > 25:
            return li

    parent = anchor

    for _ in range(8):

        parent = parent.parent

        if not parent:
            break

        text = clean_text(
            parent.get_text(
                " ",
                strip=True
            )
        )

        if (
            len(text) >= 40
            and len(text) <= 3000
            and parent.find("img")
        ):

            return parent

    return anchor.parent


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


def get_mode(text):

    if re.search(
        r"\bOnline\b",
        text,
        re.I
    ):
        return "Online"

    if re.search(
        r"\bVirtual\b",
        text,
        re.I
    ):
        return "Virtual"

    if re.search(
        r"\bOffline\b",
        text,
        re.I
    ):
        return "Offline"

    if re.search(
        r"\bIn[- ]person\b",
        text,
        re.I
    ):
        return "In-person"

    return ""


def get_status(text):

    statuses = [
        "Registration closed",
        "Pre-registration",
        "Upcoming",
        "Ongoing",
        "Live",
        "Open",
        "Ended"
    ]

    for status in statuses:

        if re.search(
            r"\b" + re.escape(status) + r"\b",
            text,
            re.I
        ):

            return status

    return ""


def get_participants(text):

    patterns = [
        r"\+[\d,]+\s+(?:participating|participated)",
        r"[\d,]+\s+participants?",
        r"[\d,]+\s+teams?"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.I
        )

        if match:
            return clean_text(
                match.group(0)
            )

    return ""


def get_prize(text):

    patterns = [

        r"(?:₹|Rs\.?|INR)\s?[\d,]+(?:\.\d+)?",

        r"\$[\d,]+(?:\.\d+)?",

        r"[\d,]+\s*(?:USD|INR)",

        r"(?:Prize Pool|Prize)\s*[:\-]?\s*"
        r"[₹$]?\s?[\d,]+"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.I
        )

        if match:
            return clean_text(
                match.group(0)
            )

    return ""


def get_date(text):

    patterns = [

        r"\d{1,2}/\d{1,2}/\d{2,4}",

        r"\d{1,2}\s+"
        r"[A-Za-z]{3,9}\s+"
        r"\d{4}",

        r"[A-Za-z]{3,9}\s+"
        r"\d{1,2}"
        r"\s*[-–]\s*"
        r"\d{1,2}",

        r"[A-Za-z]{3,9}\s+"
        r"\d{1,2}"
        r"\s*-\s*"
        r"[A-Za-z]{3,9}\s+"
        r"\d{1,2}"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text
        )

        if match:

            return match.group(0)

    return ""


def get_category(text):

    categories = [
        "AI",
        "Artificial Intelligence",
        "Blockchain",
        "Web3",
        "FinTech",
        "Gaming",
        "Design",
        "Hardware",
        "HealthTech",
        "Cybersecurity",
        "Data Science",
        "Machine Learning",
        "Cloud",
        "IoT",
        "Software Development",
        "Future Mobility",
        "Quantum",
        "BioTech"
    ]

    found = []

    for category in categories:

        if re.search(
            r"\b" + re.escape(category) + r"\b",
            text,
            re.I
        ):

            found.append(category)

    return ", ".join(
        dict.fromkeys(found)
    )


# =========================================================
# GENERIC PLATFORM PARSER
# =========================================================

def fetch_platform(
    url,
    source,
    domain_filter
):

    html = get_page(url)

    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    results = []
    seen = set()

    anchors = soup.find_all(
        "a",
        href=True
    )

    for anchor in anchors:

        href = anchor.get(
            "href",
            ""
        )

        if not href:
            continue

        link = absolute_url(
            url,
            href
        )

        # Only same platform
        if domain_filter:

            if not any(
                domain in link
                for domain in domain_filter
            ):
                continue

        card = get_card(
            anchor
        )

        if not card:
            continue

        text = clean_text(
            card.get_text(
                " ",
                strip=True
            )
        )

        if len(text) < 30:
            continue

        title = get_title(
            anchor,
            card
        )

        if not title:
            continue

        # Ignore navigation
        if title.lower() in [
            "login",
            "sign up",
            "register",
            "apply now",
            "learn more",
            "view all",
            "home",
            "hackathons",
            "competitions",
            "challenges"
        ]:
            continue

        image = get_card_image(
            card,
            url
        )

        key = (
            title.lower(),
            link
        )

        if key in seen:
            continue

        seen.add(key)

        results.append(
            make_item(
                title=title,
                description="",
                prize=get_prize(text),
                category=get_category(text),
                deadline="",
                eligibility="",
                link=link,
                source=source,
                image=image,
                mode=get_mode(text),
                participants=get_participants(text),
                status=get_status(text),
                start_date=get_date(text)
            )
        )

    return results


# =========================================================
# UNSTOP
# =========================================================

def fetch_unstop():

    print("Fetching Unstop")

    return fetch_platform(
        "https://unstop.com/hackathons",
        "Unstop",
        [
            "unstop.com"
        ]
    )


# =========================================================
# DEVFOLIO
# =========================================================

def fetch_devfolio():

    print("Fetching Devfolio")

    url = "https://devfolio.co/hackathons"

    html = get_page(url)

    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    results = []
    seen = set()

    for anchor in soup.find_all(
        "a",
        href=True
    ):

        href = anchor.get(
            "href",
            ""
        )

        link = absolute_url(
            url,
            href
        )

        host = urlparse(
            link
        ).netloc.lower()

        # Actual hackathon subdomains
        if not host.endswith(
            ".devfolio.co"
        ):
            continue

        if any(
            x in host
            for x in [
                "guide.",
                "status."
            ]
        ):
            continue

        card = get_card(
            anchor
        )

        if not card:
            continue

        text = clean_text(
            card.get_text(
                " ",
                strip=True
            )
        )

        if len(text) < 30:
            continue

        title = get_title(
            anchor,
            card
        )

        if not title:
            continue

        image = get_card_image(
            card,
            url
        )

        mode = get_mode(
            text
        )

        status = get_status(
            text
        )

        participants = get_participants(
            text
        )

        start_date = ""

        match = re.search(
            r"(?:Starts|Opens)\s+"
            r"(\d{1,2}/\d{1,2}/\d{2,4})",
            text,
            re.I
        )

        if match:
            start_date = match.group(1)

        key = (
            title.lower(),
            link
        )

        if key in seen:
            continue

        seen.add(key)

        results.append(
            make_item(
                title=title,
                description="",
                category=get_category(text),
                link=link,
                source="Devfolio",
                image=image,
                mode=mode,
                participants=participants,
                status=status,
                start_date=start_date
            )
        )

    return results


# =========================================================
# HACKEREARTH
# =========================================================

def fetch_hackerearth():

    print("Fetching HackerEarth")

    return fetch_platform(
        "https://www.hackerearth.com/challenges/",
        "HackerEarth",
        [
            "hackerearth.com"
        ]
    )


# =========================================================
# HACK2SKILL
# =========================================================

def fetch_hack2skill():

    print("Fetching Hack2Skill")

    return fetch_platform(
        "https://hack2skill.com/",
        "Hack2Skill",
        [
            "hack2skill.com"
        ]
    )


# =========================================================
# DEVPOST
# =========================================================

def fetch_devpost():

    print("Fetching Devpost")

    return fetch_platform(
        "https://devpost.com/hackathons",
        "Devpost",
        [
            "devpost.com"
        ]
    )


# =========================================================
# MLH
# =========================================================

def fetch_mlh():

    print("Fetching MLH")

    return fetch_platform(
        "https://mlh.io/seasons/2026/events",
        "MLH",
        [
            "mlh.io"
        ]
    )


# =========================================================
# KAGGLE
# =========================================================

def fetch_kaggle():

    print("Fetching Kaggle")

    return fetch_platform(
        "https://www.kaggle.com/competitions",
        "Kaggle",
        [
            "kaggle.com"
        ]
    )


# =========================================================
# DORAHACKS
# =========================================================

def fetch_dorahacks():

    print("Fetching DoraHacks")

    return fetch_platform(
        "https://dorahacks.io/hackathon",
        "DoraHacks",
        [
            "dorahacks.io"
        ]
    )


# =========================================================
# REMOVE DUPLICATES
# =========================================================

def remove_duplicates(items):

    output = []
    seen = set()

    for item in items:

        title = clean_text(
            item.get(
                "title",
                ""
            )
        )

        link = item.get(
            "link",
            ""
        )

        if not title:
            continue

        key = (
            title.lower(),
            link
        )

        if key in seen:
            continue

        seen.add(key)

        output.append(
            item
        )

    return output


# =========================================================
# ALL PLATFORMS
# =========================================================

def fetch_all():

    global CACHE

    now = time.time()

    if (
        CACHE["data"]
        and
        now - CACHE["time"] < CACHE_SECONDS
    ):

        print("Returning cached data")

        return CACHE["data"]

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

            print(
                fetcher.__name__,
                "FOUND:",
                len(data)
            )

            all_items.extend(
                data
            )

        except Exception as e:

            print(
                "PLATFORM ERROR:",
                fetcher.__name__,
                str(e)
            )

    all_items = remove_duplicates(
        all_items
    )

    CACHE["time"] = now
    CACHE["data"] = all_items

    print(
        "TOTAL:",
        len(all_items)
    )

    return all_items


# =========================================================
# ROUTES
# =========================================================

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

    return jsonify(
        fetch_all()
    )


# =========================================================
# START
# =========================================================

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

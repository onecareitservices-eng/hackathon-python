from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9"
}

TIMEOUT = 15

# Small cache so Render free service is not hit repeatedly
CACHE = {
    "time": 0,
    "data": []
}

CACHE_SECONDS = 300


# =========================================================
# HTTP
# =========================================================

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
        print("FETCH ERROR:", url, str(e))
        return None


# =========================================================
# TEXT
# =========================================================

def clean_text(value):
    if value is None:
        return ""

    value = str(value)

    soup = BeautifulSoup(
        value,
        "html.parser"
    )

    value = soup.get_text(
        " ",
        strip=True
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


# =========================================================
# URL
# =========================================================

def absolute_url(base_url, link):

    if not link:
        return ""

    return urljoin(
        base_url,
        link
    )


# =========================================================
# IMAGE
# =========================================================

def get_image(img, base_url):

    if not img:
        return ""

    attributes = [
        "src",
        "data-src",
        "data-lazy-src",
        "data-original",
        "data-image"
    ]

    for attr in attributes:

        value = img.get(attr)

        if value:

            value = value.strip()

            if value.startswith("data:image"):
                continue

            # Do not use user/avatar images
            if "/users/" in value:
                continue

            if "avatar" in value.lower():
                continue

            return absolute_url(
                base_url,
                value
            )

    # srcset fallback

    srcset = img.get("srcset")

    if srcset:

        parts = srcset.split(",")

        for part in reversed(parts):

            part = part.strip()

            if not part:
                continue

            image_url = part.split(" ")[0]

            if "/users/" in image_url:
                continue

            if "avatar" in image_url.lower():
                continue

            return absolute_url(
                base_url,
                image_url
            )

    return ""


def find_actual_image(card, base_url):

    images = card.find_all("img")

    candidates = []

    for img in images:

        image = get_image(
            img,
            base_url
        )

        if not image:
            continue

        low = image.lower()

        # Ignore profile/avatar images
        if "/users/" in low:
            continue

        if "avatar" in low:
            continue

        if "logo" in low:
            continue

        candidates.append(image)

    if candidates:
        return candidates[0]

    return ""


# =========================================================
# ITEM
# =========================================================

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
# JSON-LD
# =========================================================

def extract_jsonld(html, source, base_url):

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

            raw = script.string

            if not raw:
                raw = script.get_text()

            data = json.loads(raw)

        except Exception:
            continue

        objects = []

        if isinstance(data, dict):

            if "@graph" in data:
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

            link = absolute_url(
                base_url,
                link
            )

            image = absolute_url(
                base_url,
                image
            )

            if title:

                results.append(
                    make_item(
                        title=title,
                        description=description,
                        link=link or base_url,
                        source=source,
                        image=image
                    )
                )

    return results


# =========================================================
# META
# =========================================================

def get_meta(
    soup,
    property_name="",
    name=""
):

    if property_name:

        tag = soup.find(
            "meta",
            attrs={
                "property": property_name
            }
        )

    else:

        tag = soup.find(
            "meta",
            attrs={
                "name": name
            }
        )

    if tag:

        return tag.get(
            "content",
            ""
        )

    return ""


# =========================================================
# CARD TEXT HELPERS
# =========================================================

def card_text(card):

    return clean_text(
        card.get_text(
            " ",
            strip=True
        )
    )


def find_nearest_card(anchor):

    # Try common card elements first

    for tag_name in [
        "article",
        "li"
    ]:

        parent = anchor.find_parent(
            tag_name
        )

        if parent:

            text = card_text(parent)

            if len(text) > 30:

                return parent

    # Generic parent fallback

    parent = anchor

    for _ in range(6):

        parent = parent.parent

        if not parent:
            break

        text = card_text(parent)

        if 40 < len(text) < 2500:

            if parent.find("img"):

                return parent

    return anchor.parent


# =========================================================
# DEVFOLIO
# =========================================================

def fetch_devfolio():

    source = "Devfolio"

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

    # Devfolio hackathon pages normally use
    # *.devfolio.co links

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

        full_link = absolute_url(
            url,
            href
        )

        # Actual hackathon pages
        if ".devfolio.co" not in full_link:
            continue

        if full_link.rstrip("/") == url.rstrip("/"):
            continue

        # Ignore social/external links
        if any(x in full_link.lower() for x in [
            "twitter.com",
            "x.com",
            "discord",
            "instagram.com",
            "facebook.com"
        ]):
            continue

        card = find_nearest_card(
            anchor
        )

        if not card:
            continue

        text = card_text(card)

        # Ignore tiny/invalid cards
        if len(text) < 20:
            continue

        title = clean_text(
            anchor.get_text(
                " ",
                strip=True
            )
        )

        if not title:
            title_tag = card.find(
                [
                    "h1",
                    "h2",
                    "h3",
                    "h4",
                    "h5"
                ]
            )

            if title_tag:
                title = clean_text(
                    title_tag.get_text(
                        " ",
                        strip=True
                    )
                )

        if not title:
            continue

        # Remove generic labels
        if title.lower() in [
            "hackathon",
            "apply now",
            "see projects",
            "remind me"
        ]:
            continue

        image = find_actual_image(
            card,
            url
        )

        mode = ""

        if re.search(
            r"\bOnline\b",
            text,
            re.I
        ):
            mode = "Online"

        elif re.search(
            r"\bOffline\b",
            text,
            re.I
        ):
            mode = "Offline"

        status = ""

        if re.search(
            r"\bUpcoming\b",
            text,
            re.I
        ):
            status = "Upcoming"

        elif re.search(
            r"\bOpen\b",
            text,
            re.I
        ):
            status = "Open"

        elif re.search(
            r"\bEnded\b",
            text,
            re.I
        ):
            status = "Ended"

        if re.search(
            r"\bLive\b",
            text,
            re.I
        ):
            status = "Live"

        participants = ""

        match = re.search(
            r"\+[\d,]+\s+(?:participating|participated)",
            text,
            re.I
        )

        if match:
            participants = clean_text(
                match.group(0)
            )

        start_date = ""

        match = re.search(
            r"(?:Starts|Opens)\s+(\d{1,2}/\d{1,2}/\d{2})",
            text,
            re.I
        )

        if match:

            start_date = match.group(1)

        category_parts = []

        known_themes = [
            "AI",
            "Blockchain",
            "FinTech",
            "Hardware",
            "Design",
            "HealthTech",
            "Future Mobility",
            "Web3",
            "Gaming",
            "No Restrictions"
        ]

        for theme in known_themes:

            if re.search(
                r"\b" + re.escape(theme) + r"\b",
                text,
                re.I
            ):
                category_parts.append(
                    theme
                )

        category = ", ".join(
            dict.fromkeys(
                category_parts
            )
        )

        key = (
            title.lower(),
            full_link
        )

        if key in seen:
            continue

        seen.add(key)

        results.append(
            make_item(
                title=title,
                description="",
                prize="",
                category=category,
                deadline="",
                eligibility="",
                link=full_link,
                source=source,
                image=image,
                mode=mode,
                participants=participants,
                status=status,
                start_date=start_date
            )
        )

    return results


# =========================================================
# GENERIC CARD FETCHER
# =========================================================

def fetch_cards(
    url,
    source,
    allowed_domains=None
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

    # First try JSON-LD
    jsonld = extract_jsonld(
        html,
        source,
        url
    )

    for item in jsonld:

        if item["title"]:

            key = (
                item["title"].lower(),
                item["link"]
            )

            if key not in seen:

                seen.add(key)

                results.append(
                    item
                )

    # Then actual HTML cards

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

        full_link = absolute_url(
            url,
            href
        )

        if allowed_domains:

            if not any(
                domain in full_link
                for domain in allowed_domains
            ):
                continue

        card = find_nearest_card(
            anchor
        )

        if not card:
            continue

        text = card_text(card)

        if len(text) < 35:
            continue

        image = find_actual_image(
            card,
            url
        )

        # Ignore cards without useful content
        if not image and len(text) < 60:
            continue

        title = clean_text(
            anchor.get_text(
                " ",
                strip=True
            )
        )

        if not title:

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

                title = clean_text(
                    heading.get_text(
                        " ",
                        strip=True
                    )
                )

        if not title:
            continue

        # Avoid navigation links
        bad_titles = [
            "login",
            "sign up",
            "register",
            "apply now",
            "learn more",
            "view all",
            "home",
            "hackathons",
            "competitions"
        ]

        if title.lower() in bad_titles:
            continue

        status = ""

        for value in [
            "Open",
            "Upcoming",
            "Live",
            "Ended",
            "Ongoing",
            "Pre-registration",
            "Registration closed"
        ]:

            if re.search(
                r"\b" + re.escape(value) + r"\b",
                text,
                re.I
            ):

                status = value
                break

        mode = ""

        if re.search(
            r"\bOnline\b",
            text,
            re.I
        ):
            mode = "Online"

        elif re.search(
            r"\bVirtual\b",
            text,
            re.I
        ):
            mode = "Virtual"

        elif re.search(
            r"\bOffline\b",
            text,
            re.I
        ):
            mode = "Offline"

        elif re.search(
            r"\bIn[- ]person\b",
            text,
            re.I
        ):
            mode = "In-person"

        participants = ""

        participant_patterns = [
            r"\+[\d,]+\s+(?:participating|participated)",
            r"[\d,]+\s+participants?",
            r"[\d,]+\s+teams?"
        ]

        for pattern in participant_patterns:

            match = re.search(
                pattern,
                text,
                re.I
            )

            if match:

                participants = clean_text(
                    match.group(0)
                )

                break

        prize = ""

        prize_patterns = [
            r"(?:₹|Rs\.?|INR)\s?[\d,]+(?:\s?(?:Lakh|Crore))?",
            r"\$[\d,]+(?:\.\d+)?",
            r"[\d,]+\s*(?:USD|INR)",
            r"(?:Prize Pool|Prize)\s*[:\-]?\s*[₹$]?\s?[\d,]+"
        ]

        for pattern in prize_patterns:

            match = re.search(
                pattern,
                text,
                re.I
            )

            if match:

                prize = clean_text(
                    match.group(0)
                )

                break

        date_patterns = [
            r"\d{1,2}/\d{1,2}/\d{2,4}",
            r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}",
            r"[A-Za-z]{3,9}\s+\d{1,2}\s*[-–]\s*\d{1,2}",
            r"[A-Za-z]{3,9}\s+\d{1,2}\s*-\s*[A-Za-z]{3,9}\s+\d{1,2}"
        ]

        start_date = ""

        for pattern in date_patterns:

            match = re.search(
                pattern,
                text
            )

            if match:

                start_date = match.group(0)

                break

        category = ""

        known_categories = [
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
            "Biohack"
        ]

        found_categories = []

        for category_name in known_categories:

            if re.search(
                r"\b" + re.escape(category_name) + r"\b",
                text,
                re.I
            ):

                found_categories.append(
                    category_name
                )

        category = ", ".join(
            dict.fromkeys(
                found_categories
            )
        )

        key = (
            title.lower(),
            full_link
        )

        if key in seen:
            continue

        seen.add(key)

        results.append(
            make_item(
                title=title,
                description="",
                prize=prize,
                category=category,
                deadline="",
                eligibility="",
                link=full_link,
                source=source,
                image=image,
                mode=mode,
                participants=participants,
                status=status,
                start_date=start_date
            )
        )

    return results


# =========================================================
# UNSTOP
# =========================================================

def fetch_unstop():

    return fetch_cards(
        "https://unstop.com/hackathons?oppstatus=open",
        "Unstop",
        [
            "unstop.com/hackathons"
        ]
    )


# =========================================================
# DEVFOLIO
# =========================================================

def fetch_devfolio_source():

    return fetch_devfolio()


# =========================================================
# HACKEREARTH
# =========================================================

def fetch_hackerearth():

    return fetch_cards(
        "https://www.hackerearth.com/challenges/",
        "HackerEarth",
        [
            "hackerearth.com/challenges"
        ]
    )


# =========================================================
# HACK2SKILL
# =========================================================

def fetch_hack2skill():

    return fetch_cards(
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

    return fetch_cards(
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

    return fetch_cards(
        "https://www.mlh.com/seasons/2026/events",
        "MLH",
        [
            "mlh.io"
        ]
    )


# =========================================================
# KAGGLE
# =========================================================

def fetch_kaggle():

    return fetch_cards(
        "https://www.kaggle.com/competitions?requireHackathons=true",
        "Kaggle",
        [
            "kaggle.com/competitions"
        ]
    )


# =========================================================
# DORAHACKS
# =========================================================

def fetch_dorahacks():

    return fetch_cards(
        "https://dorahacks.io/hackathon",
        "DoraHacks",
        [
            "dorahacks.io/hackathon"
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
            item.get("title", "")
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
# FETCH ALL
# =========================================================

def fetch_all():

    global CACHE

    now = time.time()

    # Cache
    if (
        CACHE["data"]
        and
        now - CACHE["time"] < CACHE_SECONDS
    ):

        return CACHE["data"]

    all_items = []

    fetchers = [
        fetch_unstop,
        fetch_devfolio_source,
        fetch_hackerearth,
        fetch_hack2skill,
        fetch_devpost,
        fetch_mlh,
        fetch_kaggle,
        fetch_dorahacks
    ]

    for fetcher in fetchers:

        try:

            print(
                "Fetching:",
                fetcher.__name__
            )

            data = fetcher()

            if data:

                print(
                    fetcher.__name__,
                    "=>",
                    len(data),
                    "items"
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

    return all_items


# =========================================================
# API
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

    data = fetch_all()

    return jsonify(
        data
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

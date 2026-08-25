from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
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
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 25


# =========================================================
# COMMON FUNCTIONS
# =========================================================

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
        print("REQUEST ERROR:", url, e)
        return ""


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

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def absolute_url(base, value):
    if not value:
        return ""

    return urljoin(base, value)


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
    status="",
    start_date="",
    participants=""
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
        "status": clean_text(status),
        "start_date": clean_text(start_date),
        "participants": clean_text(participants)
    }


def get_meta(soup, prop=None, name=None):
    if prop:
        tag = soup.find(
            "meta",
            attrs={"property": prop}
        )
    else:
        tag = soup.find(
            "meta",
            attrs={"name": name}
        )

    if tag:
        return clean_text(
            tag.get("content", "")
        )

    return ""


def get_basic_page(url, source):
    html = get_page(url)

    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    title = get_meta(
        soup,
        prop="og:title"
    )

    if not title and soup.title:
        title = clean_text(
            soup.title.get_text()
        )

    description = get_meta(
        soup,
        prop="og:description"
    )

    if not description:
        description = get_meta(
            soup,
            name="description"
        )

    image = get_meta(
        soup,
        prop="og:image"
    )

    if image:
        image = absolute_url(
            url,
            image
        )

    return [
        make_item(
            title=title,
            description=description,
            link=url,
            source=source,
            image=image
        )
    ]


# =========================================================
# IMAGE
# =========================================================

def get_card_image(card, base_url):
    candidates = []

    for source in card.find_all("source"):
        for attr in [
            "srcset",
            "data-srcset"
        ]:
            value = source.get(
                attr,
                ""
            )

            if value:
                candidates.append(
                    value.split(",")[0]
                    .strip()
                    .split(" ")[0]
                )

    for img in card.find_all("img"):
        for attr in [
            "src",
            "data-src",
            "data-lazy-src",
            "data-original"
        ]:
            value = img.get(
                attr,
                ""
            )

            if value:
                candidates.append(value)

    # Prefer actual hackathon images.
    for value in candidates:

        if "/users/" in value:
            continue

        if (
            "/hackathons/" in value
            or "/cover/" in value
            or "cover" in value.lower()
        ):
            return absolute_url(
                base_url,
                value
            )

    # Other non-avatar image.
    for value in candidates:

        if "/users/" in value:
            continue

        return absolute_url(
            base_url,
            value
        )

    return ""


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

    blocked_hosts = {
        "guide.devfolio.co",
        "status.devfolio.co"
    }

    for anchor in soup.find_all(
        "a",
        href=True
    ):

        href = anchor.get(
            "href",
            ""
        ).strip()

        full_url = absolute_url(
            url,
            href
        ).split("?")[0].split("#")[0]

        parsed = urlparse(
            full_url
        )

        host = parsed.netloc.lower()

        if not host.endswith(
            ".devfolio.co"
        ):
            continue

        if host in blocked_hosts:
            continue

        if full_url in seen:
            continue

        seen.add(full_url)

        card = anchor

        for _ in range(12):

            if not card.parent:
                break

            card = card.parent

            text = clean_text(
                card.get_text(
                    " ",
                    strip=True
                )
            )

            if (
                "Hackathon" in text
                and "Theme" in text
                and len(text) < 3000
            ):
                break

        text = clean_text(
            card.get_text(
                " ",
                strip=True
            )
        )

        title = clean_text(
            anchor.get_text(
                " ",
                strip=True
            )
        )

        if not title:
            continue

        if title.lower() in {
            "documentation",
            "status",
            "guide"
        }:
            continue

        category = ""

        theme = re.search(
            r"\bTheme\b\s+(.*?)(?="
            r"\+\s*[\d,]+\s+(?:participated|participating)"
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
            re.I
        )

        if theme:
            category = clean_text(
                theme.group(1)
            )

        category = re.sub(
            r"\s*\+\s*[\d,]+\s+"
            r"(?:participated|participating).*?$",
            "",
            category,
            flags=re.I
        ).strip()

        participants = ""

        match = re.search(
            r"\+?\s*[\d,]+\s+"
            r"(?:participated|participating)",
            text,
            re.I
        )

        if match:
            participants = clean_text(
                match.group(0)
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

        for value in [
            "Ended",
            "Upcoming",
            "Open",
            "Live"
        ]:
            if re.search(
                r"\b" + value + r"\b",
                text,
                re.I
            ):
                status = value
                break

        start_date = ""

        date_match = re.search(
            r"\b(?:Starts|Opens)\s+"
            r"(\d{1,2}/\d{1,2}/\d{2,4})",
            text,
            re.I
        )

        if date_match:
            start_date = date_match.group(1)

        image = get_card_image(
            card,
            url
        )

        results.append(
            make_item(
                title=title,
                category=category,
                link=full_url,
                source=source,
                image=image,
                mode=mode,
                status=status,
                start_date=start_date,
                participants=participants
            )
        )

    return results


# =========================================================
# UNSTOP
# =========================================================

def fetch_unstop():
    source = "Unstop"
    url = "https://unstop.com/hackathons"

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

        if "hackathon" not in href.lower():
            continue

        link = absolute_url(
            url,
            href
        )

        if link in seen:
            continue

        seen.add(link)

        card = anchor

        for _ in range(8):
            if not card.parent:
                break

            card = card.parent

            text = clean_text(
                card.get_text(
                    " ",
                    strip=True
                )
            )

            if len(text) < 2000:
                break

        title = clean_text(
            anchor.get_text(
                " ",
                strip=True
            )
        )

        if not title:
            heading = card.find(
                ["h1", "h2", "h3", "h4"]
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

        image = get_card_image(
            card,
            url
        )

        text = clean_text(
            card.get_text(
                " ",
                strip=True
            )
        )

        prize = ""

        prize_match = re.search(
            r"(?:₹|Rs\.?|INR)\s?"
            r"[\d,]+(?:\.\d+)?",
            text,
            re.I
        )

        if prize_match:
            prize = prize_match.group(0)

        results.append(
            make_item(
                title=title,
                description="",
                prize=prize,
                link=link,
                source=source,
                image=image
            )
        )

    return results


# =========================================================
# HACKEREARTH
# =========================================================

def fetch_hackerearth():
    source = "HackerEarth"
    url = "https://www.hackerearth.com/challenges/"

    return get_basic_page(
        url,
        source
    )


# =========================================================
# HACK2SKILL
# =========================================================

def fetch_hack2skill():
    source = "Hack2Skill"
    url = "https://hack2skill.com/"

    return get_basic_page(
        url,
        source
    )


# =========================================================
# DEVPOST
# =========================================================

def fetch_devpost():
    source = "Devpost"
    url = "https://devpost.com/hackathons"

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

        if "/software/" not in href:
            continue

        link = absolute_url(
            url,
            href
        )

        if link in seen:
            continue

        seen.add(link)

        title = clean_text(
            anchor.get_text(
                " ",
                strip=True
            )
        )

        if not title:
            continue

        card = anchor.parent

        image = get_card_image(
            card,
            url
        )

        results.append(
            make_item(
                title=title,
                link=link,
                source=source,
                image=image
            )
        )

    if results:
        return results

    return get_basic_page(
        url,
        source
    )


# =========================================================
# MLH
# =========================================================

def fetch_mlh():
    source = "MLH"
    url = "https://mlh.io/seasons/2026/events"

    html = get_page(url)

    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    results = []

    for card in soup.find_all(
        class_=re.compile(
            r"event|hackathon",
            re.I
        )
    ):

        text = clean_text(
            card.get_text(
                " ",
                strip=True
            )
        )

        link_tag = card.find(
            "a",
            href=True
        )

        if not link_tag:
            continue

        link = absolute_url(
            url,
            link_tag.get(
                "href"
            )
        )

        title = ""

        heading = card.find(
            [
                "h1",
                "h2",
                "h3",
                "h4",
                "h5"
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
            title = clean_text(
                link_tag.get_text(
                    " ",
                    strip=True
                )
            )

        if not title:
            continue

        image = get_card_image(
            card,
            url
        )

        results.append(
            make_item(
                title=title,
                link=link,
                source=source,
                image=image
            )
        )

    if results:
        return results

    return get_basic_page(
        url,
        source
    )


# =========================================================
# KAGGLE
# =========================================================

def fetch_kaggle():
    source = "Kaggle"
    url = "https://www.kaggle.com/competitions"

    return get_basic_page(
        url,
        source
    )


# =========================================================
# DORAHACKS
# =========================================================

def fetch_dorahacks():
    source = "DoraHacks"
    url = "https://dorahacks.io/hackathon"

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

        if (
            "hackathon" not in href.lower()
            and "buidl" not in href.lower()
        ):
            continue

        link = absolute_url(
            url,
            href
        )

        if link in seen:
            continue

        seen.add(link)

        title = clean_text(
            anchor.get_text(
                " ",
                strip=True
            )
        )

        if not title:
            continue

        card = anchor.parent

        image = get_card_image(
            card,
            url
        )

        results.append(
            make_item(
                title=title,
                link=link,
                source=source,
                image=image
            )
        )

    if results:
        return results

    return get_basic_page(
        url,
        source
    )


# =========================================================
# FETCH ALL 8 PLATFORMS
# =========================================================

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

        print(
            "================================"
        )

        print(
            "SOURCE:",
            fetcher.__name__
        )

        try:

            data = fetcher()

            print(
                "RECORDS:",
                len(data)
            )

            all_items.extend(
                data
            )

        except Exception as e:

            print(
                "PLATFORM ERROR:",
                fetcher.__name__,
                e
            )

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

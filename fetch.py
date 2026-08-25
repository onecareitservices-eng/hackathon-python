from flask import Flask, jsonify
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
import re
import json
import html as html_module

app = Flask(__name__)

# =========================================================
# CONFIG
# =========================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

TIMEOUT = 25


# =========================================================
# SESSION
# =========================================================

session = requests.Session()
session.headers.update(HEADERS)


# =========================================================
# COMMON HELPERS
# =========================================================

def get_page(url):
    try:
        response = session.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=True
        )

        response.raise_for_status()

        return response.text

    except Exception as e:
        print("Fetch error:", url, e)
        return None


def clean_text(value):
    if value is None:
        return ""

    try:
        value = html_module.unescape(str(value))
    except Exception:
        value = str(value)

    value = BeautifulSoup(
        value,
        "html.parser"
    ).get_text(
        " ",
        strip=True
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


def absolute_url(base, link):
    if not link:
        return ""

    link = str(link).strip()

    if link.startswith("//"):
        return "https:" + link

    return urljoin(
        base,
        link
    )


def same_domain(link, allowed_domains):
    if not link:
        return False

    try:
        hostname = urlparse(link).netloc.lower()

        return any(
            domain.lower() in hostname
            for domain in allowed_domains
        )

    except Exception:
        return False


# =========================================================
# BLOCKED LINKS
# =========================================================

BLOCKED_WORDS = [
    "privacy policy",
    "privacy",
    "terms of service",
    "terms & conditions",
    "terms and conditions",
    "terms",
    "contact us",
    "contact",
    "about us",
    "about",
    "login",
    "log in",
    "sign up",
    "signup",
    "register",
    "registration",
    "home",
    "careers",
    "career",
    "jobs",
    "job",
    "help",
    "support",
    "cookie policy",
    "cookies",
    "refund policy",
    "copyright",
    "sitemap",
    "press",
    "advertise"
]


EVENT_WORDS = [
    "hackathon",
    "hack",
    "challenge",
    "competition",
    "contest",
    "coding",
    "code",
    "build",
    "innovation",
    "developer",
    "developers",
    "tech",
    "technology",
    "festival",
    "jam",
    "battle",
    "cup",
    "summit"
]


def is_blocked_text(text):
    if not text:
        return True

    value = clean_text(text).lower()

    for word in BLOCKED_WORDS:

        if value == word:
            return True

        if word in value and len(value) < 80:
            return True

    return False


def looks_like_event(text):
    if not text:
        return False

    value = text.lower()

    for word in EVENT_WORDS:

        if word in value:
            return True

    return False


# =========================================================
# IMAGE HELPERS
# =========================================================

def is_bad_image(url):
    if not url:
        return True

    value = url.lower()

    bad_words = [
        "avatar",
        "/users/",
        "/user/",
        "profile",
        "profile-image",
        "profile_image",
        "user-image",
        "user_image",
        "headshot",
        "testimonial",
        "author",
        "person"
    ]

    for word in bad_words:

        if word in value:
            return True

    return False


def image_score(url):
    if not url:
        return -100

    value = url.lower()

    if is_bad_image(value):
        return -100

    score = 0

    preferred = [
        "cover",
        "banner",
        "hackathon",
        "event",
        "competition",
        "challenge",
        "hero",
        "thumbnail",
        "poster",
        "assets"
    ]

    for word in preferred:

        if word in value:
            score += 10

    if value.endswith(
        (
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".gif"
        )
    ):
        score += 3

    return score


def get_card_image(card, base_url):
    if not card:
        return ""

    candidates = []

    # -----------------------------------------------------
    # IMG
    # -----------------------------------------------------

    for img in card.find_all("img"):

        attrs = [
            "src",
            "data-src",
            "data-lazy-src",
            "data-original",
            "data-image",
            "data-image-url",
            "data-lazy"
        ]

        for attr in attrs:

            value = img.get(attr)

            if value:
                candidates.append(value)

        srcset = img.get("srcset")

        if srcset:

            for item in srcset.split(","):

                value = item.strip().split(" ")[0]

                if value:
                    candidates.append(value)

        data_srcset = img.get("data-srcset")

        if data_srcset:

            for item in data_srcset.split(","):

                value = item.strip().split(" ")[0]

                if value:
                    candidates.append(value)

    # -----------------------------------------------------
    # SOURCE
    # -----------------------------------------------------

    for source in card.find_all("source"):

        srcset = (
            source.get("srcset")
            or source.get("data-srcset")
        )

        if srcset:

            for item in srcset.split(","):

                value = item.strip().split(" ")[0]

                if value:
                    candidates.append(value)

    # -----------------------------------------------------
    # META IMAGE
    # -----------------------------------------------------

    for meta in card.find_all(
        "meta"
    ):

        prop = (
            meta.get("property", "")
            or meta.get("name", "")
        ).lower()

        if prop in [
            "og:image",
            "twitter:image",
            "twitter:image:src"
        ]:

            value = meta.get("content")

            if value:
                candidates.append(value)

    # -----------------------------------------------------
    # CLEAN + SCORE
    # -----------------------------------------------------

    valid = []

    for candidate in candidates:

        candidate = absolute_url(
            base_url,
            candidate
        )

        if not candidate:
            continue

        if is_bad_image(candidate):
            continue

        score = image_score(candidate)

        valid.append(
            (
                score,
                candidate
            )
        )

    valid.sort(
        key=lambda x: x[0],
        reverse=True
    )

    if valid:
        return valid[0][1]

    return ""


# =========================================================
# CARD HELPERS
# =========================================================

def get_card(anchor):

    if not anchor:
        return None

    # article
    article = anchor.find_parent("article")

    if article:
        return article

    # list item
    li = anchor.find_parent("li")

    if li:

        text = clean_text(
            li.get_text(
                " ",
                strip=True
            )
        )

        if len(text) >= 30:
            return li

    # div parents
    parent = anchor

    for _ in range(10):

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
            40 <= len(text) <= 5000
            and parent.find("img")
        ):
            return parent

    return anchor.parent


def get_title(anchor, card):

    # -----------------------------------------------------
    # heading inside card
    # -----------------------------------------------------

    if card:

        for tag_name in [
            "h1",
            "h2",
            "h3",
            "h4",
            "h5"
        ]:

            tag = card.find(tag_name)

            if tag:

                title = clean_text(
                    tag.get_text(
                        " ",
                        strip=True
                    )
                )

                if (
                    title
                    and not is_blocked_text(title)
                ):
                    return title

    # -----------------------------------------------------
    # anchor title
    # -----------------------------------------------------

    if anchor:

        for attr in [
            "aria-label",
            "title"
        ]:

            value = anchor.get(attr)

            if value:

                value = clean_text(value)

                if (
                    value
                    and not is_blocked_text(value)
                ):
                    return value

    # -----------------------------------------------------
    # anchor text
    # -----------------------------------------------------

    if anchor:

        value = clean_text(
            anchor.get_text(
                " ",
                strip=True
            )
        )

        if (
            value
            and not is_blocked_text(value)
        ):
            return value

    return ""


# =========================================================
# FIELD EXTRACTORS
# =========================================================

def get_prize(text):
    if not text:
        return ""

    patterns = [
        r"(?:₹|rs\.?|inr|\$|usd)\s?[\d,]+(?:\.\d+)?(?:\s?(?:lakh|crore|k|m))?",
        r"[\d,]+(?:\.\d+)?\s?(?:usd|inr|rs\.?|k|lakh|crore)",
        r"prize\s*(?:pool|amount)?\s*[:\-]?\s*([₹$]?\s?[\d,]+)"
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            value = clean_text(
                match.group(0)
            )

            return value

    return ""


def get_participants(text):
    if not text:
        return ""

    patterns = [
        r"\+?\s*[\d,]+\s*(?:participants?|participating)",
        r"[\d,]+\s*(?:participants?|teams?)"
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


def get_mode(text):
    if not text:
        return ""

    value = text.lower()

    if "offline" in value:
        return "Offline"

    if "online" in value:
        return "Online"

    if "virtual" in value:
        return "Virtual"

    if "hybrid" in value:
        return "Hybrid"

    if "in-person" in value:
        return "In-Person"

    return ""


def get_status(text):
    if not text:
        return ""

    value = text.lower()

    if "upcoming" in value:
        return "Upcoming"

    if "pre-registration" in value:
        return "Pre-registration"

    if "open" in value:
        return "Open"

    if "live" in value:
        return "Live"

    if "ongoing" in value:
        return "Ongoing"

    if "ended" in value:
        return "Ended"

    if "closed" in value:
        return "Closed"

    return ""


def get_category(text):
    if not text:
        return ""

    categories = [
        "AI",
        "Artificial Intelligence",
        "Blockchain",
        "Web3",
        "FinTech",
        "Finance",
        "Cybersecurity",
        "Cyber Security",
        "Cloud",
        "IoT",
        "Hardware",
        "Robotics",
        "Gaming",
        "Design",
        "Healthcare",
        "Education",
        "Future Mobility",
        "Quantum",
        "Crypto",
        "Machine Learning",
        "Data Science",
        "Open Innovation",
        "No Restrictions"
    ]

    found = []

    lower_text = text.lower()

    for category in categories:

        if category.lower() in lower_text:

            if category not in found:
                found.append(category)

    return ", ".join(found)


def get_date(text):
    if not text:
        return ""

    patterns = [

        r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",

        r"\b\d{1,2}-\d{1,2}-\d{2,4}\b",

        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?"
        r"(?:\s*[-–]\s*"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?)?"
        r"(?:,\s*\d{4})?",

        r"\b\d{1,2}\s+"
        r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
        r"[a-z]*\s+\d{4}\b"
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


# =========================================================
# MAKE ITEM
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
        "image": image,
        "link": link,
        "mode": clean_text(mode),
        "participants": clean_text(participants),
        "source": clean_text(source),
        "start_date": clean_text(start_date),
        "status": clean_text(status)
    }


# =========================================================
# JSON-LD
# =========================================================

def extract_jsonld_items(
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

            if "@graph" in data:

                graph = data.get(
                    "@graph"
                )

                if isinstance(graph, list):
                    objects.extend(graph)

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

            description = (
                obj.get("description")
                or ""
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

            if isinstance(image, dict):

                image = (
                    image.get("url")
                    or ""
                )

            if isinstance(image, list):

                image = (
                    image[0]
                    if image
                    else ""
                )

            link = absolute_url(
                base_url,
                link
            )

            image = absolute_url(
                base_url,
                image
            )

            if not title:
                continue

            if is_blocked_text(title):
                continue

            if not looks_like_event(
                title + " " + description
            ):
                continue

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
# META FALLBACK
# =========================================================

def extract_meta(
    html,
    source,
    url
):

    if not html:
        return []

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    title = ""

    og_title = soup.find(
        "meta",
        property="og:title"
    )

    if og_title:
        title = og_title.get(
            "content",
            ""
        )

    if not title and soup.title:
        title = soup.title.get_text(
            " ",
            strip=True
        )

    description = ""

    og_description = soup.find(
        "meta",
        property="og:description"
    )

    if og_description:

        description = og_description.get(
            "content",
            ""
        )

    image = ""

    og_image = soup.find(
        "meta",
        property="og:image"
    )

    if og_image:

        image = absolute_url(
            url,
            og_image.get(
                "content",
                ""
            )
        )

    if (
        title
        and not is_blocked_text(title)
    ):

        return [
            make_item(
                title=title,
                description=description,
                link=url,
                source=source,
                image=image
            )
        ]

    return []


# =========================================================
# GENERIC PLATFORM SCRAPER
# =========================================================

def scrape_platform(
    url,
    source,
    domains
):

    html = get_page(url)

    if not html:
        return []

    results = []

    # JSON-LD
    try:

        results.extend(
            extract_jsonld_items(
                html,
                source,
                url
            )
        )

    except Exception as e:

        print(
            "JSON-LD error:",
            source,
            e
        )

    # -----------------------------------------------------
    # HTML cards
    # -----------------------------------------------------

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # Remove unwanted areas
    for tag in soup.find_all([
        "header",
        "footer",
        "nav",
        "script",
        "style",
        "noscript"
    ]):

        tag.decompose()

    anchors = soup.find_all(
        "a",
        href=True
    )

    for anchor in anchors:

        try:

            href = anchor.get(
                "href",
                ""
            ).strip()

            if not href:
                continue

            link = absolute_url(
                url,
                href
            )

            if not same_domain(
                link,
                domains
            ):
                continue

            card = get_card(
                anchor
            )

            if not card:
                continue

            card_text = clean_text(
                card.get_text(
                    " ",
                    strip=True
                )
            )

            if not card_text:
                continue

            title = get_title(
                anchor,
                card
            )

            if not title:
                continue

            if is_blocked_text(title):
                continue

            if is_blocked_text(
                card_text
            ):
                continue

            # Must resemble event
            if not looks_like_event(
                title + " " + card_text
            ):
                continue

            # Avoid giant page containers
            if len(card_text) > 7000:
                continue

            # Avoid navigation-like titles
            if len(title) < 4:
                continue

            if len(title) > 250:
                continue

            image = get_card_image(
                card,
                url
            )

            mode = get_mode(
                card_text
            )

            status = get_status(
                card_text
            )

            prize = get_prize(
                card_text
            )

            participants = get_participants(
                card_text
            )

            category = get_category(
                card_text
            )

            start_date = get_date(
                card_text
            )

            item = make_item(
                title=title,
                description="",
                prize=prize,
                category=category,
                deadline="",
                eligibility="",
                link=link,
                source=source,
                image=image,
                mode=mode,
                participants=participants,
                status=status,
                start_date=start_date
            )

            results.append(item)

        except Exception as e:

            print(
                "Card error:",
                source,
                e
            )

    return results


# =========================================================
# DEVFOLIO
# =========================================================

def fetch_devfolio():

    source = "Devfolio"

    urls = [
        "https://devfolio.co/hackathons",
        "https://devfolio.co/hackathons/open",
        "https://devfolio.co/hackathons/upcoming"
    ]

    all_items = []

    for url in urls:

        try:

            data = scrape_platform(
                url,
                source,
                [
                    "devfolio.co"
                ]
            )

            all_items.extend(
                data
            )

        except Exception as e:

            print(
                "Devfolio error:",
                e
            )

    return all_items


# =========================================================
# UNSTOP
# =========================================================

def fetch_unstop():

    source = "Unstop"

    urls = [
        "https://unstop.com/hackathons?oppstatus=open",
        "https://unstop.com/hackathons"
    ]

    all_items = []

    for url in urls:

        try:

            data = scrape_platform(
                url,
                source,
                [
                    "unstop.com"
                ]
            )

            all_items.extend(
                data
            )

        except Exception as e:

            print(
                "Unstop error:",
                e
            )

    return all_items


# =========================================================
# HACKEREARTH
# =========================================================

def fetch_hackerearth():

    source = "HackerEarth"

    url = (
        "https://www.hackerearth.com/challenges/"
    )

    return scrape_platform(
        url,
        source,
        [
            "hackerearth.com"
        ]
    )


# =========================================================
# HACK2SKILL
# =========================================================

def fetch_hack2skill():

    source = "Hack2Skill"

    url = "https://hack2skill.com/"

    return scrape_platform(
        url,
        source,
        [
            "hack2skill.com"
        ]
    )


# =========================================================
# DEVPOST
# =========================================================

def fetch_devpost():

    source = "Devpost"

    url = "https://devpost.com/hackathons"

    return scrape_platform(
        url,
        source,
        [
            "devpost.com"
        ]
    )


# =========================================================
# MLH
# =========================================================

def fetch_mlh():

    source = "MLH"

    url = (
        "https://www.mlh.com/seasons/2026/events"
    )

    # Current MLH page
    if get_page(url) is None:

        url = (
            "https://mlh.io/seasons/2026/events"
        )

    return scrape_platform(
        url,
        source,
        [
            "mlh.io",
            "mlh.com"
        ]
    )


# =========================================================
# KAGGLE
# =========================================================

def fetch_kaggle():

    source = "Kaggle"

    url = (
        "https://www.kaggle.com/competitions"
        "?requireHackathons=true"
    )

    return scrape_platform(
        url,
        source,
        [
            "kaggle.com"
        ]
    )


# =========================================================
# DORAHACKS
# =========================================================

def fetch_dorahacks():

    source = "DoraHacks"

    url = (
        "https://dorahacks.io/hackathon"
    )

    return scrape_platform(
        url,
        source,
        [
            "dorahacks.io"
        ]
    )


# =========================================================
# DEDUPLICATION
# =========================================================

def deduplicate(items):

    unique = []

    seen_links = set()
    seen_titles = set()

    for item in items:

        if not isinstance(
            item,
            dict
        ):
            continue

        title = clean_text(
            item.get(
                "title",
                ""
            )
        )

        link = clean_text(
            item.get(
                "link",
                ""
            )
        )

        if not title:
            continue

        if is_blocked_text(
            title
        ):
            continue

        title_key = re.sub(
            r"[^a-z0-9]+",
            "",
            title.lower()
        )

        link_key = link.rstrip(
            "/"
        ).lower()

        if link_key and link_key in seen_links:
            continue

        if title_key and title_key in seen_titles:
            continue

        if link_key:
            seen_links.add(
                link_key
            )

        if title_key:
            seen_titles.add(
                title_key
            )

        unique.append(
            item
        )

    return unique


# =========================================================
# CLEAN FINAL DATA
# =========================================================

def clean_final_items(items):

    cleaned = []

    for item in items:

        title = clean_text(
            item.get(
                "title",
                ""
            )
        )

        if not title:
            continue

        if is_blocked_text(
            title
        ):
            continue

        # Remove obvious navigation items
        if any(
            word in title.lower()
            for word in [
                "privacy policy",
                "terms of service",
                "contact us",
                "login",
                "sign up",
                "about us"
            ]
        ):
            continue

        # Description
        description = clean_text(
            item.get(
                "description",
                ""
            )
        )

        # Don't use avatar/profile images
        image = item.get(
            "image",
            ""
        )

        if image and is_bad_image(
            image
        ):
            image = ""

        item["title"] = title
        item["description"] = description
        item["image"] = image

        cleaned.append(
            item
        )

    return cleaned


# =========================================================
# FETCH ALL
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

        try:

            print(
                "Fetching:",
                fetcher.__name__
            )

            data = fetcher()

            if data:

                print(
                    fetcher.__name__,
                    "found",
                    len(data),
                    "items"
                )

                all_items.extend(
                    data
                )

        except Exception as e:

            print(
                "Platform error:",
                fetcher.__name__,
                e
            )

    all_items = clean_final_items(
        all_items
    )

    all_items = deduplicate(
        all_items
    )

    return all_items


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return (
        "Hackathon Python API is working!"
    )


# =========================================================
# TEST
# =========================================================

@app.route("/api/test")
def test():

    return jsonify({
        "status": "success",
        "message": "Python API is running on Render"
    })


# =========================================================
# HACKATHONS API
# =========================================================

@app.route("/api/hackathons")
def hackathons():

    data = fetch_all()

    return jsonify(
        data
    )


# =========================================================
# START SERVER
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

#!/usr/bin/env python3
import argparse
import os
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs
import email.utils
import re
import xml.etree.ElementTree as ET
import xml.sax.saxutils as saxutils

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser

DEFAULT_TIMEOUT = 20


FRENCH_DATE_REGEX = re.compile(
    r"\b(?P<day>\d{1,2})\s+(?P<month>janvier|février|fevrier|mars|avril|mai|juin|juillet|août|aout|septembre|octobre|novembre|décembre|decembre)\s+(?P<year>\d{4})\b",
    re.IGNORECASE,
)

FRENCH_MONTHS = {
    "janvier": 1,
    "février": 2,
    "fevrier": 2,
    "mars": 3,
    "avril": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7,
    "août": 8,
    "aout": 8,
    "septembre": 9,
    "octobre": 10,
    "novembre": 11,
    "décembre": 12,
    "decembre": 12,
}

MONTH_NAMES_FR = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril",
    5: "Mai", 6: "Juin", 7: "Juillet", 8: "Août",
    9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre",
}
 
# Keyword-based auto-categorisation
CATEGORIES = [
    {
        "id": "ia",
        "label": "Intelligence Artificielle",
        "keywords": [
            "intelligence artificielle", "ia", "algorithme", "machine learning",
            "apprentissage automatique", "deep learning", "llm", "chatgpt", "openai",
            "modèle d'ia", "système d'ia", "robot", "automatisation", "chatbot",
            "recommandation algorithmique", "traitement automatisé",
        ],
    },
    {
        "id": "education",
        "label": "Éducation",
        "keywords": [
            "éducation", "école", "lycée", "collège", "enfant", "mineur", "jeune",
            "sensibilisation", "formation", "pédagogie", "élève", "étudiant",
            "numérique responsable", "médias", "apprentissage", "parent",
        ],
    },
    {
        "id": "sante",
        "label": "Santé",
        "keywords": [
            "santé", "médical", "hôpital", "patient", "données de santé", "dossier médical",
            "pharmacie", "biométrique", "génétique", "ehpad", "médecin",
            "assurance maladie", "télémédecine", "essai clinique",
        ],
    },
    {
        "id": "droits",
        "label": "Droits & Libertés",
        "keywords": [
            "droit", "liberté", "plainte", "recours", "rgpd", "règlement",
            "consentement", "transparence", "vie privée", "protection des données",
            "droit d'accès", "droit à l'oubli", "droit d'opposition", "cookies",
            "traçage", "surveillance", "reconnaissance faciale",
        ],
    },
    {
        "id": "cyber",
        "label": "Cybersécurité",
        "keywords": [
            "cybersécurité", "sécurité informatique", "violation", "fuite de données",
            "piratage", "ransomware", "malware", "phishing", "hameçonnage",
            "incident", "brèche", "vulnérabilité", "chiffrement", "mot de passe",
            "authentification", "attaque informatique",
        ],
    },
    {
        "id": "entreprises",
        "label": "Entreprises & RGPD",
        "keywords": [
            "entreprise", "société", "délibération", "mise en demeure", "sanction",
            "amende", "contrôle", "conformité", "dpo", "responsable de traitement",
            "sous-traitant", "transfert de données", "contrat", "privacy by design",
            "registre des traitements", "analyse d'impact",
        ],
    },
    {
        "id": "sanctions",
        "label": "Sanctions",
        "keywords": [
            "sanction", "sanctionne", "sanctions", "sanctionnes", "sanctionné",
            "sanctionnée","sanctionnés", "sanctionnées", "amende", "pénalité", "inobservation",
            "manquement"
        ],
    },
]


def _compile_keyword_pattern(keyword):
    # \b on each side avoids matching the keyword as a sub-string of an
    # unrelated word (e.g. "ia" no longer matches inside "diagnostic").
    return re.compile(r"\b" + re.escape(keyword.strip()) + r"\b", re.IGNORECASE)


for _cat in CATEGORIES:
    _cat["patterns"] = [_compile_keyword_pattern(kw) for kw in _cat["keywords"]]


def classify_article(title, description, themes):
    text = " ".join([title, description] + themes)
    matched = []
    for cat in CATEGORIES:
        if any(pattern.search(text) for pattern in cat["patterns"]):
            matched.append(cat["label"])
    return matched if matched else ["Autre"]
 


def parse_french_date(text):
    if not text:
        return None
    match = FRENCH_DATE_REGEX.search(text)
    if not match:
        return None
    day = int(match.group("day"))
    month = match.group("month").lower()
    year = int(match.group("year"))
    month_number = FRENCH_MONTHS.get(month)
    if not month_number:
        return None
    return datetime(year, month_number, day)


def extract_image_url(node, base_url):
    img = node.select_one('img')
    if not img:
        return None
    for attr in ("src", "data-src", "data-lazy-src", "data-original", "data-srcset"):
        value = img.get(attr)
        if not value:
            continue
        if attr == "data-srcset":
            value = value.split(",")[0].strip().split(" ")[0]
        if value:
            return urljoin(base_url, value)
    return None


def find_next_page_url(soup, base_url):
    next_link = soup.select_one('a[rel="next"], .pager__item--next a, .pagination a[rel="next"]')
    if not next_link or not next_link.has_attr("href"):
        return None
    return urljoin(base_url, next_link["href"])


def page_number_from_url(url):
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    page_values = query.get("page")
    if not page_values:
        return 1
    try:
        page_index = int(page_values[0])
    except ValueError:
        return 1
    return page_index + 1


def crawl(start_url, existing_links=None, max_pages=0, items_per_page=0,
          delay=0.5, timeout=DEFAULT_TIMEOUT, stop_when_no_new=True):
    """Fetch CNIL listing pages one by one (single HTTP request per page).

    If stop_when_no_new is True and existing_links is non-empty, the crawl
    stops as soon as a page contains no article we haven't already seen in
    a previous run. This avoids re-downloading the entire site (100+ pages)
    on every scheduled run -- only the newest pages need to be fetched.
    """
    existing_links = existing_links or set()
    session = requests.Session()
    session.headers.update({"User-Agent": "cnil-rss-generator/1.0"})

    all_items = []
    url = start_url
    visited = set()
    pages_fetched = 0

    while url and url not in visited:
        visited.add(url)
        try:
            resp = session.get(url, timeout=timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:
            print(f"Avertissement: échec de la requête vers {url} ({exc}). "
                  f"Arrêt du crawl, conservation des {len(all_items)} article(s) déjà récupéré(s).")
            break
        soup = BeautifulSoup(resp.text, "html.parser")

        page_number = page_number_from_url(url)
        page_items = parse_articles(soup, url, page_number=page_number)
        if items_per_page > 0:
            page_items = page_items[:items_per_page]
        all_items.extend(page_items)
        pages_fetched += 1

        has_new = any(item["link"] not in existing_links for item in page_items)
        next_url = find_next_page_url(soup, url)

        if max_pages and pages_fetched >= max_pages:
            break
        if stop_when_no_new and existing_links and not has_new:
            break
        if not next_url or next_url in visited:
            break

        url = next_url
        if delay:
            time.sleep(delay)

    return all_items


def load_existing_items(path):
    """Read a previously generated cnil_feed.xml back into the same item
    shape produced by parse_articles, so new runs can merge with it instead
    of re-scraping the whole site every time."""
    if not path or not os.path.exists(path):
        return []

    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return []

    ns = {"media": "http://search.yahoo.com/mrss/"}
    items = []
    for item_el in root.findall("./channel/item"):
        def text(tag):
            el = item_el.find(tag)
            return el.text.strip() if el is not None and el.text else ""

        link = text("link")
        if not link:
            continue

        pub_date_text = text("pubDate")
        dt = None
        if pub_date_text:
            try:
                dt = email.utils.parsedate_to_datetime(pub_date_text)
            except (TypeError, ValueError):
                dt = None
        if dt is not None and dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        if dt is None:
            dt = datetime.now()

        image = None
        image_el = item_el.find("./image/url")
        if image_el is not None and image_el.text:
            image = image_el.text.strip()
        if not image:
            media_el = item_el.find("media:content", ns)
            if media_el is not None:
                image = media_el.get("url")

        page_text = text("page")
        page = int(page_text) if page_text.isdigit() else None

        themes = [
            (el.text or "").strip()
            for el in item_el.findall("theme")
            if el.text and el.text.strip()
        ]

        items.append({
            "title": text("title"),
            "link": link,
            "pubDate": pub_date_text or email.utils.format_datetime(dt),
            "description": text("description"),
            "page": page,
            "date": dt,
            "image": image,
            "themes": themes,
        })
    return items


def parse_articles(soup, base_url, page_number=None):
    items = []
    # Try common article selectors used by many CMSs; fallback to 'a' links
    candidates = soup.select("article") or soup.select(".node") or soup.select(".views-row") or soup.select(".teaser") or soup.select(".item")
    for node in candidates:
        a = node.select_one("a[href]")
        if not a:
            continue
        href = urljoin(base_url, a["href"])
        title = a.get_text(strip=True)
        description_el = (
            node.select_one(".introduction")
            or node.select_one(".description")
            or node.select_one(".summary")
            or node.select_one(".teaser")
            or node.select_one("p:not(.date)")
            or node.select_one("p")
        )
        description = description_el.get_text(strip=True) if description_el else title
        if not title:
            h = node.select_one("h1,h2,h3")
            title = h.get_text(strip=True) if h else href

        # attempt to extract themes/categories from CNIL tag blocks
        themes = []
        for tag in node.select('.tags-list__item, .tag-item'):
            theme = tag.get_text(' ', strip=True)
            if not theme:
                continue
            theme = theme.lstrip('#').strip()
            if theme and theme not in themes:
                themes.append(theme)

        # attempt to find a time element or textual date
        time_el = node.select_one("time") or node.select_one("p.date") or node.select_one(".date") or node.select_one(".posted")
        dt_text = ""
        if time_el:
            if time_el.has_attr("datetime"):
                dt_text = time_el["datetime"].strip()
            else:
                dt_text = time_el.get_text(" ", strip=True)

        if dt_text:
            dt = parse_french_date(dt_text)
            if not dt:
                try:
                    dt = dateparser.parse(dt_text, dayfirst=True, fuzzy=True)
                except Exception:
                    dt = None
        else:
            dt = None
        if not dt:
            dt = datetime.now()

        image_url = extract_image_url(node, base_url)
        pubdate = email.utils.format_datetime(dt)
        items.append({
            "title": title,
            "link": href,
            "pubDate": pubdate,
            "description": description,
            "page": page_number,
            "date": dt,
            "image": image_url,
            "themes": themes,
        })
    # As a fallback, collect top-level links from the page
    if not items:
        for a in soup.select("a[href]")[:30]:
            href = urljoin(base_url, a["href"])
            title = a.get_text(strip=True) or href
            now = datetime.now()
            items.append({"title": title, "link": href, "pubDate": email.utils.format_datetime(now), "description": title, "page": page_number, "date": now})
    return items


def guess_image_mime(url):
    if not url:
        return "image/jpeg"
    path = urlparse(url).path.lower()
    if path.endswith(".png"):
        return "image/png"
    if path.endswith(".gif"):
        return "image/gif"
    if path.endswith(".webp"):
        return "image/webp"
    if path.endswith(".svg"):
        return "image/svg+xml"
    return "image/jpeg"


def build_rss(items, title="CNIL Actualités", link="https://cnil.fr/fr/actualite", description="Flux RSS personnalisé des actualités CNIL"):
    out = '<?xml version="1.0" encoding="UTF-8"?>\n'
    out += '<?xml-stylesheet type="text/xsl" href="feed.xsl"?>\n'
    out += "<rss version=\"2.0\" xmlns:media=\"http://search.yahoo.com/mrss/\">\n  <channel>\n"
    out += f"    <title>{saxutils.escape(title)}</title>\n"
    out += f"    <link>{saxutils.escape(link)}</link>\n"
    out += f"    <description>{saxutils.escape(description)}</description>\n"
    out += f"    <language>fr-FR</language>\n"
    for it in items:
        out += "    <item>\n"
        out += f"      <title>{saxutils.escape(it['title'])}</title>\n"
        out += f"      <link>{saxutils.escape(it['link'])}</link>\n"
        out += f"      <guid isPermaLink=\"true\">{saxutils.escape(it['link'])}</guid>\n"
        description_text = saxutils.escape(it['description'])
        if it.get("image"):
            image_url = saxutils.escape(it['image'])
            mime_type = guess_image_mime(it['image'])
            out += f"      <enclosure url=\"{image_url}\" length=\"0\" type=\"{mime_type}\"/>\n"
            out += f"      <media:content url=\"{image_url}\" medium=\"image\" type=\"{mime_type}\"/>\n"
            out += f"      <media:thumbnail url=\"{image_url}\"/>\n"
            out += "      <image>\n"
            out += f"        <url>{image_url}</url>\n"
            out += "      </image>\n"
            safe_description = it['description'].replace(']]>', ']]]]><![CDATA[>')
            out += f"      <description><![CDATA[{safe_description}]]></description>\n"
        else:
            safe_description = it['description'].replace(']]>', ']]]]><![CDATA[>')
            out += f"      <description><![CDATA[{safe_description}]]></description>\n"
        if it.get("page") is not None:
            out += f"      <page>{int(it['page'])}</page>\n"
        out += f"      <year>{it['date'].year}</year>\n"
        out += f"      <month>{it['date'].month}</month>\n"
        categories = classify_article(it['title'], it['description'], it.get('themes', []))
        for category in categories:
            out += f"      <category>{saxutils.escape(category)}</category>\n"
        if it.get("themes"):
            for theme in it["themes"]:
                out += f"      <theme>{saxutils.escape(theme)}</theme>\n"
        out += f"      <pubDate>{saxutils.escape(it['pubDate'])}</pubDate>\n"
        out += "    </item>\n"
    out += "  </channel>\n</rss>\n"
    return out


def main():
    parser = argparse.ArgumentParser(description="Generate a simple RSS feed from https://cnil.fr/fr/actualite")
    parser.add_argument("--url", default="https://cnil.fr/fr/actualite")
    parser.add_argument("--output", default="cnil_feed.xml")
    parser.add_argument("--limit", type=int, default=0, help="Number of articles to include. Use 0 for no limit.")
    parser.add_argument("--pages", type=int, default=0, help="Max number of listing pages to fetch this run. Use 0 for no limit.")
    parser.add_argument("--items-per-page", type=int, default=6, help="Maximum number of articles per RSS page")
    parser.add_argument("--year", type=int, default=None, help="Include only articles from this year")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP request timeout in seconds")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay in seconds between page requests")
    parser.add_argument(
        "--force-full-scan",
        action="store_true",
        help="Re-crawl every listing page even if no new articles are found (default: stop early once nothing new shows up).",
    )
    args = parser.parse_args()

    existing_items = load_existing_items(args.output)
    existing_links = {item["link"] for item in existing_items}

    new_items = crawl(
        args.url,
        existing_links=existing_links,
        max_pages=args.pages,
        items_per_page=args.items_per_page,
        delay=args.delay,
        timeout=args.timeout,
        stop_when_no_new=not args.force_full_scan,
    )

    # Merge: newly-scraped data wins for articles seen again (content may
    # have changed), everything else from the previous feed is kept as-is.
    merged_by_link = {item["link"]: item for item in existing_items}
    merged_by_link.update({item["link"]: item for item in new_items})
    all_items = list(merged_by_link.values())

    if args.year is not None:
        all_items = [item for item in all_items if item["date"].year == args.year]
    all_items.sort(key=lambda item: item["date"], reverse=True)
    items = all_items if args.limit <= 0 else all_items[: args.limit]
    rss = build_rss(items)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(rss)
    print(f"Found {len(new_items)} item(s) on this crawl, {len(items)} total written to {args.output}")


if __name__ == "__main__":
    main()

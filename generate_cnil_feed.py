#!/usr/bin/env python3
import argparse
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs
import email.utils
import re
import xml.sax.saxutils as saxutils

import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser


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


def collect_paginated_urls(start_url, max_pages=3):
    urls = [start_url]
    while len(urls) < max_pages:
        resp = requests.get(urls[-1], headers={"User-Agent": "cnil-rss-generator/1.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        next_url = find_next_page_url(soup, urls[-1])
        if not next_url or next_url in urls:
            break
        urls.append(next_url)
    return urls


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
    out += "<rss version=\"2.0\">\n  <channel>\n"
    out += f"    <title>{saxutils.escape(title)}</title>\n"
    out += f"    <link>{saxutils.escape(link)}</link>\n"
    out += f"    <description>{saxutils.escape(description)}</description>\n"
    out += f"    <language>fr-FR</language>\n"
    for it in items:
        out += "    <item>\n"
        out += f"      <title>{saxutils.escape(it['title'])}</title>\n"
        out += f"      <link>{saxutils.escape(it['link'])}</link>\n"
        out += f"      <guid isPermaLink=\"true\">{saxutils.escape(it['link'])}</guid>\n"
        if it.get("image"):
            out += f"      <enclosure url=\"{saxutils.escape(it['image'])}\" length=\"0\" type=\"{guess_image_mime(it['image'])}\"/>\n"
            out += "      <image>\n"
            out += f"        <url>{saxutils.escape(it['image'])}</url>\n"
            out += "      </image>\n"
        if it.get("page") is not None:
            out += f"      <category>Page {it['page']}</category>\n"
        out += f"      <description>{saxutils.escape(it['description'])}</description>\n"
        out += f"      <pubDate>{saxutils.escape(it['pubDate'])}</pubDate>\n"
        out += "    </item>\n"
    out += "  </channel>\n</rss>\n"
    return out


def main():
    parser = argparse.ArgumentParser(description="Generate a simple RSS feed from https://cnil.fr/fr/actualite")
    parser.add_argument("--url", default="https://cnil.fr/fr/actualite")
    parser.add_argument("--output", default="cnil_feed.xml")
    parser.add_argument("--limit", type=int, default=20, help="Number of articles to include. Use 0 for no limit.")
    parser.add_argument("--pages", type=int, default=3, help="Number of paginated pages to fetch")
    parser.add_argument("--items-per-page", type=int, default=6, help="Maximum number of articles per RSS page")
    parser.add_argument("--year", type=int, default=None, help="Include only articles from this year")
    args = parser.parse_args()

    page_urls = collect_paginated_urls(args.url, max_pages=args.pages)
    all_items = []
    for page_url in page_urls:
        resp = requests.get(page_url, headers={"User-Agent": "cnil-rss-generator/1.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        page_number = page_number_from_url(page_url)
        all_items.extend(parse_articles(soup, page_url, page_number=page_number))

    if args.year is not None:
        all_items = [item for item in all_items if item["date"].year == args.year]
    all_items.sort(key=lambda item: item["date"], reverse=True)
    items = all_items if args.limit <= 0 else all_items[: args.limit]
    for index, item in enumerate(items):
        item["page"] = (index // args.items_per_page) + 1
    rss = build_rss(items)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(rss)
    print(f"Wrote {len(items)} items to {args.output}")


if __name__ == "__main__":
    main()

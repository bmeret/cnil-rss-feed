#!/usr/bin/env python3
import argparse
from datetime import datetime
from urllib.parse import urljoin
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


def parse_articles(soup, base_url):
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

        pubdate = email.utils.format_datetime(dt)
        items.append({"title": title, "link": href, "pubDate": pubdate, "description": description})
    # As a fallback, collect top-level links from the page
    if not items:
        for a in soup.select("a[href]")[:30]:
            href = urljoin(base_url, a["href"])
            title = a.get_text(strip=True) or href
            items.append({"title": title, "link": href, "pubDate": email.utils.format_datetime(datetime.now())})
    return items


def build_rss(items, title="CNIL Actualités", link="https://cnil.fr/fr/actualite", description="Flux RSS personnalisé des actualités CNIL"):
    out = '<?xml version="1.0" encoding="UTF-8"?>\n'
    out += '<?xml-stylesheet type="text/css" href="style.css"?>\n'
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
        out += f"      <description>{saxutils.escape(it['description'])}</description>\n"
        out += f"      <pubDate>{saxutils.escape(it['pubDate'])}</pubDate>\n"
        out += "    </item>\n"
    out += "  </channel>\n</rss>\n"
    return out


def main():
    parser = argparse.ArgumentParser(description="Generate a simple RSS feed from https://cnil.fr/fr/actualite")
    parser.add_argument("--url", default="https://cnil.fr/fr/actualite")
    parser.add_argument("--output", default="cnil_feed.xml")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    resp = requests.get(args.url, headers={"User-Agent": "cnil-rss-generator/1.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    items = parse_articles(soup, args.url)[: args.limit]
    rss = build_rss(items)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(rss)
    print(f"Wrote {len(items)} items to {args.output}")


if __name__ == "__main__":
    main()

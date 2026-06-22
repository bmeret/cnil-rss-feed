# CNIL RSS generator

This project scrapes https://cnil.fr/fr/actualite and produces:

- `cnil_feed.xml` — an RSS 2.0 feed, enriched with images, the CNIL site's
  own tags (`<theme>`), an auto-classified topic taxonomy (`<category>`,
  see "Categorisation" below), and `<year>`/`<month>` for date filtering.
- `feed.xsl` — a stylesheet attached to the feed itself. Opening
  `cnil_feed.xml` directly in a browser renders a styled, filterable page
  (filter by tag, browse by page) without any extra setup.
- `index.html` — a standalone dashboard (fetches `cnil_feed.xml` via
  JavaScript) with a sidebar to filter by category, year and month.

## Usage

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run the generator (writes `cnil_feed.xml` by default):

```bash
python generate_cnil_feed.py --output cnil_feed.xml
```

Useful options:

| Flag | Default | Description |
|---|---|---|
| `--url` | `https://cnil.fr/fr/actualite` | Listing page to start crawling from |
| `--output` | `cnil_feed.xml` | Output file. Also read on startup to merge with previous results |
| `--limit` | `0` (unlimited) | Max number of articles kept in the final feed (oldest dropped first). Recommended in production to stop the file growing forever — e.g. `--limit 500` |
| `--pages` | `0` (unlimited) | Max number of listing pages fetched **this run** |
| `--items-per-page` | `6` | Max articles parsed per listing page |
| `--year` | none | Keep only articles from a given year |
| `--timeout` | `20` | HTTP request timeout (seconds) |
| `--delay` | `0.5` | Delay between page requests, to be polite to cnil.fr |
| `--force-full-scan` | off | Re-crawl every listing page even if a page has no new article (see "Incremental crawling") |

3. Open `index.html` (or `cnil_feed.xml` directly) in a browser, served
   from the same folder so the relative `cnil_feed.xml` / `feed.xsl`
   reference resolves.

## Incremental crawling

On each run, the script first reads the existing `--output` file (if any)
and remembers which article links it already has. It then crawls listing
pages starting from `--url`, and **stops as soon as a page contains no
article it hasn't already seen** — new articles always appear on the
first page(s), so a routine run typically fetches only 1-2 pages instead
of re-downloading the whole site's history every time.

The newly-found items are merged with the previous feed (new data wins
for articles seen again, e.g. if a title was edited). Use
`--force-full-scan` to disable the early stop and re-crawl everything —
useful for a first run, or to recover after a long gap.

## Categorisation

Each article is auto-tagged with one or more of: *Intelligence
Artificielle, Éducation, Santé, Droits & Libertés, Cybersécurité,
Entreprises & RGPD* (or *Autre* if nothing matches), based on keyword
matching over the title, description and the site's own tags. This is
what `index.html`'s sidebar filters on — it's independent from `<theme>`,
which holds CNIL's raw, unfiltered tags. The keyword lists live in the
`CATEGORIES` constant in `generate_cnil_feed.py` and can be tuned there.

## Hosting

- To publish the feed and dashboard, push the repository to GitHub and
  enable GitHub Pages (serve from the repository root). They'll be
  available at `https://<username>.github.io/<repo>/cnil_feed.xml` and
  `https://<username>.github.io/<repo>/index.html`.
- `generate_cnil_feed.yml` is a GitHub Actions workflow that runs the
  generator every 2 hours and commits the updated `cnil_feed.xml`
  automatically — no extra setup needed beyond enabling Actions on the repo.
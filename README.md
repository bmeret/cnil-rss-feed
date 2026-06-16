# CNIL RSS generator

This small project generates a simple RSS feed for https://cnil.fr/fr/actualite.

Usage

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Run the generator (writes `cnil_feed.xml` by default):

```bash
python generate_cnil_feed.py --output cnil_feed.xml
```

Hosting

- To publish the feed, push `cnil_feed.xml` to a GitHub repository and enable GitHub Pages (serve from the repository root). The file will be available at `https://<username>.github.io/<repo>/cnil_feed.xml`.
- For automatic updates, set up a scheduled runner (GitHub Actions or a cron job) that runs the script and commits the updated `cnil_feed.xml`.

If you want, I can add a GitHub Actions workflow that runs daily and commits the generated feed.
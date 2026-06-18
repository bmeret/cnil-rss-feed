<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns:media="http://search.yahoo.com/mrss/">
  <xsl:output method="html" encoding="UTF-8" indent="yes"/>
  <xsl:key name="item-by-category" match="channel/item" use="category"/>

  <xsl:template match="/rss">
    <html>
      <head>
        <meta charset="UTF-8"/>
        <title><xsl:value-of select="channel/title"/></title>
        <style>
          body { font-family: Arial, sans-serif; background: #f5f5f5; color: #222; margin: 0; padding: 30px; }
          .container { max-width: 980px; margin: auto; }
          header { margin-bottom: 30px; }
          h1 { font-size: 28px; margin-bottom: 5px; color: #003d7a; }
          p.description { margin-top: 0; color: #555; }
          .item { background: #fff; border-left: 4px solid #003d7a; padding: 18px 20px; margin-bottom: 18px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
          .item.hidden { display: none; }
          .item-image { margin-bottom: 14px; }
          .item-image img { width: 100%; max-height: 220px; object-fit: cover; border-radius: 6px; display: block; }
          .item h2 { font-size: 18px; margin: 0 0 10px; }
          .item a.title { color: #003d7a; text-decoration: none; }
          .item a.title:hover { text-decoration: underline; }
          .meta { font-size: 13px; color: #666; margin-bottom: 10px; }
          .meta span { margin-right: 14px; }
          .theme-list { margin-bottom: 12px; }
          .theme-tag { display: inline-block; background: #e1f0ff; color: #003d7a; border-radius: 12px; padding: 3px 10px; font-size: 12px; margin-right: 6px; margin-bottom: 6px; }
          .filter-bar { margin-bottom: 20px; }
          .filter-group { display: flex; flex-wrap: wrap; gap: 10px; }
          .filter-button { padding: 8px 14px; background: #ccc; color: #222; border: none; border-radius: 4px; cursor: pointer; }
          .filter-button.active { background: #003d7a; color: #fff; }
          .pager { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 28px; }
          .pager button { padding: 8px 14px; background: #003d7a; color: #fff; border: none; border-radius: 4px; cursor: pointer; }
          .pager button.active { background: #0058b0; }
          .pager button:hover { opacity: 0.9; }
        </style>
      </head>
      <body>
        <div class="container">
          <header>
            <h1><xsl:value-of select="channel/title"/></h1>
            <p class="description"><xsl:value-of select="channel/description"/></p>
          </header>
          <div class="filter-bar">
            <div class="filter-group">
              <button class="filter-button active" data-theme="all">Tous</button>
            </div>
          </div>

          <xsl:for-each select="channel/item">
            <div class="item" data-page="{page}">
              <xsl:attribute name="data-themes">
                <xsl:for-each select="theme">
                  <xsl:value-of select="."/>
                  <xsl:if test="position() != last()">|</xsl:if>
                </xsl:for-each>
              </xsl:attribute>
              <xsl:choose>
                <xsl:when test="image/url">
                  <div class="item-image">
                    <img src="{image/url}" alt="Article image" loading="lazy" />
                  </div>
                </xsl:when>
                <xsl:when test="media:content/@url">
                  <div class="item-image">
                    <img src="{media:content/@url}" alt="Article image" loading="lazy" />
                  </div>
                </xsl:when>
              </xsl:choose>
              <h2><a class="title" href="{link}" target="_blank"><xsl:value-of select="title"/></a></h2>
              <div class="meta">
                <span><xsl:value-of select="pubDate"/></span>
                <span><xsl:value-of select="page"/></span>
              </div>
                  <div class="theme-list">
                <xsl:for-each select="theme">
                  <span class="theme-tag"><xsl:value-of select="."/></span>
                </xsl:for-each>
              </div>
              <div class="description"><xsl:value-of select="description" disable-output-escaping="yes"/></div>
            </div>
          </xsl:for-each>

          <div class="pager" id="pager"></div>
        </div>
        <script type="text/javascript">
          (function() {
            var container = document.querySelector('.container');
            if (!container) return;
            var pager = document.getElementById('pager');
            var filterGroup = document.querySelector('.filter-group');
            var items = Array.prototype.slice.call(container.querySelectorAll('.item'));
            var categories = [];
            var currentPage = 'Page 1';
            var activeThemes = [];

            items.forEach(function(item) {
              var page = item.getAttribute('data-page') || 'Page 1';
              if (categories.indexOf(page) === -1) {
                categories.push(page);
              }
            });

            function updateVisibility() {
              items.forEach(function(item) {
                var pageMatch = item.getAttribute('data-page') === currentPage;
                var themeAttr = item.getAttribute('data-themes') || '';
                var themeMatch = activeThemes.length === 0 || activeThemes.some(function(theme) {
                  return themeAttr.split('|').indexOf(theme) !== -1;
                });
                item.classList.toggle('hidden', !(pageMatch && themeMatch));
              });
            }

            function updateThemeButtons() {
              var buttons = filterGroup.querySelectorAll('button[data-theme]');
              buttons.forEach(function(btn) {
                var theme = btn.getAttribute('data-theme');
                if (theme === 'all') {
                  btn.classList.toggle('active', activeThemes.length === 0);
                } else {
                  btn.classList.toggle('active', activeThemes.indexOf(theme) !== -1);
                }
              });
            }

            categories.forEach(function(page, index) {
              var button = document.createElement('button');
              button.textContent = page;
              button.setAttribute('data-page', page);
              button.addEventListener('click', function() {
                currentPage = page;
                var buttons = pager.querySelectorAll('button');
                buttons.forEach(function(btn) {
                  btn.classList.toggle('active', btn === button);
                });
                updateVisibility();
              });
              pager.appendChild(button);
              if (index === 0) {
                button.classList.add('active');
                currentPage = page;
              }
            });

            if (categories.length > 0) {
              updateVisibility();
            }

            var themes = [];
            items.forEach(function(item) {
              var themeAttr = item.getAttribute('data-themes');
              if (!themeAttr) return;
              themeAttr.split('|').forEach(function(theme) {
                if (theme && themes.indexOf(theme) === -1) {
                  themes.push(theme);
                }
              });
            });
            themes.sort();

            var allButton = filterGroup.querySelector('button[data-theme="all"]');
            if (allButton) {
              allButton.addEventListener('click', function() {
                activeThemes = [];
                updateThemeButtons();
                updateVisibility();
              });
            }

            themes.forEach(function(theme) {
              var button = document.createElement('button');
              button.className = 'filter-button';
              button.textContent = theme;
              button.setAttribute('data-theme', theme);
              button.addEventListener('click', function() {
                var index = activeThemes.indexOf(theme);
                if (index === -1) {
                  activeThemes.push(theme);
                } else {
                  activeThemes.splice(index, 1);
                }
                updateThemeButtons();
                updateVisibility();
              });
              filterGroup.appendChild(button);
            });
            updateThemeButtons();
          })();
        </script>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>

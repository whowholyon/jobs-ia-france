#!/usr/bin/env python3
"""
Generateur de site statique : construit les pages HTML
a partir des donnees TSV/JSON du scraper.
"""

import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
SITE = ROOT / 'site'

SITE_TITLE = 'Jobs IA France'
SITE_DESC = 'Offres d\'emploi dans les startups IA francaises qui font de la vraie tech'
SITE_URL = ''

CATEGORIES = [
    ('IA / ML / Data Science', 'ia-ml', '#e74c3c'),
    ('Dev / Engineering', 'dev', '#3498db'),
    ('Data', 'data', '#2ecc71'),
    ('Ops / Infra / QA', 'ops', '#9b59b6'),
    ('Product / Design', 'product', '#f39c12'),
    ('Sales / Business', 'sales', '#1abc9c'),
    ('Marketing / Growth', 'marketing', '#e67e22'),
    ('Management / Leadership', 'management', '#34495e'),
    ('RH / People', 'rh', '#e91e63'),
    ('Stage / Alternance', 'stages', '#00bcd4'),
    ('Autre', 'autre', '#95a5a6'),
]

CATEGORY_SLUGS = {name: slug for name, slug, _ in CATEGORIES}
CATEGORY_COLORS = {name: color for name, _, color in CATEGORIES}


def loadJobs() -> list[dict]:
    tsvPath = DATA / 'offres_emploi.tsv'
    if not tsvPath.exists():
        oldPath = ROOT / 'offres_emploi_ia_core.tsv'
        if oldPath.exists():
            tsvPath = oldPath

    jobs = []
    with open(tsvPath, encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            key = 'Categorie' if 'Categorie' in row else 'Catégorie'
            jobs.append({
                'category': row.get(key, 'Autre'),
                'startup': row.get('Startup', ''),
                'tier': row.get('Tier', ''),
                'region': row.get('Region', row.get('Région', '')),
                'title': row.get('Titre du poste', ''),
                'url': row.get('Lien offre', ''),
                'tech': row.get('Tech startup', ''),
                'startup_url': row.get('Site startup', ''),
            })

    return jobs


def loadStartups() -> list[dict]:
    tsvPath = DATA / 'ai_core.tsv'
    if not tsvPath.exists():
        tsvPath = ROOT / 'ai_core.tsv'

    startups = []
    with open(tsvPath, encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            startups.append({
                'tier': row.get('Tier', ''),
                'score': row.get('Score', ''),
                'name': row.get('Nom', ''),
                'url': row.get('URL', ''),
                'year': row.get('Annee', row.get('Année', '')),
                'region': row.get('Region', row.get('Région', '')),
                'tech': row.get('Tech detectee sur le site', row.get('Tech détectée sur le site', '')),
                'desc': row.get('Description', ''),
            })

    return startups


def escape(text: str) -> str:
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def css() -> str:
    return """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,-apple-system,sans-serif;background:#0a0a0a;color:#e0e0e0;line-height:1.6}
a{color:#60a5fa;text-decoration:none}a:hover{text-decoration:underline}
.container{max-width:1100px;margin:0 auto;padding:0 20px}
header{background:#111;border-bottom:1px solid #222;padding:20px 0}
header h1{font-size:1.8rem;color:#fff}
header p{color:#888;margin-top:4px}
nav{background:#111;border-bottom:1px solid #222;padding:10px 0;position:sticky;top:0;z-index:10}
nav .container{display:flex;gap:8px;flex-wrap:wrap}
nav a{padding:4px 12px;border-radius:16px;font-size:.85rem;color:#ccc;border:1px solid #333;white-space:nowrap}
nav a:hover,nav a.active{background:#222;color:#fff;text-decoration:none;border-color:#555}
.stats{display:flex;gap:20px;padding:20px 0;flex-wrap:wrap}
.stat{background:#161616;border:1px solid #222;border-radius:8px;padding:16px 20px;flex:1;min-width:140px}
.stat-value{font-size:1.5rem;font-weight:700;color:#fff}
.stat-label{font-size:.8rem;color:#888;margin-top:2px}
.filters{padding:16px 0;display:flex;gap:12px;flex-wrap:wrap;align-items:center}
.filters input{background:#161616;border:1px solid #333;color:#e0e0e0;padding:8px 14px;border-radius:8px;font-size:.9rem;width:300px}
.filters select{background:#161616;border:1px solid #333;color:#e0e0e0;padding:8px 14px;border-radius:8px;font-size:.9rem}
.job-list{list-style:none;display:flex;flex-direction:column;gap:2px}
.job{background:#161616;border:1px solid #222;border-radius:6px;padding:14px 18px;display:flex;align-items:center;gap:16px;transition:border-color .15s}
.job:hover{border-color:#444}
.job-cat{font-size:.7rem;padding:3px 8px;border-radius:10px;color:#fff;white-space:nowrap;font-weight:600;min-width:60px;text-align:center}
.job-info{flex:1;min-width:0}
.job-title{font-weight:500;color:#fff}
.job-meta{font-size:.8rem;color:#888;margin-top:2px}
.job-meta span{margin-right:12px}
.tier{font-size:.65rem;padding:2px 6px;border-radius:4px;font-weight:700}
.tier-A{background:#166534;color:#4ade80}.tier-B{background:#854d0e;color:#fbbf24}
.section-title{font-size:1.2rem;font-weight:600;color:#fff;padding:24px 0 12px;border-bottom:1px solid #222;margin-bottom:12px}
.startup-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:12px;padding:12px 0}
.startup-card{background:#161616;border:1px solid #222;border-radius:8px;padding:16px}
.startup-card h3{font-size:1rem;color:#fff;margin-bottom:4px}
.startup-card .meta{font-size:.8rem;color:#888;margin-bottom:8px}
.startup-card .tech{display:flex;flex-wrap:wrap;gap:4px}
.startup-card .tech span{font-size:.7rem;background:#1e293b;color:#94a3b8;padding:2px 8px;border-radius:10px}
footer{border-top:1px solid #222;padding:20px 0;margin-top:40px;text-align:center;color:#555;font-size:.8rem}
@media(max-width:640px){
  .stats{flex-direction:column}
  .filters input{width:100%}
  .job{flex-direction:column;align-items:flex-start;gap:8px}
  nav .container{gap:4px}nav a{font-size:.75rem;padding:3px 8px}
}
"""


def js() -> str:
    return """
document.addEventListener('DOMContentLoaded',()=>{
  const input=document.getElementById('search');
  const regionSel=document.getElementById('region-filter');
  const jobs=document.querySelectorAll('.job');
  if(!input)return;

  function filter(){
    const q=input.value.toLowerCase();
    const r=regionSel?regionSel.value:'';
    let count=0;
    jobs.forEach(j=>{
      const text=j.textContent.toLowerCase();
      const region=j.dataset.region||'';
      const show=text.includes(q)&&(!r||region===r);
      j.style.display=show?'':'none';
      if(show)count++;
    });
    const counter=document.getElementById('job-count');
    if(counter)counter.textContent=count;
  }

  input.addEventListener('input',filter);
  if(regionSel)regionSel.addEventListener('change',filter);
});
"""


def renderNav(activeCat: str = '') -> str:
    links = [f'<a href="index.html"{"class=\"active\"" if not activeCat else ""}>Toutes</a>']
    for name, slug, _ in CATEGORIES:
        active = ' class="active"' if activeCat == slug else ''
        links.append(f'<a href="{slug}.html"{active}>{escape(name)}</a>')
    links.append(f'<a href="startups.html"{"class=\"active\"" if activeCat == "startups" else ""}>Startups</a>')

    return f'<nav><div class="container">{"".join(links)}</div></nav>'


def renderJobList(jobs: list[dict]) -> str:
    regions = sorted(set(j['region'] for j in jobs if j['region']))
    regionOptions = ''.join(f'<option value="{escape(r)}">{escape(r)}</option>' for r in regions)

    html = f'''<div class="filters">
<input type="text" id="search" placeholder="Rechercher par titre, startup, techno...">
<select id="region-filter"><option value="">Toutes les regions</option>{regionOptions}</select>
<span style="color:#888;font-size:.85rem"><span id="job-count">{len(jobs)}</span> offres</span>
</div>
<ul class="job-list">'''

    for j in jobs:
        color = CATEGORY_COLORS.get(j['category'], '#666')
        tierClass = f'tier-{j["tier"]}' if j['tier'] in ('A', 'B') else ''

        html += f'''<li class="job" data-region="{escape(j['region'])}">
<span class="job-cat" style="background:{color}">{escape(j['category'])}</span>
<div class="job-info">
<a class="job-title" href="{escape(j['url'])}" target="_blank" rel="noopener">{escape(j['title'])}</a>
<div class="job-meta">
<span>{escape(j['startup'])}</span>
<span class="tier {tierClass}">{escape(j['tier'])}</span>
<span>{escape(j['region'])}</span>
</div>
</div>
</li>'''

    html += '</ul>'

    return html


def renderPage(title: str, body: str, nav: str, desc: str = '') -> str:
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

    return f'''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} - {SITE_TITLE}</title>
<meta name="description" content="{escape(desc or SITE_DESC)}">
<style>{css()}</style>
</head>
<body>
<header><div class="container">
<h1>{SITE_TITLE}</h1>
<p>{escape(SITE_DESC)}</p>
</div></header>
{nav}
<main class="container">
{body}
</main>
<footer><div class="container">
Mis a jour le {now} &middot;
Donnees extraites automatiquement des sites des startups
</div></footer>
<script>{js()}</script>
</body>
</html>'''


def generateIndex(jobs: list[dict], startups: list[dict]) -> None:
    nbStartups = len(set(j['startup'] for j in jobs))
    nbRegions = len(set(j['region'] for j in jobs if j['region']))

    catCounts = {}
    for j in jobs:
        catCounts[j['category']] = catCounts.get(j['category'], 0) + 1

    stats = f'''<div class="stats">
<div class="stat"><div class="stat-value">{len(jobs)}</div><div class="stat-label">offres d'emploi</div></div>
<div class="stat"><div class="stat-value">{nbStartups}</div><div class="stat-label">startups IA</div></div>
<div class="stat"><div class="stat-value">{len(startups)}</div><div class="stat-label">startups analysees</div></div>
<div class="stat"><div class="stat-value">{nbRegions}</div><div class="stat-label">regions</div></div>
</div>'''

    body = stats + renderJobList(jobs)

    page = renderPage('Toutes les offres', body, renderNav())
    (SITE / 'index.html').write_text(page, encoding='utf-8')


def generateCategoryPages(jobs: list[dict]) -> None:
    for catName, slug, _ in CATEGORIES:
        catJobs = [j for j in jobs if j['category'] == catName]
        if not catJobs:
            continue

        title = f'{catName} ({len(catJobs)} offres)'
        body = f'<h2 class="section-title">{escape(title)}</h2>' + renderJobList(catJobs)

        page = renderPage(catName, body, renderNav(slug),
                          f'Offres {catName} dans les startups IA francaises')
        (SITE / f'{slug}.html').write_text(page, encoding='utf-8')


def generateStartupsPage(startups: list[dict], jobs: list[dict]) -> None:
    jobCounts = {}
    for j in jobs:
        jobCounts[j['startup']] = jobCounts.get(j['startup'], 0) + 1

    body = f'<h2 class="section-title">{len(startups)} startups IA core analysees</h2>'
    body += '<div class="startup-grid">'

    for s in startups:
        techTags = ''.join(
            f'<span>{escape(t.strip())}</span>'
            for t in s['tech'].split(',') if t.strip()
        )
        nbJobs = jobCounts.get(s['name'], 0)
        jobsText = f'{nbJobs} offre{"s" if nbJobs > 1 else ""}' if nbJobs else 'Pas d\'offres'

        body += f'''<div class="startup-card">
<h3><a href="{escape(s['url'])}" target="_blank" rel="noopener">{escape(s['name'])}</a></h3>
<div class="meta">
<span class="tier tier-{s['tier']}">Tier {s['tier']}</span> &middot;
{escape(s['region'])} &middot; {jobsText}
</div>
<p style="font-size:.85rem;color:#aaa;margin-bottom:8px">{escape(s['desc'][:150])}</p>
<div class="tech">{techTags}</div>
</div>'''

    body += '</div>'

    page = renderPage('Startups', body, renderNav('startups'),
                      'Startups IA francaises analysees')
    (SITE / 'startups.html').write_text(page, encoding='utf-8')


def generateRssFeed(jobs: list[dict]) -> None:
    now = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S +0000')
    items = ''

    for j in jobs[:100]:
        items += f'''<item>
<title>{escape(j['title'])} - {escape(j['startup'])}</title>
<link>{escape(j['url'])}</link>
<description>{escape(j['category'])} | {escape(j['region'])}</description>
<category>{escape(j['category'])}</category>
</item>
'''

    rss = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>{SITE_TITLE}</title>
<description>{escape(SITE_DESC)}</description>
<lastBuildDate>{now}</lastBuildDate>
{items}
</channel>
</rss>'''

    (SITE / 'feed.xml').write_text(rss, encoding='utf-8')


def main():
    SITE.mkdir(exist_ok=True)
    jobs = loadJobs()
    startups = loadStartups()

    print(f'{len(jobs)} offres, {len(startups)} startups')

    generateIndex(jobs, startups)
    generateCategoryPages(jobs)
    generateStartupsPage(startups, jobs)
    generateRssFeed(jobs)

    pages = list(SITE.glob('*.html'))
    print(f'Site genere dans {SITE}/ ({len(pages)} pages)')


if __name__ == '__main__':
    main()

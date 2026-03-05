#!/usr/bin/env python3
"""
Scraper principal : extraction des startups IA core depuis source.html,
scraping des sites web pour signaux techniques, recherche de pages carrieres,
extraction des offres d'emploi.
"""

import hashlib
import json
import os
import re
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'data'
TIMEOUT = 10
MAX_WORKERS = 20
OLLAMA_API_KEY = os.environ.get('OLLAMA_API_KEY', '')
OLLAMA_API_URL = 'https://ollama.com/api/chat'
OLLAMA_MODEL = 'gemini-3-flash-preview'
LLM_BATCH_SIZE = 30
CACHE_PATH = DATA / 'jobs_validated.json'
MAX_MISSED_RUNS = 3

POSITIVE_SIGNALS = {
    'pytorch': 3, 'tensorflow': 3, 'deep learning': 3, 'neural network': 3,
    'reinforcement learning': 3, 'computer vision': 3, 'vision par ordinateur': 3,
    'fine-tuning': 3, 'fine tuning': 3, 'training data': 3,
    'machine learning': 2, 'data science': 2, 'data scientist': 2,
    'scikit-learn': 3, 'computer-vision': 3,
    'GPU': 2, 'PhD': 2, 'chercheur': 2, 'researcher': 2,
    'annotation': 2, 'labeling': 2, 'dataset': 2, 'edge AI': 2,
    'inference': 2, 'embedding': 2, 'transformer': 2,
    'nos modeles': 2, 'nos modèles': 2, 'entraîné': 2, 'entrainé': 2,
    'proprietary tech': 2, 'open-source': 1, 'R&D': 1,
    'lidar': 2, 'LiDAR': 2,
}

NEGATIVE_SIGNALS = {
    'no-code': -3, 'nocode': -3, 'chatbot': -2, 'zapier': -3,
    'assisté par IA': -2, 'assistée par IA': -2,
    'make.com': -2, 'bubble': -2, 'intégrateur': -2,
}

CAREER_PATHS = [
    '/careers', '/jobs', '/recrutement', '/join-us', '/join',
    '/nous-rejoindre', '/recrutement', '/carrieres', '/hiring',
    '/work-with-us', '/equipe', '/team',
]


def extractStartups(htmlPath: Path) -> list[dict]:
    soup = BeautifulSoup(htmlPath.read_text(encoding='utf-8'), 'lxml')
    startups = []

    for card in soup.select('.item-card-top'):
        h2 = card.select_one('h2')
        if not h2:
            continue

        name = h2.get_text(strip=True)
        link = card.select_one('a')
        url = link['href'] if link else ''

        yearDiv = card.select_one('div[style*="font-size:14px"]')
        yearText = yearDiv.get_text(strip=True) if yearDiv else ''
        parts = yearText.split('|', 1)
        year = parts[0].strip() if parts else ''
        aiLevel = parts[1].strip() if len(parts) > 1 else ''

        regionDiv = card.select_one('div[style*="background-color:#42A58D"]')
        region = regionDiv.get_text(strip=True) if regionDiv else ''

        descP = card.select_one('p.item-description')
        desc = descP.get_text(strip=True) if descP else ''

        clientsP = card.select_one('p.item-types_noms_clients')
        clients = clientsP.get_text(strip=True) if clientsP else ''

        startups.append({
            'name': name, 'url': url, 'year': year,
            'ai_level': aiLevel, 'region': region,
            'desc': desc, 'clients': clients,
        })

    return startups


def scrapeWebsite(startup: dict) -> dict:
    url = startup['url']
    if not url.startswith('http'):
        url = 'https://' + url

    result = {**startup, 'web_score': 0, 'web_signals': [], 'scraped': False}

    try:
        resp = requests.get(url, timeout=TIMEOUT, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; JobBoardBot/1.0)'
        })
        resp.raise_for_status()
        text = resp.text.lower()
        result['scraped'] = True

        for keyword, weight in POSITIVE_SIGNALS.items():
            if keyword.lower() in text:
                result['web_score'] += weight
                result['web_signals'].append(f'+{weight} {keyword}')

        for keyword, weight in NEGATIVE_SIGNALS.items():
            if keyword.lower() in text:
                result['web_score'] += weight
                result['web_signals'].append(f'{weight} {keyword}')

    except Exception:
        pass

    return result


def classifyStartups(startups: list[dict]) -> list[dict]:
    print(f'Scraping {len(startups)} sites web...')
    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(scrapeWebsite, s): s for s in startups}
        for future in as_completed(futures):
            results.append(future.result())

    for s in results:
        score = s['web_score']
        if score >= 8:
            s['tier'] = 'A'
        elif score >= 4:
            s['tier'] = 'B'
        elif score >= 2:
            s['tier'] = 'C'
        elif score >= 0:
            s['tier'] = 'D'
        elif score >= -3:
            s['tier'] = 'E'
        else:
            s['tier'] = 'F'

    results.sort(key=lambda s: (-s['web_score'], s['name']))

    return results


def findCareerPage(startup: dict) -> dict | None:
    url = startup['url']
    if not url.startswith('http'):
        url = 'https://' + url

    try:
        resp = requests.get(url, timeout=TIMEOUT, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; JobBoardBot/1.0)'
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'lxml')

        careerKeywords = re.compile(
            r'(career|job|recrutement|rejoindre|hiring|carriere|carrieres|nous.rejoindre|join|talent)',
            re.IGNORECASE
        )

        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True).lower()
            href = a['href'].lower()
            if careerKeywords.search(text) or careerKeywords.search(href):
                careerUrl = urljoin(url, a['href'])
                if urlparse(careerUrl).scheme in ('http', 'https'):
                    return {
                        'name': startup['name'], 'url': url,
                        'career_url': careerUrl, 'career_source': 'lien homepage',
                    }

        for path in CAREER_PATHS:
            try:
                testUrl = urljoin(url, path)
                r = requests.head(testUrl, timeout=5, allow_redirects=True, headers={
                    'User-Agent': 'Mozilla/5.0 (compatible; JobBoardBot/1.0)'
                })
                if r.status_code == 200:
                    return {
                        'name': startup['name'], 'url': url,
                        'career_url': testUrl, 'career_source': f'chemin {path}',
                    }
            except Exception:
                continue

    except Exception:
        pass

    return None


def scanCareerPages(startups: list[dict]) -> list[dict]:
    print(f'Recherche de pages carrieres pour {len(startups)} startups...')
    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(findCareerPage, s): s for s in startups}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)

    print(f'{len(results)} pages carrieres trouvees')

    return results


def extractJobs(career: dict) -> dict:
    result = {**career, 'jobs': [], 'status': 'ok'}

    try:
        resp = requests.get(career['career_url'], timeout=TIMEOUT, headers={
            'User-Agent': 'Mozilla/5.0 (compatible; JobBoardBot/1.0)'
        })
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'lxml')

        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            if len(text) > 5 and len(text) < 200:
                jobUrl = urljoin(career['career_url'], a['href'])
                if urlparse(jobUrl).scheme in ('http', 'https'):
                    result['jobs'].append({'title': text, 'url': jobUrl})

    except Exception:
        result['status'] = 'fetch_error'

    return result


def classifyJob(title: str) -> str:
    title_lower = title.lower()
    categories = {
        'IA / ML / Data Science': r'(machine learning|deep learning|data scien|[^a-z]ml[^a-z]|[^a-z]ai[^a-z]|intelligence artificielle|nlp|computer vision|research)',
        'Dev / Engineering': r'(develop|engineer|fullstack|full.stack|backend|back.end|frontend|front.end|software|sre|devops|mobile|android|ios|golang|java[^s]|python|rust|c\+\+)',
        'Data': r'(data engineer|data analyst|analytics|bi[^a-z]|business intelligence|dba|database)',
        'Ops / Infra / QA': r'(ops|infra|cloud|sysadmin|qa[^a-z]|quality|test|securit|cyber|platform)',
        'Product / Design': r'(product|design|ux|ui[^a-z]|ergonome)',
        'Sales / Business': r'(sales|business|commercial|account|customer|client|bdm|bdr|sdr|partnership)',
        'Marketing / Growth': r'(marketing|growth|seo|content|community|brand|communication)',
        'Management / Leadership': r'(manager|director|directeur|head of|chief|vp[^a-z]|lead[^a-z]|responsable|cto|ceo|coo|cfo)',
        'RH / People': r'(rh[^a-z]|people|recruteu|talent|human)',
        'Stage / Alternance': r'(stage|stagiaire|intern|alternance|apprenti|working student)',
    }

    for category, pattern in categories.items():
        if re.search(pattern, title_lower):
            return category

    return 'Autre'


def scrapeJobs(careers: list[dict]) -> list[dict]:
    print(f'Extraction des offres depuis {len(careers)} pages carrieres...')
    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(extractJobs, c): c for c in careers}
        for future in as_completed(futures):
            results.append(future.result())

    return results


def jobKey(job: dict) -> str:
    raw = f'{job["startup"]}|{job["title"]}|{job["url"]}'

    return hashlib.md5(raw.encode()).hexdigest()


def loadCache() -> dict:
    if not CACHE_PATH.exists():
        return {}

    with open(CACHE_PATH, encoding='utf-8') as f:
        return json.load(f)


def saveCache(cache: dict) -> None:
    DATA.mkdir(exist_ok=True)
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def callLlm(titles: str) -> str:
    prompt = f"""Voici une liste de textes extraits de pages carrieres de startups.
Pour chacun, reponds UNIQUEMENT avec le numero suivi de:
- "OUI | Categorie" si c'est une vraie offre d'emploi (CDI, CDD, stage, alternance, freelance)
- "NON" si ce n'est PAS une offre (lien de navigation, mention legale, nom de page, description produit, etc.)

Categories possibles: IA / ML / Data Science, Dev / Engineering, Data, Ops / Infra / QA, Product / Design, Sales / Business, Marketing / Growth, Management / Leadership, RH / People, Stage / Alternance, Autre

{titles}"""

    resp = requests.post(OLLAMA_API_URL, timeout=60, headers={
        'Authorization': f'Bearer {OLLAMA_API_KEY}',
        'Content-Type': 'application/json',
    }, json={
        'model': OLLAMA_MODEL,
        'messages': [{'role': 'user', 'content': prompt}],
        'stream': False,
    })
    resp.raise_for_status()

    return resp.json()['message']['content']


def validateJobsWithLlm(jobs: list[dict]) -> list[dict]:
    cache = loadCache()
    now = datetime.now(timezone.utc).isoformat()
    currentKeys = set()
    validated = []
    toValidate = []

    for job in jobs:
        key = jobKey(job)
        currentKeys.add(key)

        if key in cache:
            entry = cache[key]
            entry['last_seen'] = now
            entry['missed_runs'] = 0
            if entry['is_job']:
                job['category'] = entry.get('category', job['category'])
                validated.append(job)
            continue

        toValidate.append((key, job))

    print(f'  Cache: {len(jobs) - len(toValidate)} deja connues, {len(toValidate)} nouvelles')

    if not OLLAMA_API_KEY:
        if toValidate:
            print('  OLLAMA_API_KEY absente, nouvelles offres gardees sans validation')
            validated.extend(job for _, job in toValidate)
        saveCache(cache)

        return validated

    if toValidate:
        print(f'  Validation LLM de {len(toValidate)} nouvelles offres...')

    for i in range(0, len(toValidate), LLM_BATCH_SIZE):
        batch = toValidate[i:i + LLM_BATCH_SIZE]
        titles = '\n'.join(
            f'{idx}. [{job["startup"]}] {job["title"]}'
            for idx, (_, job) in enumerate(batch)
        )

        try:
            answer = callLlm(titles)

            for line in answer.strip().split('\n'):
                match = re.match(r'(\d+)\.\s*(OUI|NON)(?:\s*\|\s*(.+))?', line.strip())
                if not match:
                    continue
                idx = int(match.group(1))
                if idx >= len(batch):
                    continue
                isJob = match.group(2) == 'OUI'
                category = (match.group(3) or '').strip()
                key, job = batch[idx]

                cache[key] = {
                    'is_job': isJob,
                    'category': category if isJob else '',
                    'title': job['title'],
                    'startup': job['startup'],
                    'first_seen': now,
                    'last_seen': now,
                    'missed_runs': 0,
                }

                if isJob:
                    if category:
                        job['category'] = category
                    validated.append(job)

        except Exception as e:
            print(f'  Erreur LLM batch {i}: {e}, fallback regex')
            for key, job in batch:
                cache[key] = {
                    'is_job': True, 'category': job['category'],
                    'title': job['title'], 'startup': job['startup'],
                    'first_seen': now, 'last_seen': now, 'missed_runs': 0,
                }
                validated.append(job)

    expired = []
    for key, entry in cache.items():
        if key not in currentKeys:
            entry['missed_runs'] = entry.get('missed_runs', 0) + 1
            if entry['missed_runs'] >= MAX_MISSED_RUNS:
                expired.append(key)

    for key in expired:
        del cache[key]

    if expired:
        print(f'  {len(expired)} offres expirees supprimees du cache')

    saveCache(cache)
    print(f'  {len(validated)} offres validees, {len(cache)} en cache')

    return validated


def buildJobsList(jobsRaw: list[dict], aiCoreMap: dict) -> list[dict]:
    jobs = []
    for entry in jobsRaw:
        startup = entry['name']
        info = aiCoreMap.get(startup, {})
        for job in entry.get('jobs', []):
            jobs.append({
                'category': classifyJob(job['title']),
                'startup': startup,
                'tier': info.get('tier', '?'),
                'region': info.get('region', ''),
                'title': job['title'],
                'url': job['url'],
                'tech': ', '.join(info.get('web_signals', [])),
                'startup_url': info.get('url', ''),
            })

    return jobs


def saveResults(scrapeResults: list[dict], aiCore: list[dict],
                careers: list[dict], jobsRaw: list[dict],
                jobs: list[dict]) -> None:
    DATA.mkdir(exist_ok=True)

    with open(DATA / 'scrape_results.json', 'w', encoding='utf-8') as f:
        json.dump(scrapeResults, f, ensure_ascii=False, indent=2)

    with open(DATA / 'ai_core.tsv', 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter='\t')
        w.writerow(['Tier', 'Score', 'Nom', 'URL', 'Annee', 'Region', 'Tech detectee sur le site', 'Description'])
        for s in aiCore:
            signals = [sig.split(' ', 1)[1] for sig in s.get('web_signals', []) if sig.startswith('+')]
            w.writerow([s['tier'], s['web_score'], s['name'], s['url'],
                        s['year'], s['region'], ', '.join(signals), s['desc']])

    with open(DATA / 'career_scan.json', 'w', encoding='utf-8') as f:
        json.dump(careers, f, ensure_ascii=False, indent=2)

    with open(DATA / 'jobs_raw.json', 'w', encoding='utf-8') as f:
        json.dump(jobsRaw, f, ensure_ascii=False, indent=2)

    with open(DATA / 'offres_emploi.tsv', 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter='\t')
        w.writerow(['Categorie', 'Startup', 'Tier', 'Region', 'Titre du poste', 'Lien offre', 'Tech startup', 'Site startup'])
        for j in jobs:
            w.writerow([j['category'], j['startup'], j['tier'], j['region'],
                        j['title'], j['url'], j['tech'], j['startup_url']])

    print(f'Resultats sauvegardes dans {DATA}/')
    print(f'  {len(scrapeResults)} startups analysees')
    print(f'  {len(aiCore)} startups IA core (A+B)')
    print(f'  {len(careers)} pages carrieres')
    print(f'  {len(jobs)} offres d\'emploi')


def main():
    sourcePath = ROOT / 'source.html'
    if not sourcePath.exists():
        print(f'Erreur: {sourcePath} introuvable')
        sys.exit(1)

    print('1/5 Extraction des startups depuis source.html...')
    startups = extractStartups(sourcePath)
    print(f'  {len(startups)} startups extraites')

    print('2/5 Scraping des sites web pour signaux IA...')
    scrapeResults = classifyStartups(startups)
    aiCore = [s for s in scrapeResults if s['tier'] in ('A', 'B')]
    print(f'  {len(aiCore)} startups IA core (A+B)')

    print('3/5 Recherche des pages carrieres...')
    careers = scanCareerPages(aiCore)

    print('4/5 Extraction des offres d\'emploi...')
    jobsRaw = scrapeJobs(careers)

    aiCoreMap = {s['name']: s for s in aiCore}
    jobs = buildJobsList(jobsRaw, aiCoreMap)
    print(f'  {len(jobs)} offres extraites')

    print('5/6 Validation LLM des offres...')
    jobs = validateJobsWithLlm(jobs)

    print('6/6 Sauvegarde...')
    saveResults(scrapeResults, aiCore, careers, jobsRaw, jobs)


if __name__ == '__main__':
    main()

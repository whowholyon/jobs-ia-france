# Projet Job Board IA France

## Ce qu'on a fait

### 1. Extraction des données source

- Fichier `source.html` (2 Mo) : export HTML d'un annuaire French Tech, ~800 startups
- Extraction des métadonnées : nom, URL, année, région, description, niveau IA déclaré
- 3 niveaux IA déclarés par les startups :
  - "L'IA est indispensable au fonctionnement de mon produit" (581)
  - "J'ai intégré l'IA pour améliorer mon produit" (171)
  - "Mon produit sert au développement ou à la gestion de l'IA" (48)

### 2. Classification IA "vraie" vs "wrapper API"

**Première passe — analyse des descriptions** (mots-clés)
- Résultat : seulement 20% classifiables, 561 indéterminées (descriptions trop marketing)

**Deuxième passe — scraping des 800 sites web**
- 763 sites accessibles sur 800 (en 38 secondes, 20 threads parallèles)
- Détection de mots-clés techniques sur les sites : pytorch, tensorflow, machine learning, computer vision, fine-tuning, PhD, etc.
- Détection de signaux "wrapper" : no-code, chatbot, zapier, "assisté par IA", etc.
- Score combiné (description + site web) pour chaque startup

**Résultat final :**

| Catégorie | Nb | Description |
|---|---|---|
| A - IA core confirmée | 67 | Techno propre détectée sur le site (PyTorch, TensorFlow, training...) |
| B - IA core probable | 83 | Signaux modérés (ML, modèles, LiDAR...) |
| C - Signaux modérés | 181 | Quelques indices sans certitude |
| D - Indéterminé | 412 | Rien de technique trouvé |
| E - Intégrateur probable | 45 | Zapier, no-code, chatbot... |
| F - Wrapper quasi certain | 12 | Cumul de signaux wrapper |

### 3. Scraping des offres d'emploi

**Étape 1 — trouver les pages carrières des 150 startups IA core (A+B)**
- 105 pages carrières trouvées sur 150
- Sources : liens sur la homepage (76), liens externes type WTTJ (14), chemins classiques /careers /jobs /recrutement (15)

**Étape 2 — extraction des offres**
- 706 offres extraites de 101 startups
- Classification par catégorie (regex sur les titres)

| Catégorie | Nb offres |
|---|---|
| Autre | 167 |
| Management / Leadership | 109 |
| Dev / Engineering | 107 |
| Sales / Business | 85 |
| IA / ML / Data Science | 66 |
| Product / Design | 54 |
| Ops / Infra / QA | 48 |
| Stage / Alternance | 24 |
| Marketing / Growth | 21 |
| Data | 16 |
| RH / People | 9 |

**Top recruteurs :** crunch dao (45), Lucky cart (33), Akur8 (25), Ai For Alpha (17), Adaptive ML (16)

### 4. Publication

- Offres postées sur paste.rs en 2 parties :
  - Partie 1 : https://paste.rs/nRA5P
  - Partie 2 : https://paste.rs/uGxdL

## Fichiers générés

| Fichier | Contenu |
|---|---|
| `source.html` | HTML brut source (800 startups) |
| `startups.tsv` | Liste simple des 800 startups |
| `scrape_results.json` | Résultats complets du scraping des sites web |
| `startups_analyse.tsv` | Classification v1 (description seule) |
| `startups_analyse_v2.tsv` | Classification v2 (description + scraping site web) |
| `ai_core.tsv` | 150 startups IA core (tier A+B) avec tech détectée |
| `career_scan.json` | URLs des pages carrières trouvées |
| `jobs_raw.json` | Données brutes des offres extraites |
| `offres_emploi_ia_core.tsv` | 706 offres détaillées (catégorie, startup, titre, lien, région) |
| `recrutement_ia_core.tsv` | Résumé recrutement par startup |

## Architecture cible

### Stack (coût total ~8€/an = un domaine)

- **Scraper Python** — ce qu'on a déjà, à nettoyer et structurer
- **GitHub Actions** — cron gratuit, exécute le scraper toutes les 6h sur une VM Ubuntu
- **GitHub Pages** — héberge le site statique gratuitement (HTTPS + CDN inclus)
- **Domaine custom** — optionnel, ~8€/an (OVH, Gandi, Cloudflare Registrar)

### Flux automatique

```
GitHub Actions (toutes les 6h)
  1. Démarre une VM Ubuntu
  2. Clone le repo
  3. Installe Python, lance scrape.py
  4. scrape.py va sur les 150 sites, récupère les offres
  5. Appelle Ollama Cloud API pour classifier/enrichir les offres
  6. Génère les fichiers HTML dans site/
  7. git commit + git push
  8. GitHub Pages publie automatiquement
  9. La VM s'éteint
```

Rien ne tourne en local. Le repo GitHub est le serveur. GitHub Actions est le cron. GitHub Pages est l'hébergement.

### Structure du repo envisagée

```
├── scraper/
│   ├── scrape.py              ← script principal
│   └── startups.json          ← liste des startups à surveiller
├── .github/workflows/
│   └── build.yml              ← cron GitHub Actions
└── site/                      ← GÉNÉRÉ automatiquement
    ├── index.html             ← toutes les offres
    ├── ia-ml/index.html       ← offres IA / ML / Data Science
    ├── dev/index.html         ← offres Dev / Engineering
    ├── product/index.html     ← offres Product / Design
    ├── sales/index.html       ← offres Sales / Business
    ├── stages/index.html      ← stages et alternances
    ├── startup/picsellia/     ← page par startup
    ├── region/bretagne/       ← page par région
    ├── tech/pytorch/          ← page par techno
    ├── feed.xml               ← flux RSS
    └── sitemap.xml            ← SEO
```

GitHub Pages sert n'importe quel fichier HTML du repo. Autant de sous-pages que voulu.

### Enrichissement LLM via Ollama Cloud

**Ollama Cloud** (https://ollama.com/cloud) :
- API compatible OpenAI (même format de requêtes)
- Tier gratuit disponible (usage léger)
- Pro à 20$/mois (largement suffisant)
- Clé API stockée dans GitHub Secrets (chiffré, jamais dans le code)

**Ce que le LLM peut faire :**
- Classifier les offres mieux que les regex (junior/senior, remote/onsite, type de contrat)
- Résumer les descriptions de poste en 1-2 lignes
- Scorer l'attractivité (salaire, stack, avantages)
- Détecter les doublons entre les runs
- Tagger les technos mentionnées (Python, PyTorch, React...)
- Traduire les offres en/fr

**Exemple d'appel :**
```python
import requests

response = requests.post('https://api.ollama.com/v1/chat/completions',
    headers={'Authorization': f'Bearer {OLLAMA_API_KEY}'},
    json={
        'model': 'llama3.3',
        'messages': [{'role': 'user', 'content': f'Classifie cette offre: {job_title} chez {startup}...'}]
    })
```

### Domaine custom

1. Acheter un domaine (~8€/an)
2. CNAME DNS → `tonpseudo.github.io`
3. Déclarer dans GitHub Pages settings
4. HTTPS automatique (Let's Encrypt)
5. Résultat : `https://jobs-ia.fr` (ou autre)

## Limites connues

- **561 startups indéterminées** : descriptions trop vagues, sites marketing sans détail technique
- **Sites full-JS (React SPA)** : le scraper simple ne rend pas le JS → certaines offres manquées
- **Plateformes externes** (Welcome to the Jungle, Lever, Greenhouse) : le lien est détecté mais les offres individuelles pas toujours extraites
- **Catégorie "Autre" (167 offres)** : titres non standard que le classifieur regex n'a pas reconnu → le LLM résoudra ça
- Pour aller plus loin sur la classification des startups : scraper les pages "About/Tech/Team", analyser les profils LinkedIn des fondateurs, croiser avec des bases brevets

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

French AI startup job board — scrapes career pages from startups classified as "real AI" companies (not just API wrappers), and publishes job offers as a static site.

## Data Pipeline

1. **source.html** — Raw HTML export (~800 startups from a French Tech directory)
2. **Python scraper** — Extracts startup metadata, scrapes their websites for AI/ML tech signals, scores and classifies them into tiers (A = confirmed AI core, B = probable AI core)
3. **Career scraper** — Finds career pages (homepage links, common paths like /careers, /jobs, /recrutement), extracts job listings
4. **Static site generator** — Builds an HTML page from the job data

## Key Data Files

- `ai_core.tsv` — 150 tier A+B startups with tech signals detected on their websites
- `offres_emploi_ia_core.tsv` — Job offers (706) with category, startup, region, link
- `scrape_results.json` — Full scrape results with web scores for all 800 startups
- `career_scan.json` — Career page URLs found for each startup
- `jobs_raw.json` — Raw extracted job data

## Classification System

Startups are scored by combining description keywords + website scraping for tech signals:
- **Positive signals**: pytorch, tensorflow, machine learning, computer vision, fine-tuning, PhD, etc.
- **Negative signals**: no-code, chatbot, zapier, "assisté par IA", etc.
- **Tier A** (score >= 8): confirmed AI core tech
- **Tier B** (score 4-7): probable AI core tech

## Target Architecture

GitHub Actions cron (every 6h) → Python scraper → static HTML generation → GitHub Pages deployment.

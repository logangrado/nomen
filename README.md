# Nomen

A data-driven baby name discovery app for two people trying to find names they
both like. Not a swipe app — a *data* app.

## What it is

- A **queryable name database** with frequency data by year, region, and gender
- A **collaborative rating system** (love / like / dislike / hate per user)
- A tool for discovering names from multiple countries and cultures — with a
  particular focus on Eastern European / Slavic names

## What it is not

A swipe app with confetti animations. Baby names is serious business.

## Architecture

See [`docs/architecture.md`](docs/architecture.md) for the full ADR covering:
- Database choice (DuckDB)
- Schema design (multi-country, multi-script)
- Data sources (SSA, Polish GUS, Czech ČSÚ, Behind the Name, ...)
- Build phases (pipeline → CLI → web UI → ML)

## Status

Early stage — pipeline and schema work in progress.

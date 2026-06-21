# Task: init-nomen

**Status**: complete
**Branch**: hatchery/init-nomen
**Created**: 2026-06-21 14:25

## Objective

Build a data-driven baby-name discovery app that helps two people find names they
both like. Not a swipe app — a *data* app. Core capabilities: rich name database
(frequency by year/region/gender), collaborative rating (love/like/dislike/hate),
and eventually ML-assisted clustering and recommendation.

## Context

Two people need to converge on a baby name. The problem is that most name tools
are either pure vibes (swipe apps with confetti) or reference-only (just look up
meanings). What's missing is a *queryable, filterable database* of names with
real frequency data, so you can answer questions like:

- "Show me girl names that were popular in Poland in the 1990s but rare in the US"
- "What names peaked between 2005–2015 and are now declining?"
- "Give me Eastern European names with a similar feel to Katerina"

The user's wife has an Eastern European name (Katerina), so Slavic name coverage
is a first-class concern — not an afterthought.

## Summary

ADR promoted to `docs/architecture.md`. See that file for the full record:
schema, data sources, build phases, and implementation notes.

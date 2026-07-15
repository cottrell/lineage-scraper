---
id: task-9
title: >-
  Evaluate WAF bypass/fallback for ShieldSquare-protected targets (e.g.,
  dmo.gov.uk)
status: Done
assignee: []
created_date: '2025-12-17 13:49'
updated_date: '2025-12-17 16:31'
labels:
  - crawler
  - discussion
  - dependency
dependencies: []
priority: medium
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`https://www.dmo.gov.uk/data` responds with ShieldSquare block/CAPTCHA, so the crawler finds zero links. Past work (see ~/projects/notebooks/my-gym/toplevelrepo/our/our/extractors/dmo/scrape_util.py) used `cloudscraper` with browser-like headers to fetch `XmlDataReport` and `DataExport` endpoints. Decide whether to add an optional/fallback fetch path (e.g., `cloudscraper` or similar) when we hit bot defenses, and how to expose/guard it (config flag, ethics/legal considerations, caching, robots.txt handling). Outcome should be a recommendation or minimal implementation plan; avoid defaulting to new deps without justification. If approved, document how to supply headers/cookies and how this interacts with existing rate limiting/cache.
<!-- SECTION:DESCRIPTION:END -->

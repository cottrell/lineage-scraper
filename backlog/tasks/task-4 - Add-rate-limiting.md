---
id: task-4
title: Add rate limiting
status: Done
assignee: []
created_date: '2025-12-16 23:17'
updated_date: '2025-12-17 16:31'
labels:
  - enhancement
  - crawler
dependencies: []
priority: medium
ordinal: 8000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Implement configurable rate limiting to avoid being blocked.

Options:
- --delay: seconds between requests (default: 0.5)
- --concurrent: max concurrent requests (default: 1)

Respect Crawl-delay in robots.txt if present.
<!-- SECTION:DESCRIPTION:END -->

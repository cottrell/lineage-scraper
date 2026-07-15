---
id: task-2
title: Add sitemap.xml discovery
status: Done
assignee: []
created_date: '2025-12-16 23:17'
updated_date: '2025-12-17 16:31'
labels:
  - enhancement
  - discovery
dependencies: []
priority: medium
ordinal: 10000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Check robots.txt for sitemap.xml and parse sitemaps to find data file URLs.

Benefit: Direct access to URLs the site wants indexed, without extensive crawling.

Implementation:
- Fetch /robots.txt at start of crawl
- Parse Sitemap: directives
- Fetch and parse sitemap.xml files
- Add discovered URLs to crawl queue
<!-- SECTION:DESCRIPTION:END -->

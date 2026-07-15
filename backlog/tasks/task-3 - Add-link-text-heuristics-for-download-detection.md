---
id: task-3
title: Add link text heuristics for download detection
status: Done
assignee: []
created_date: '2025-12-16 23:17'
updated_date: '2025-12-17 16:31'
labels:
  - enhancement
  - discovery
dependencies: []
priority: medium
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Improve discovery by analyzing link text and attributes.

Look for:
- Link text containing "Download", "Export", "CSV", "Excel", etc.
- HTML5 download attribute: <a download="file.csv">
- Data-* attributes that suggest file downloads

This catches download buttons that dont have file extensions in URLs.
<!-- SECTION:DESCRIPTION:END -->

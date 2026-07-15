---
id: task-1
title: Add Content-Type sniffing via HEAD requests
status: Done
assignee: []
created_date: '2025-12-16 23:17'
updated_date: '2025-12-17 16:31'
labels:
  - enhancement
  - discovery
dependencies: []
priority: high
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Instead of relying solely on URL extensions, use HEAD requests to check Content-Type header.

This catches:
- URLs without extensions
- Misleading extensions
- API endpoints that return data files

Implementation:
- For candidate URLs, issue HEAD request
- Check Content-Type header (text/csv, application/json, etc.)
- Fall back to extension detection if HEAD fails
<!-- SECTION:DESCRIPTION:END -->

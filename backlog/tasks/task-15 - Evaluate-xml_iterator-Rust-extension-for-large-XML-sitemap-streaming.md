---
id: task-15
title: Evaluate xml_iterator Rust extension for large XML sitemap streaming
status: To Do
assignee: ""
labels:
  - enhancement
  - performance
dependencies: []
created_date: "2026-09-13"
---

## Description
Consider integrating `xml_iterator` (local toolbox at `~/dev/xml_iterator` or `~/projects/notebooks/my-gym/toplevelrepo/our/our/extractors/xml_iterator`) for parsing large XML sitemaps and feeds with stream-based Rust parsing and zero-copy JSON/dict conversion.

## Acceptance Criteria
- [ ] Evaluate memory/speed benefit of `xml_iterator` vs standard library XML parsing on massive sitemaps.

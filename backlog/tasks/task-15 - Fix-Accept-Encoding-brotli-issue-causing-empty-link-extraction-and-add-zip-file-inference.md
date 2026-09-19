---
id: TASK-15
title: >-
  Fix Accept-Encoding brotli issue causing empty link extraction and add zip
  file inference
status: Done
assignee: []
created_date: '2026-09-19 11:12'
updated_date: '2026-09-19 11:12'
labels: []
dependencies: []
ordinal: 12000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
DEFAULT_BROWSER_HEADERS specified Accept-Encoding: gzip, deflate, br, but httpx does not decompress brotli without the optional brotli package installed. When requesting sites like gov.uk that favor brotli compression, httpx returned raw binary bytes in resp.text, which failed _looks_like_html() and caused 0 links to be extracted and cached. Omitting Accept-Encoding lets httpx negotiate encodings it can decode automatically. Additionally, archive formats like .zip are common data download targets (e.g. Companies House bulk data) and should be recognized by infer_file_type.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 DEFAULT_BROWSER_HEADERS does not set Accept-Encoding, allowing HTTP client library to negotiate supported compression
- [x] #2 infer_file_type recognizes .zip, .tar, .gz, and .tgz archive files
- [x] #3 Tests pass covering infer_file_type archive extensions and default headers
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Remove Accept-Encoding from DEFAULT_BROWSER_HEADERS in lineage_scraper.py so httpx negotiates supported encodings.
2. Add archive formats (.zip, .tar, .gz, .tgz) to infer_file_type ext_map and patterns.
3. Add unit tests for header configuration and archive file type inference in tests/test_lineage_scraper.py.
4. Run pytest and verify end-to-end against live site or simulated responses.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Removed Accept-Encoding from DEFAULT_BROWSER_HEADERS in lineage_scraper.py. Added archive extensions (.zip, .tar, .gz, .tgz, .7z) to infer_file_type ext_map, regex patterns, and text heuristic. Added unit tests in tests/test_lineage_scraper.py (9/9 pass). Verified live extraction on gov.uk/guidance/companies-house-data-products (89 links found) and download.companieshouse.gov.uk/en_output.html (20 links, all zip/pdf files identified).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Fixed brotli compression failure by removing Accept-Encoding from default headers so httpx negotiates supported algorithms. Added archive format detection to infer_file_type. All tests pass.
<!-- SECTION:FINAL_SUMMARY:END -->

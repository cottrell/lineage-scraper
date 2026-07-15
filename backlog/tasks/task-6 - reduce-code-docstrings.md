---
id: task-6
title: 'reduce code, docstrings'
status: Done
assignee: []
created_date: '2025-12-17 11:18'
updated_date: '2025-12-17 16:31'
labels: []
dependencies: []
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
$ find src/ -name '*.py'| xargs wc
  156   473  5164 src/lineage_scraper/crawler/base.py
  218   581  7311 src/lineage_scraper/crawler/discovery.py
    6    18   169 src/lineage_scraper/crawler/__init__.py
  118   342  4141 src/lineage_scraper/storage/database.py
    5    12   120 src/lineage_scraper/storage/__init__.py
  182   466  6084 src/lineage_scraper/cli.py
    3    15   109 src/lineage_scraper/__init__.py
   73   177  2154 src/lineage_scraper/models/enums.py
   13    29   307 src/lineage_scraper/models/__init__.py
  123   346  3051 src/lineage_scraper/models/lineage.py
  897  2459 28610 total

doc says 200 lines.

def get_records(...)

is obvious and doesn't need doc strings surely? Do you require it in the linter?
<!-- SECTION:DESCRIPTION:END -->

---
id: task-14
title: Add local config for fetch headers/cookies per strategy
status: To Do
assignee: []
created_date: '2025-12-17 14:21'
labels:
  - config
  - fetcher
  - headers
dependencies: []
priority: medium
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Need a way to configure headers/cookies per fetch strategy (httpx/curl_cffi/cloudscraper) via a local config file (e.g., config.json) instead of code changes. Should allow merging user-provided headers/cookies with defaults, per-strategy or global. Consider path, format, precedence (CLI overrides config), and security/privacy guidance for storing cookies. Also note how this interacts with caching and rate limiting.
<!-- SECTION:DESCRIPTION:END -->

---
id: task-14
title: Add local config for fetch headers/cookies per strategy
status: Done
assignee: []
created_date: '2025-12-17 14:21'
updated_date: '2026-08-03 09:34'
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

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Implemented config.json loader with support for custom headers/cookies, precedence merging rules, security alerts, and comprehensive test coverage.
<!-- SECTION:FINAL_SUMMARY:END -->

---
id: task-11
title: Review rate limit params and communicate them better in the docs?
status: Done
assignee: []
created_date: '2025-12-17 14:04'
updated_date: '2025-12-17 16:31'
labels: []
dependencies: []
ordinal: 2000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Supposing the rate limit stuff is sane, we should make sure to document it a little better pointing at least to where it is.

Also the swarm cli param --delay is not specific enough!

It should at least be delay_seconds

But really it should tell us what that is for. is it delay_s_on_failure? delay_s_on_success?

Really rate limit means we actually TRACK how long it's been since the last call not merely delay all the time! So I'm not even sure that is correct anymore.
<!-- SECTION:DESCRIPTION:END -->

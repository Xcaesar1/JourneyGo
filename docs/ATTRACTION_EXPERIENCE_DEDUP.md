# Attraction experience deduplication

## Rules

- Keep POI identity separate from the planning experience group.
- Share `resolve_experience_groups` between discovery and the final planner.
- Resolve same-city parent chains from retained query evidence, including intermediate POIs across responses. Stop on cycles, missing parents, and city mismatches.
- Only inherit groups rooted in curated landmarks. An old-city parent must not merge independent temples.
- Prefer the verified main landmark for automatic recommendations. Explicit must-visits retain priority; conflicting required members pause planning.
- Apply exclusions to all resolved group aliases. Do not replace an excluded main attraction with one of its components.
- Similar names without verified group membership are a review signal, not a merge rule. Retain these candidates with an explanation, omit default selection and automatic scheduling, and allow explicit must-visit selection.
- Missing ancestry without a recognizable name is not automatically detectable. Add sourced rules only after checking the specific POI; do not infer containment from proximity.
- Never rewrite saved trips or issue extra supplier queries for deduplication.

## Lijiang regression evidence

The 2026-09-18 mobile candidate response contained these distinct POIs:

| POI | Name | Direct parent |
| --- | --- | --- |
| B0378008FA | 玉龙雪山国家级风景名胜区 | none |
| B0K6DS8TXV | 玉龙雪山观景湖 | B0HBXXU1MR |
| B037814YDS | 玉龙雪山国家级风景名胜区-玉液湖 | B0378157WA |
| B0FFFDR6FE | 玉龙雪山冰川博物馆 | B03780I3SU |

These are treated as one default visit allocation, not interchangeable POI identities or a fabricated combined attraction. Main-attraction selection does not promise every internal stop fits in a day. Rules and source links live in `backend/app/domain/landmarks.py`.

Do not generalize this rule to every museum or distant viewpoint with a mountain name. Review uncertain candidates separately.

## Verification

Run `python -m pytest backend/tests/test_landmark_planning.py backend/tests/test_attraction_discovery.py -q -o addopts=''`.

Cover actual mobile POI names and parent IDs, cross-query ancestry, cycles, cross-city links, independent temples, uncertain names, exclusions, must-visit conflicts, and one full-day allocation across the whole trip. Tests use mocks only.

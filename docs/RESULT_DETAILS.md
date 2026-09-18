# Result Detail Corrections (2026-09-18)

- Saved Shanghai itinerary inspection confirmed transfer rows already existed. Display
  enrichment uses their original timestamps and the saved origin/arrival/return station
  and hotel coordinates. It does not rewrite snapshots, add expenses or calculate new routes.
- One-click overview no longer exposes raw model `overall_suggestions`; structured
  logistics, visible planning notices and excluded costs remain. Classic plans retain it.
- Hotel photos from existing AMap POI responses survive non-attraction parsing. The
  overview and daily hotel cards display verified AMap images with source attribution.
  Legacy snapshots with empty images offer a manual existing-photo-endpoint lookup;
  non-AMap fallback images are not presented as hotel photos. No lookup runs automatically.
- Staging Wikipedia API returned missing pages for all three full POI names in the
  inspected itinerary, but returned the `博文女校` alias. Alias requests retain city
  validation, bounded excerpts and attribution. No article match is not a network failure.
- Staging personal-map creation is enabled persistently. Real Android Chrome
  confirmation and app-link handoff reused the existing map; see
  `AMAP_ENABLEMENT_HANDOFF.md`. No claim of free billing follows from success.
- The attraction map uses the standard light AMap basemap and a white container
  background, replacing the fixed dark-blue theme without changing routes or markers.
- Overview photos retain the original centered coverflow, hover selection and
  itinerary link. Only depth/overlap, spacing, rounded corners and shadow are
  softened; image-bottom waves are removed for a straight edge. The replacement grid, new card design and arrow controls
  are discarded; no gallery structure or interaction redesign is retained.
- Daily panels omit the redundant description/transport/accommodation summary and
  per-day validation pills. Timeline, navigation, hotel details and overview critical
  notices remain; saved snapshots and validation reports are not modified.
- Local fixture verification passed at 390/1440px and on the connected Android using
  native CDP touch events: station labels/navigation, disabled map explanation, explicit
  photo loading and no business POST. The real saved task was read only; the fixture tab
  was closed afterward. No real map was created or paid quote refreshed.

# Live Android Acceptance: 2026-09-17

## Outcome

Not passed end-to-end. A single real task paused at model POI selection. No
complete itinerary, final budget, result navigation or final approval was verified.

## Scope

- Existing authenticated Android Chrome tab on staging, not local mock preview.
- Shanghai to Xi'an, September 20-24, five days, one adult, one room,
  train/high-speed rail, business accommodation, CNY 10000 total.
- One UI submission returned HTTP 202. No duplicate submission/resume, paid
  flight call, booking, production deployment or quota change.
- Task: `task_d240621fd74f4d3e83ff`.

## Observed Results

- Outbound and return train requests succeeded and persisted.
- Hotel search, three room-detail requests and five AMap POI requests succeeded.
  These are query successes, not proof that the final selected itinerary is valid.
- The model place-selection record is `blocked`; task is `awaiting_input`,
  code `model_output`. The UI reports an incomplete planning result.
- Twelve query records persisted: eleven successful provider requests and one
  blocked model request. No synthetic results were substituted.
- Phone reload restored the pause, source query snapshots, origin/destination,
  travel dates, five days, budget and adult count. Continue was not clicked.

## Findings To Address

1. `travel_place_selection.select_places` hardcodes `max_tokens=4096`, while
   staging's structured-output budget is 32768. The `model_output` branch means
   either missing choices or `finish_reason=length`. The response/finish reason
   was not persisted, so truncation is suspected, not established. Add sanitized
   diagnostics and respect the configured budget before a controlled retry.
2. The pause incorrectly directs the user to adjust preferences for a model
   output failure. Distinguish service/model recovery from invalid user inputs.
   Same-input continuation currently reuses the blocked intent; recovery must
   not silently repeat successful transport/hotel queries or paid requests.
3. Android date selection summoned the keyboard. Text entry did not commit;
   automated click selection timed out. Dismissing the keyboard and sending a
   touch to the September 20 calendar cell succeeded. Verify a touch-friendly
   date/time picker without the software keyboard obscuring it.

Preserve this task and query evidence. Do not claim full live acceptance from
the earlier mocked tests or from successful supplier query responses alone.

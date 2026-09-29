# Test plan

Automated cases were run locally on 2026-09-29. Manual simulator, dashboard visual, physical hardware and cloud cases remain pending. Automated tests live under `tests/`.

| ID | Scenario / input | Expected result | Actual result | Status |
|---|---|---|---|---|
| T01 | Start simulator | Process produces synthetic samples | Not run | Pending |
| T02 | Generate one sample | Fields and ranges are valid | Not run | Pending |
| T03 | POST valid sample with demo key | 201 and record stored | Automated API run: accepted and retrievable | Pass |
| T04 | POST soil 140 | 422 validation error | User observed 422 with max-100 detail; automated case also passed | Pass |
| T05 | Ingest valid sample, query DB | Row exists | Automated API run: history contains inserted row | Pass |
| T06 | GET latest after ingest | Most recent record returned | Automated API run: latest returns inserted sample | Pass |
| T07 | GET history with limit | Chronological bounded list returned | Automated API run: one sample returned | Pass |
| T08 | Soil >= threshold | No automatic event | Automated API run: 55% sample recorded no watering event | Pass |
| T09 | Soil < threshold | Low-moisture alert created | Automated API run: warning alert created | Pass |
| T10 | Low soil with auto enabled/cooldown complete | Automatic event and pump pulse | Automated API run: event recorded and pump status ON | Pass |
| T11 | Simulator sees new event | Next virtual sample moisture rises | Not run | Pending |
| T12 | Pulse duration expires | pump_status becomes false | Automated API run: expired pulse reports OFF | Pass |
| T13 | Re-ingest during 2-minute cooldown | No repeat automatic event | Automated API run: second automatic event suppressed | Pass |
| T14 | Manual water for 3 seconds | Manual event recorded, virtual pulse visible | Automated API run: manual event and pump status ON | Pass |
| T15 | Ingest low reading | Alert appears | Automated API run: low-moisture alert present | Pass |
| T16 | Acknowledge open alert | Status becomes acknowledged | Automated API run: acknowledgement returned | Pass |
| T17 | Previously seen device misses 90 seconds | Offline status and one alert | Automated API run: offline state and alert appeared | Pass |
| T18 | New reading after outage | Online state and offline alert resolved | Automated API run: online status restored | Pass |
| T19 | Dashboard polling with saved samples | Cards and chart update | Not run | Pending |
| T20 | Database table unavailable | API returns 503 with safe error and logs failure type | Automated API run: 503 returned | Pass |
| T21 | API process unavailable to simulator | Error logged; next interval retries | Not run | Pending |
| T22 | Restart API / resume simulator | New post is attempted | Not run | Pending |
| T23 | Ingest with incorrect key | 401 response | Automated API run: unauthorized response | Pass |
| T24 | PUT threshold within range | Saved threshold returned | Automated API run: threshold updated | Pass |
| T25 | Register second device, send sample | Separate records by device ID | Automated API run: second device history isolated | Pass |
| T26 | Report tank at 10% or lower, then try both watering controls | Warning shown; automatic action suppressed and manual request rejected | Automated API test: alert raised, no event created, manual call returned 409; replenishment resolves alert | Pass |
| T27 | Save a daily watering time and ingest during that minute | One scheduled event is queued; a second reading that day does not repeat it; invalid time is rejected | Automated API test: one scheduled event created, repeated ingest did not duplicate it, invalid time returned 422 | Pass |
| T28 | Create plant without a custom threshold, apply another plant profile, then save a custom threshold | Profile defaults vary by plant; custom threshold remains supported | Automated API test: tomato default 40%, succulent profile 20%, custom value 30% | Pass |
| T29 | Submit the same device/timestamp reading twice | Duplicate returns HTTP 200 and does not create a second reading or watering action | Automated API test: one reading and one watering event persisted | Pass |
| T30 | Register/login/logout and access another account’s plant | Session authentication works; unauthenticated requests return 401; non-owner gets 404 | Automated API test: account isolation and session checks | Pass |
| T31 | Simulator reads device state/actions with API key | Valid key returns latest reading/action cursor; missing key gets 401 | Automated API test: state endpoint checks key and response shape | Pass |
| T32 | API unavailable, then returns | Queued simulator readings remain on disk after failure and are removed after successful upload | Automated test: failed send retained the row; successful retry sent it once and emptied the queue | Pass |
| T33 | Back up and restore SQLite | Backup is consistent; restore verifies integrity and refuses to overwrite a destination | Automated test: restored row matched source; existing destination was preserved | Pass |

Test environment: Python 3.14.7, dependencies in `requirements.txt`, local SQLite. Latest run: 31 passed on 2026-09-29. Manual simulator retry, moisture feedback loop, dashboard visual behavior, physical hardware, live PostgreSQL and cloud deployment still need separate verification.

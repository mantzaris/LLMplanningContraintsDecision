# Public schedules and constructed research data

The primary source is the agency's [GTFS download page](https://developer.trimet.org/GTFS.shtml),
using its published ZIP over HTTPS. The frozen feed has SHA-256
`82e6b822de008367b3d3d35bb52545807ea41b6f56623a9aa4b1162b3d54671b`.
See the [acquisition manifest](../data/manifests/trimet-82e6b822de008367b3d3d35bb52545807ea41b6f56623a9aa4b1162b3d54671b.json)
for timestamps, bytes, source and validity fields. The manual bootstrap download
was imported using its original completion mtime; normal acquisition records HTTP
ETag/Last-Modified when provided. No substitute agency was needed.

Feed version `20260823-20260910-0900` declares 2026-08-23 through 2027-02-27.
The actual calendar table spans only 2026-08-23 through 2026-11-28 and exceptions
through 2026-11-27. A feed-info range does not imply service on every day; the
implementation always evaluates calendars and exceptions for the chosen day.
Agencies declare `America/Los_Angeles`. The planning day is Monday 2026-09-14,
07:00–10:00 service time, within the populated calendar. No realtime feed is used.

Before observing any model output, [data.json](../configs/data.json) fixed a downtown
bbox (45.50–45.54 latitude, −122.69–−122.64 longitude), three routes, at most two
boardings per segment and a conservative 120-second same-stop connection minimum.
The busiest eligible route starts selection; subsequent routes maximize overlap
in exact stop IDs, then trip coverage, then stable route ID. The resulting connected
route subset is **2, 4, 17**, all buses, with 70 named calls/stops and 6,574 ride edges.
The mode-language logic is additionally tested with synthetic multimodal fixtures;
this feed subset alone does not validate multimodal behavior empirically.

Enumerate all supported paths up to two rides for each public segment, sort by
content hash, keep at most 64, then combine segments and retain at most 256 joint
journeys by ID. Counts and truncation flags are in the [preparation manifest](../data/manifests/preparation.json).
This deterministic pool samples timing alternatives. Every solver result and
equivalence statement is conditional on it, even though pre-truncation enumeration
completes within the declared ride bound. The bound is infrastructure metadata,
not the user's transfer preference. Reference and predicted constraints never
prune candidate generation.

The parser follows the [GTFS schedule reference](https://gtfs.org/documentation/schedule/reference/):
it applies weekday calendars with add/remove exceptions; retains string stop/trip
identities; sorts numeric stop sequences; uses agency time zones; and parses times
beyond 24:00 without wrapping. Absolute conversion uses local noon minus twelve
elapsed hours as the service-day origin, including DST transitions. Every intermediate
scheduled call remains in a ride, even outside the boarding/alighting bbox.
Missing stop times exclude a trip with an exclusion count; no interpolation is
invented. Duplicate sequences or nonmonotone times fail explicitly. Pickup/drop-off
restrictions limit boardings/alightings. Frequency-based trips are excluded.

Connections are only between identical stop IDs and different trips. Applicable
same-stop transfer prohibitions/minimum times are honored with route/trip specificity.
Timed/guaranteed transfers and in-seat rules are excluded conservatively. Different-stop
walking transfers, parent-station/platform equivalence, pathways, block-based
through-service, GTFS-flex, fares, capacity and accessibility guarantees are outside
scope. We do not treat a shared block as permission to stay aboard. Multiple agency
time zones in one universe are explicitly unsupported. Multi-segment requests specify
their own endpoints; any external movement/activity between segments is expressly
outside the transport task, not an invented walking connection.

## Provenance categories and reuse

| Material | Provenance | Location |
|---|---|---|
| Infrastructure and scheduled services | Published TriMet GTFS; not observed movements | Local `data/raw/`, `data/prepared/public/pools/` |
| Constructed requests | Assistant-authored deterministic templates; not passenger requests | [requests.json](../data/development/requests.json) |
| Textual variants | Assistant-authored prefix variation; not diverse generated paraphrases | Same request file, paired `p0/p1` IDs |
| Reference annotations | Independently specified rule dictionaries, provisional and unaudited | [provisional.json](../data/references/provisional.json) |
| Human-review worksheet | Blank reviewer/correction fields; no human audit claimed | [annotation-review.csv](../data/references/annotation-review.csv) |
| Injected errors | Explicit synthetic fixture interpretations and scripted judgments | `tests/`, separate diagnostic command |
| Natural errors | Actual model translations, judged after inference using separate annotations | Local immutable run artifacts |

The [TriMet developer terms](https://developer.trimet.org/terms_of_use.shtml) govern
the feed. Their content-use and redistribution provisions distinguish website
content from registered web-service API data; the ZIP should not be assumed to
inherit an unrestricted open-data license. Therefore this repository commits
acquisition code, provenance, constructed requests/annotations and aggregate audit
metrics, but **does not redistribute raw feeds, journey schedules or full model
prompts containing schedules**. This unofficial project is not endorsed by TriMet.
Repository MIT licensing applies to project code, not agency content.

The exact ZIP is retained locally under its checksum; the public download endpoint
is mutable and does not guarantee future availability of that historical version.
For exact reproduction use the already frozen file and verify the manifest hash.
If only a newer download is available, explicitly create a new versioned data
configuration and run, rather than silently calling it the same dataset. Obtain
appropriate rights before publishing a frozen schedule archive. Replay can use
saved local run inputs and model outputs without the original ZIP or GPU.

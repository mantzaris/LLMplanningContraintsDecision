| ID | Family | Wording / time / scope | Visits | DSL | Feasible / pool | Issue |
| --- | --- | --- | --- | --- | --- | --- |
| pilot-00 | timing | Agree | — | Supported | 11/64 | None identified |
| pilot-01 | mode_exclusion | Agree | — | Supported | 4/64 | None identified |
| pilot-02 | ordered_visits | Agree | Agree | Supported | 64/64 | None identified |
| pilot-03 | transfers | Agree | — | Supported | 1/64 | None identified |
| pilot-04 | scope | Agree | — | Supported | 141/256 | None identified |
| pilot-05 | infeasible | Agree | — | Supported | 0/64 | None identified |
| pilot-06 | mode_exclusion | Agree | — | Supported | 35/64 | None identified |
| pilot-07 | ordered_visits | Agree | Agree | Supported | 64/64 | None identified |
| pilot-08 | timing | Agree | — | Supported | 18/64 | None identified |
| pilot-09 | scope | Agree | — | Supported | 18/256 | None identified |
| pilot-10 | infeasible | Agree | — | Supported | 0/64 | None identified |
| pilot-11 | transfers | Agree | — | Supported | 64/64 | None identified |
| pilot-12 | ordered_visits | Agree | Agree | Supported | 64/64 | None identified |
| pilot-13 | timing | Agree | — | Supported | 5/64 | None identified |
| pilot-14 | mode_exclusion | Agree | — | Supported | 22/64 | None identified |
| pilot-15 | infeasible | Agree | — | Supported | 0/64 | None identified |
| pilot-16 | transfers | Agree | — | Supported | 6/57 | None identified |
| pilot-17 | scope | Agree | — | Supported | 31/256 | None identified |
| pilot-18 | timing | Agree | — | Supported | 17/64 | None identified |
| pilot-19 | mode_exclusion | Agree | — | Supported | 45/64 | None identified |
| pilot-20 | ordered_visits | Agree | Agree | Supported | 64/64 | None identified |
| pilot-21 | transfers | Agree | — | Supported | 17/17 | None identified |
| pilot-22 | scope | Agree | — | Supported | 256/256 | None identified |
| pilot-23 | infeasible | Agree | — | Supported | 0/64 | None identified |
| pilot-24 | mode_exclusion | Agree | — | Supported | 14/64 | None identified |
| pilot-25 | ordered_visits | Agree | Agree | Supported | 64/64 | None identified |
| pilot-26 | timing | Agree | — | Supported | 35/51 | None identified |
| pilot-27 | scope | Agree | — | Supported | 35/256 | None identified |
| pilot-28 | infeasible | Agree | — | Supported | 0/64 | None identified |
| pilot-29 | transfers | Agree | — | Supported | 2/64 | None identified |
| pilot-30 | ordered_visits | Agree | Agree | Supported | 31/64 | None identified |
| pilot-31 | timing | Agree | — | Supported | 4/64 | None identified |
| pilot-32 | mode_exclusion | Agree | — | Supported | 30/45 | None identified |
| pilot-33 | infeasible | Agree | — | Supported | 0/64 | None identified |
| pilot-34 | transfers | Agree | — | Supported | 13/64 | None identified |
| pilot-35 | scope | Agree | — | Supported | 168/256 | None identified |
| pilot-36 | timing | Agree | — | Supported | 18/64 | None identified |
| pilot-37 | mode_exclusion | Agree | — | Supported | 59/64 | None identified |
| pilot-38 | ordered_visits | Agree | Agree | Supported | 25/25 | None identified |
| pilot-39 | transfers | Agree | — | Supported | 2/64 | None identified |
| pilot-40 | scope | Agree | — | Supported | 256/256 | None identified |
| pilot-41 | infeasible | Agree | — | Supported | 0/25 | None identified |
| pilot-42 | mode_exclusion | Agree | — | Supported | 28/64 | None identified |
| pilot-43 | ordered_visits | Agree | Agree | Supported | 64/64 | None identified |
| pilot-44 | timing | Agree | — | Supported | 9/25 | None identified |
| pilot-45 | scope | Agree | — | Supported | 204/256 | None identified |
| pilot-46 | infeasible | Agree | — | Supported | 0/64 | None identified |
| pilot-47 | transfers | Agree | — | Supported | 16/25 | None identified |

| Constraint | Separates | Always true | Always false | Duplicates* | Zero marginal* | Unsupported |
| --- | --- | --- | --- | --- | --- | --- |
| earliest_departure | 22 | 7 | 0 | 4 | 7 | 0 |
| latest_departure | 8 | 0 | 0 | 0 | 0 | 0 |
| latest_arrival | 13 | 0 | 0 | 0 | 0 | 0 |
| transfer_limit | 6 | 18 | 0 | 11 | 18 | 0 |
| allowed_modes | 0 | 8 | 0 | 7 | 8 | 0 |
| forbidden_modes | 0 | 8 | 3 | 7 | 8 | 0 |
| ordered_calls | 1 | 7 | 0 | 7 | 7 | 0 |

| GTFS mode | Source routes | Active trips | Trips with morning call | BBox-eligible routes | Selected routes |
| --- | --- | --- | --- | --- | --- |
| bus | 71 | 4727 | 1105 | 24 | 3 |
| gondola | 1 | 384 | 74 | 0 | 0 |
| rail | 1 | 20 | 7 | 0 | 0 |
| tram | 8 | 1022 | 204 | 7 | 0 |

| Method | Budget | Original = rescored | Valid plan | Invalid plan | Correct infeas. | False infeas. | Invalid output | Unresolved / infra |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A | 0 | 31/48 | 28 | 5 | 3 | 6 | 6 | 0 |
| D = E | 0 | 31/48 | 28 | 5 | 3 | 7 | 5 | 0 |
| D = E | 1 | 33/48 | 30 | 5 | 3 | 5 | 5 | 0 |
| D = E | 2 | 33/48 | 30 | 5 | 3 | 5 | 5 | 0 |
| D = E | 4 | 33/48 | 30 | 5 | 3 | 5 | 5 | 0 |

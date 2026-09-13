# Stage 3 oracle narrative correction — 13 September 2026

This corrects one explanatory sentence in the preserved [Stage 3 report](STAGE3_SEMANTIC_SAMPLING_PILOT.md), in “What failed and what the feedback changed.” It changes **no reference annotation, raw generation, selected output, aggregate result, cost, or ledger**.

The original report says that two erroneous positive witness judgments retained the lower-bound interpretation for independent sampling on `sampling-20`. The actual eight-attempt trace contains **one erroneous positive followed by one correct positive**:

| Step | Saved journey ID | Scheduled departure | Reference: depart ≤ 10:55:00 | Ordinary judgment | Candidates remaining |
|---|---|---|---|---|---|
| First witness | `0046a48e25e956543682` | 11:25:00 | Violated | Satisfied — incorrect | `c1`, `c6` |
| Second witness | `03c572f19409b8bd2a6c` | 10:55:00 | Satisfied | Satisfied — correct | `c6` |

Candidate `c6` requires departure ≥ 10:55:00. Its selected journey `0ce2d0f97e8a8824a218` departs exactly at 10:55:00, so the final plan satisfies the true upper-bound request despite the nonmatching formalization. Under truthful first-witness rejection, only `c0` survives; its selected journey `2ba084255b08719b7312` departs at 11:31:00 and violates the request.

The oracle procedure is bounded witness selection and elimination with truthful reference labels, followed by the first surviving candidate's deterministic plan. It is not a reference-optimal selector or an unconditional correctness ceiling. Final ordinary correctness remains 28/32 and oracle-witness correctness remains 27/32 for independent sampling. The 11/19 ordinary judgment-error total was computed from records and is unchanged.

The prior “only ordinary correct plan without full candidate equivalence” statement applies to the **final eight-attempt checkpoint**. At checkpoint four, diversified sampling also has such a case (`sampling-04`); the new complete joint table includes it. This is a scope clarification, not an additional numerical correction.

Evidence: original `runs/stage3-fresh/pairs/sampling-20.json`, its frozen pool and `data/sampling/references.json`; saved `offline-oracle-stage3.json`; [compact corrected trace](../paper/icaart_position/analysis/worked-examples.json); [all checkpoint joint counts](../paper/icaart_position/analysis/stage3-joint.csv). The manuscript's focused regression check explicitly verifies the first-false/second-true reference labels. Historical report and generator remain preserved; the paper's analysis is generated separately from the raw records.

No new experimental inference or GPU usage occurred.

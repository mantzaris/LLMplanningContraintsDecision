# Verified bibliography and targeted overlap review

Verified on 2026-09-12 against the primary links below. Published proceedings and
preprints are distinguished. The search was targeted, not exhaustive novelty
verification; unverifiable and aggregator-only hits were excluded.

| Reference | Verified status and source | Relevance and limits |
|---|---|---|
| Gautier Dagan, Frank Keller, Alex Lascarides. *Dynamic Planning with a LLM*. 2023. | [arXiv:2308.06391v1](https://arxiv.org/abs/2308.06391v1), preprint; no proceedings status asserted here. | LLM-DP combines language-model interpretation with a traditional planner in ALFWorld. The composition is prior work, not our increment. |
| Yilun Hao, Yongchao Chen, Yang Zhang, Chuchu Fan. *Large Language Models Can Solve Real-World Planning Rigorously with Formal Verification Tools*. 2025. | Published [NAACL 2025, pp. 3434–3483](https://aclanthology.org/2025.naacl-long.176/), DOI 10.18653/v1/2025.naacl-long.176. | Formalized travel requirements, satisfiability solving and infeasibility handling overlap strongly with our foundation. Our question concerns selecting semantic checks when the formalization itself may be wrong. |
| Mohammad Raza, Natasa Milic-Frayling. *Instantiation-based Formalization of Logical Reasoning Tasks Using Language Models and Logical Solvers*. 2025. | Published [IJCAI-25, pp. 4633–4641](https://www.ijcai.org/proceedings/2025/516), DOI 10.24963/ijcai.2025/516; [arXiv v3](https://arxiv.org/abs/2501.16961v3). | Semantic Self-Verification (SSV) already uses concrete instantiations, consistency and refinement. Our C baseline adapts this concept to finite scheduled journeys; it does not reproduce SSV's full algorithm or selective-verification guarantee. |
| Daniel Mendoza, Anastasia Mavridou, Andreas Katis, Caroline Trippel. *Automating Requirements Formalization: Using LLMs and Low-Complexity Distinguishing Traces for Semantic Validation*. 2026. | Published ICSE ’26; DOI [10.1145/3744916.3787815](https://doi.org/10.1145/3744916.3787815), verified in [author-hosted paper](https://cs.stanford.edu/people/trippel/pubs/mendoza_ICSE26.pdf) and [official program](https://conf.researchr.org/details/icse-2026/icse-2026-research-track/287/Automating-Requirements-Formalization-Using-LLMs-and-Low-Complexity-Distinguishing-T). | ARTEMIS is the closest selection comparison: balanced distinguishing traces for human validation. D adapts balanced separation; E adds weights from selected-plan cross-violation. Our automated judge and finite task representation differ materially. |
| Rikhil Amonkar, Ceyhun Efe Kayan, Qimei Lai, Ronan Le Bras, Li Zhang. *A Reality Check of Language Models as Formalizers on Constraint Satisfaction Problems*. | [arXiv:2505.13252v6](https://arxiv.org/abs/2505.13252v6), revised 2026-08-19; preprint status used here. | Shows that formalizer performance is not automatically superior and studies omission/logic errors. This cautions against treating solver validity as intent correctness. No headline accuracy figures are transferred to our setting. |
| Jian Xie, Kai Zhang, Jiangjie Chen, Tinghui Zhu, Renze Lou, Yuandong Tian, Yanghua Xiao, Yu Su. *TravelPlanner: A Benchmark for Real-World Planning with Language Agents*. 2024. | Published [ICML 2024, PMLR 235:54590–54613](https://proceedings.mlr.press/v235/xie24j.html); [arXiv:2402.01622](https://arxiv.org/abs/2402.01622). | Later external comparison, not a Stage 1 dependency. Its curated intents/reference plans and sandbox records are a separate benchmark with its own collection and licensing provenance. They are not observed passenger requests or GTFS vehicle observations. Integration needs a separate provenance/license and checker audit. |
| André G. Pereira, Augusto B. Corrêa, Jendrik Seipp. *Property-Guided LLM Program Synthesis for Planning*. 2026. | [arXiv:2605.16142v2](https://arxiv.org/abs/2605.16142v2), preprint, revised 2026-05-18. | A newer close planning comparison: formal properties and concrete counterexamples guide heuristic-program repair. Its property is specified externally, whereas our uncertainty is the interpretation of user constraints. Counterexample-guided planning repair itself is therefore not a contribution claim. |
| Jun Yang, Yuechun Sun, Yi Wu, Rodrigo Caridad, Yongwei Yuan, Jianan Yao, Shan Lu, Kexin Pei. *ExVerus: Verus Proof Repair via Counterexample Reasoning*. 2026. | [arXiv:2603.25810](https://arxiv.org/abs/2603.25810), preprint. | Behavioral counterexamples guiding proof repair further narrow any generic counterexample-feedback claim. It does not establish the proposed planning interpretation-selection policy. |

Searches included exact ARTEMIS/SSV titles, semantic-validation planning constraints,
and LLM formalization/counterexamples in 2026. The newer planning-synthesis paper
materially reinforces the overlap in repair and verifier feedback. The remaining
proposed increment is narrowly stated: **a fixed weighted pair-separation policy
whose weights depend on whether candidate-selected plans violate competing
interpretations, evaluated against balanced separation at matched inference cost**.
Whether that improves final-plan correctness is an empirical question, not a result
established by this bibliography or implementation.

Machine-readable citation entries: [references.bib](references.bib).

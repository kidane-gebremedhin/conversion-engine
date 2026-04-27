# Statistical test — Delta A

**Question.** Does the Act IV mechanism (full dual-control) outperform
the Day-1 baseline (stock `llm_agent`) on the same partition, paired by
task?

**Method.** Paired-task percentile bootstrap. For each task in the
partition, take pass-rate(B) − pass-rate(A) across that task's trials.
Resample the task-level delta vector with replacement 5000 times for the
CI; centered bootstrap of the same size for the p-value.

**Result.**

| Quantity | Value |
|---|---|
| Pass@1 — A (baseline)  | 0.867 |
| Pass@1 — B (mechanism) | 0.833 |
| Δ̂ A = B − A           | -0.0333 |
| 95% CI on Δ̂ A         | [-0.1667, 0.1] |
| Two-sided p-value      | 0.742 |
| Paired tasks (n)       | 30 |
| Resamples              | 5000 |

**Verdict.** **DOES NOT PASS.**

The Act IV gate is `Delta A > 0 AND p < 0.05`. Failing this means the
mechanism does not pass; the trainee must either revise the mechanism
or honestly report the null result in `memo.pdf` Page 2.

**Reproducibility.** Same partition, same trial count, same seed across
all conditions; tau2 SHA `6e1d57640fb25df43c3d8049abeefade6275c6f0` pinned in
`config.yaml > tau2.pinned_sha`. Bootstrap RNG seed: 0.

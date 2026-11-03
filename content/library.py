# -*- coding: utf-8 -*-
"""Reference library shown in the Material pane under the Library tab.

Short, memorisable lines. This is the material you read on the way into a task, not a
textbook: each row is one thing you might otherwise get wrong under time pressure.
"""

LIBRARY = {
    "SQL": [
        ("Contract", "grain, population, identity, time boundary, tie rule"),
        ("Evaluation order", "FROM, WHERE, GROUP BY, HAVING, SELECT, window"),
        ("Portable", "substr(ts,1,7) for month, 1.0*a/b for division"),
        ("PostgreSQL", "date_trunc, INTERVAL, ::date, PERCENTILE_CONT, DISTINCT ON"),
        ("SQLite", "strftime, JULIANDAY, date(ts,'-1 month'), no percentile"),
        ("Dedupe", "ROW_NUMBER() OVER (PARTITION BY k ORDER BY ts DESC, id DESC), rn = 1"),
        ("Ranking", "ROW_NUMBER exact n, RANK ties kept, DENSE_RANK distinct values"),
        ("Zero fill", "grid CTE, then LEFT JOIN the aggregate onto it"),
        ("Rolling", "ROWS BETWEEN n-1 PRECEDING AND CURRENT ROW on a date spine"),
        ("Anti-join", "NOT EXISTS, never NOT IN with a nullable column"),
        ("NULL", "comparison is unknown, COUNT(col) skips NULLs"),
        ("Cohort index", "12*(y2-y1) + (m2-m1)"),
        ("Islands", "day_number - ROW_NUMBER() is constant within a run"),
        ("Fanout", "one-to-many join multiplies sums, pre-aggregate first"),
    ],
    "Statistics": [
        ("p-value", "P(data | null), never P(null | data)"),
        ("CI", "coverage of the procedure, not probability for this interval"),
        ("Power", "1 - beta, rises with n, effect size and lower variance"),
        ("MDE", "scales as 1/sqrt(n), halving it costs 4x the sample"),
        ("n per arm", "16 * p(1-p) / delta^2 as a sanity check"),
        ("z test", "(p1-p2) / sqrt(p(1-p)(1/n1+1/n2)), pooled p"),
        ("Phi(x)", "0.5 * (1 + erf(x/sqrt(2)))"),
        ("CUPED", "theta = cov/var, Y - theta(X - mean X)"),
        ("SRM", "z = (obs-exp)/sqrt(np(1-p)), flag beyond 4 sigma"),
        ("Multiplicity", "Bonferroni alpha/k, or FDR when many tests"),
        ("Peeking", "fixed-horizon tests cannot be stopped early"),
        ("Bootstrap", "for ratios and percentiles, not for broken samples"),
    ],
    "Python and pandas": [
        ("Order", "stub that returns the right shape first, then fill in"),
        ("Grain", "dedupe to the entity before aggregating"),
        ("Sort", "sort inside the group before diff, pct_change, streak"),
        ("Merge", "validate='many_to_one', assert row count unchanged"),
        ("Copy", "df = df.copy() before mutating"),
        ("Dates", "pd.to_datetime(errors='coerce'), then count NaT"),
        ("Group feature", "groupby(...).transform, not apply"),
        ("Loc", "df.loc[mask, 'col'] = value, one call, no chaining"),
        ("Money", "round to cents or use integer minor units"),
        ("Debug", "print may be suppressed, assert instead"),
        ("Empty", "return the correct empty structure, do not raise"),
        ("Json", "json.dumps(result, sort_keys=True) to compare outputs"),
    ],
    "Grab": [
        ("GMV", "transaction value incl. taxes, tips, tolls, not revenue"),
        ("On-Demand GMV", "Mobility GMV plus Deliveries GMV"),
        ("MTU", "monthly transacting users, not monthly active"),
        ("Intensity", "GMV per MTU, the second factor in the identity"),
        ("DTU/MTU", "stickiness, around 17%"),
        ("GrabUnlimited", "over a third of Deliveries GMV, 5x spend, 4x frequency"),
        ("Incentives", "consumer and partner subsidy, a cost line"),
        ("Experiments", "GrabX reports per-variant stats, CIs, p-values"),
        ("Warehouse", "Spark on Databricks, Trino, Delta and Iceberg"),
        ("C360", "consumer-360 mart used for personalisation and CLV"),
        ("Role", "growth analytics, CRM, A/B testing, LLM self-serve tools"),
    ],
}

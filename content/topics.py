# -*- coding: utf-8 -*-
"""Topic cards shown in the learning pane beside every MCQ.

One card per topic rather than one per question: the item supplies its own
explanation and the card supplies the surrounding theory, which is how the
material stays useful when a question is drawn at random from a pool of 72.
"""

TOPICS = {
    "stats": dict(
        name="Statistics and inference",
        concept=[
            "Every claim in an experiment readout is a statement about a sampling "
            "distribution. The estimator is random, the parameter is fixed, and the "
            "only thing a sample can tell you is how surprising the data would be if "
            "nothing were happening.",
            "The three numbers that travel together are the estimate, its standard "
            "error and the interval. A p-value without an effect size tells you "
            "nothing about whether the finding is worth money.",
        ],
        recipe=[
            "Write the estimator first: a mean, a difference of means, a ratio.",
            "Its standard error is the standard deviation divided by sqrt(n) for a "
            "mean, or the pooled formula for a proportion difference.",
            "Interval: estimate plus or minus z times SE.",
            "Test: statistic divided by SE under the null, then a tail probability.",
            "Report estimate, interval, n, and the decision threshold it has to clear.",
        ],
        gotchas=[
            "p-values and intervals must agree. If the interval excludes zero and the "
            "p-value is above alpha, one of the two is computed wrong.",
            "With very large n, almost any difference is significant. Practical "
            "significance needs a cost comparison, not a smaller alpha.",
            "Skewed metrics break mean-based tests. Log transform for the test, report "
            "the original-scale mean, or bootstrap.",
        ],
        reference=[("p-value", "P(data | H0), not P(H0 | data)"),
                   ("95% interval", "estimate +/- 1.96 SE"),
                   ("SE of a mean", "sd / sqrt(n)"),
                   ("SE of a difference", "sqrt(SE1^2 + SE2^2)"),
                   ("Power", "1 - P(Type II), rises with n and effect size")],
    ),
    "experiment": dict(
        name="Experimentation",
        concept=[
            "An experiment is a comparison against a counterfactual, and the "
            "counterfactual is only credible if the randomisation held. That is why "
            "the first questions are about assignment, not about results.",
            "In a marketplace, units interact: treating one set of users changes the "
            "supply available to the control group. That is interference, and it "
            "changes the design rather than the analysis.",
        ],
        recipe=[
            "Define the unit, the metric, the horizon and the guardrails before launch.",
            "Check SRM on assignment counts as the first readout step.",
            "Read the primary metric with its interval, then guardrails, then segments.",
            "State the decision rule in advance: what lift, at what cost, would ship.",
            "For interference, move to cluster or switchback randomisation.",
        ],
        gotchas=[
            "Peeking at a fixed-horizon test and stopping at the first crossing "
            "inflates false positives well beyond alpha.",
            "A flat result on an underpowered test is not evidence of no effect.",
            "Segment hunting without multiplicity control produces a winner every time.",
            "Novelty effects decay. Read the last week and a repeat-purchase metric.",
        ],
        reference=[("SRM test", "chi-square or z on assignment counts"),
                   ("CUPED", "theta = cov/var, adjust Y by theta(X - mean X)"),
                   ("Interference", "marketplace tests need cluster or switchback"),
                   ("Guardrails", "unsubscribes, complaints, refund rate, latency"),
                   ("Incrementality", "requires a concurrent control, never last click")],
    ),
    "ml": dict(
        name="Machine learning",
        concept=[
            "Model choices are mostly decisions about the bias-variance trade-off and "
            "about what the model is allowed to see at prediction time. Most failures "
            "in production are leakage failures, not algorithm failures.",
            "The metric has to match the decision. Targeting a fixed number of users "
            "asks a precision-at-k question. Forecasting expected value asks a "
            "calibration question. Comparing models asks a ranking question.",
        ],
        recipe=[
            "State the prediction point, then list what is knowable at that moment.",
            "Split by time for anything with temporal structure.",
            "Fit inside a pipeline so preprocessing is learned on training data only.",
            "Evaluate on the holdout, at the operating point the business will use.",
            "Calibrate if probabilities feed a cost or revenue calculation.",
        ],
        gotchas=[
            "A feature computed after the label date is leakage, and it produces "
            "beautiful offline numbers.",
            "Resampling the test set makes the holdout a fiction. Adjust training only.",
            "ROC-AUC hides behaviour at a fixed cutoff when the positive rate is low.",
            "Impurity importance is biased toward high-cardinality features. Use "
            "permutation importance on held-out data.",
        ],
        reference=[("L1 / L2", "L1 sparse selection, L2 smooth shrinkage"),
                   ("C in sklearn", "inverse regularisation strength"),
                   ("exp(beta)", "odds ratio per unit"),
                   ("PR-AUC", "positive-class focused summary"),
                   ("Calibration", "Platt or isotonic on held-out data")],
    ),
    "sql": dict(
        name="SQL",
        concept=[
            "SQL questions are rarely about syntax. They are about grain: what one row "
            "of the answer means, and whether your joins preserve that grain or "
            "multiply it.",
            "The second theme is evaluation order. FROM, WHERE, GROUP BY, HAVING, "
            "SELECT, then window functions. Almost every trap comes from forgetting "
            "where in that sequence a clause runs.",
        ],
        recipe=[
            "Write the grain in a comment before the query.",
            "Build the base population, then aggregate, then window, then filter.",
            "Wrap window filters in a CTE, because WHERE runs before windows.",
            "Check row counts after each join while developing.",
            "Test empty input, NULLs, ties and the time boundary before submitting.",
        ],
        gotchas=[
            "NOT IN against a nullable column returns nothing. Use NOT EXISTS.",
            "A right-table filter in WHERE after a LEFT JOIN silently makes it inner.",
            "ROW_NUMBER drops ties that RANK would keep. Choose deliberately.",
            "Integer division truncates. Multiply by 1.0 before dividing.",
            "BETWEEN on timestamps double-counts the boundary. Use >= and <.",
        ],
        reference=[("Evaluation order", "FROM, WHERE, GROUP BY, HAVING, SELECT, window"),
                   ("PostgreSQL", "date_trunc, INTERVAL, ::date, PERCENTILE_CONT"),
                   ("SQLite", "strftime, JULIANDAY, date(ts,'-1 month')"),
                   ("Portable", "substr(ts,1,7), 1.0*a/b, CTE then filter"),
                   ("Dedupe", "ROW_NUMBER over the key, filter rn = 1")],
    ),
    "growth": dict(
        name="Growth, CRM and product metrics",
        concept=[
            "Growth questions are decomposition questions. GMV equals transacting users "
            "times spend per user. Revenue equals GMV times take rate. Once the "
            "identity is written down, most 'why did the number move' questions answer "
            "themselves.",
            "CRM questions add a counterfactual. A campaign's value is the behaviour it "
            "caused, not the behaviour it coincided with, which is why every serious "
            "readout has a control arm.",
        ],
        recipe=[
            "Write the identity for the headline metric.",
            "Break the change into a mix effect and a rate effect.",
            "Check whether the base moved: percentages of a shrinking base mislead.",
            "For campaigns, report absolute lift, relative lift, cost per incremental "
            "action, and the margin comparison.",
            "Ask the retention question, because bought growth decays.",
        ],
        gotchas=[
            "GMV is not revenue. Incentives are a cost line, not a discount on GMV.",
            "Last-click attribution gives full credit for conversions that would have "
            "happened anyway.",
            "A significant 0.8% lift that costs more than the margin is a loss.",
            "Churn defined by a fixed inactivity window misreads naturally infrequent "
            "users.",
        ],
        reference=[("GMV", "transaction value incl. taxes, tips, tolls"),
                   ("MTU", "monthly transacting users, not active"),
                   ("Intensity", "GMV per MTU"),
                   ("DTU/MTU", "stickiness, around 17% for Grab"),
                   ("Unlimited", "over a third of Deliveries GMV, 5x spend, 4x frequency")],
    ),
    "llm": dict(
        name="LLMs and applied GenAI",
        concept=[
            "Applied GenAI questions are architecture questions disguised as model "
            "questions. The interesting decisions are retrieval, grounding, evaluation "
            "and cost, not the size of the model.",
            "Anything customer-facing needs a measured failure rate. Without an "
            "evaluation set you cannot tell whether a prompt change helped or the "
            "sample changed.",
        ],
        recipe=[
            "Decide whether the problem is knowledge (retrieval) or behaviour "
            "(fine-tuning). Most analytics problems are knowledge.",
            "Chunk documents to the grain of the question, embed, retrieve, then "
            "generate with citations.",
            "Build a golden set of 50 to 200 cases before tuning anything.",
            "Grade with a rubric, compare pairwise with randomised order, and check "
            "against human labels.",
            "Route by difficulty: small model first, escalate on low confidence.",
        ],
        gotchas=[
            "LLM judges favour longer answers and their own position. Randomise order "
            "and control for length.",
            "Retrieved text can contain instructions. Never let it trigger side effects.",
            "Raising model size does not fix missing metric definitions in the data layer.",
            "Temperature near zero for extraction and SQL generation, never for ideation.",
        ],
        reference=[("RAG", "changing facts, citations required"),
                   ("Fine-tune", "fixed format or behaviour"),
                   ("Chunking", "size trades retrieval precision against context"),
                   ("Cost control", "prompt caching, batching, distillation"),
                   ("Guardrails", "schema-constrained output, allow-listed tools")],
    ),
    "python": dict(
        name="Python and pandas",
        concept=[
            "Pandas questions test whether you know where the data grain lives and "
            "whether you mutate things you do not own. Almost every pandas bug is a "
            "grain bug or a view-versus-copy bug.",
            "In a timed environment, the winning habit is the stub: return the correct "
            "shape immediately, then fill it in. A submitted partial beats an "
            "unsubmitted perfect.",
        ],
        recipe=[
            "Copy the frame at the top if you will mutate it.",
            "Deduplicate to the entity grain before aggregating.",
            "Sort inside the group before diff, pct_change or any streak logic.",
            "Prefer groupby transform over apply for group-level features.",
            "Assert row counts before and after every merge.",
        ],
        gotchas=[
            "Merging without validate silently multiplies rows and inflates every sum.",
            "Chained assignment may write to a copy. Use a single .loc call.",
            "Comparing floats for money equality fails. Round or use integer minor units.",
            "iterrows is slow and returns copies. Use vectorised operations.",
        ],
        reference=[("loc / iloc", "label based / position based"),
                   ("transform", "group aggregate broadcast to rows"),
                   ("validate", "one_to_one, many_to_one guards on merge"),
                   ("to_datetime", "errors='coerce', then count NaT"),
                   ("dtype", "category for low-cardinality string columns")],
    ),
}

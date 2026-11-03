# -*- coding: utf-8 -*-
"""Learning cards for the 15 SQL tasks, plus the merge that produces app tasks.

Card fields match what the right-hand pane renders: concept, recipe, gotchas,
reference. The SQL itself lives in sql_tasks.py and is verified by build/verify.py.
"""
from sql_tasks import DRILLS

CARDS = {
    "S1": dict(
        concept=[
            "Period-over-period comparisons look trivial and fail constantly, for two "
            "reasons: the series has holes where nothing happened, and the first period "
            "has no previous value to compare against.",
            "The fix is to build the output grid first and join the aggregate onto it. "
            "That way an empty month is a row with zero GMV rather than a missing row "
            "that reads as stable performance.",
        ],
        recipe=[
            "Build a grid CTE of every dimension crossed with every period.",
            "Aggregate the fact table to the same grain.",
            "LEFT JOIN the aggregate onto the grid.",
            "Use LAG over the grid, so the previous value exists even when it is zero.",
            "Guard the ratio with NULLIF so a zero prior period cannot divide.",
        ],
        gotchas=[
            "An inner join drops quiet months, and the MoM chart then shows growth that "
            "did not happen.",
            "LAG on the fact table gives you the previous row with data, not the previous "
            "month.",
            "Percentage change from zero is undefined. Decide and state the convention.",
        ],
        reference=[("grid", "SELECT DISTINCT dim CROSS JOIN periods"),
                   ("LAG", "previous row in the window order"),
                   ("NULLIF(x,0)", "avoid division by zero"),
                   ("ORDER BY", "part of the answer when the prompt says so")],
    ),
    "S2": dict(
        concept=[
            "Retention needs two correct decisions: the denominator is distinct users, "
            "and the comparison is between a period and the period immediately before.",
            "Because a single user generates many bookings, aggregating the raw fact "
            "table on both sides measures booking retention, not user retention, and the "
            "result exceeds 100 percent on any dense dataset.",
        ],
        recipe=[
            "Deduplicate to (period, user) pairs.",
            "Count pairs per period for the denominator.",
            "Self-join pairs to pairs on user, with the prior period on the right.",
            "LEFT JOIN the retained counts so quiet months stay visible.",
        ],
        gotchas=[
            "COUNT(*) on raw bookings is the classic wrong denominator.",
            "The first period has no predecessor. Exclude it or show zero, deliberately.",
            "An inner join deletes the months where nobody returned, which are the "
            "interesting ones.",
        ],
        reference=[("grain", "one row per period"),
                   ("identity", "user counts once per period"),
                   ("prior period", "date(month || '-01', '-1 month') in SQLite"),
                   ("COALESCE", "turn no survivors into 0, not NULL")],
    ),
    "S3": dict(
        concept=[
            "A cohort table fixes the denominator at signup and tracks the same people "
            "forward. That is what makes cohorts comparable: each row is a different "
            "group of users, measured the same way.",
            "The month index is arithmetic, not a join: 12 times the year difference plus "
            "the month difference. Once you have the index, retention is conditional "
            "aggregation.",
        ],
        recipe=[
            "Cohort the users by signup month.",
            "Join their activity and compute the month index arithmetically.",
            "Use COUNT(DISTINCT CASE WHEN index = k THEN user END) per column.",
            "Divide every column by the cohort size from the user table.",
        ],
        gotchas=[
            "Dividing by active users instead of cohort size produces flattering, "
            "incomparable numbers.",
            "A LEFT JOIN from the cohort is what keeps never-transacting users in the "
            "denominator.",
            "Month 0 is a partial month for late-month signups, so M0 can sit below M1. "
            "That is real, not a bug.",
        ],
        reference=[("cohort", "month of the first event"),
                   ("index", "12*(y2-y1) + (m2-m1)"),
                   ("M0", "activity in the signup month itself"),
                   ("denominator", "cohort size, fixed"),
                   ("CLASSIC", "conditional aggregation with COUNT DISTINCT")],
    ),
    "S4": dict(
        concept=[
            "Repeat-purchase rates need an anchor event per user, which is the first "
            "completed booking, not the signup. Everything else is a window measured "
            "from that anchor.",
            "The subtle parts are the second event (strictly after the first, not equal "
            "to it) and the window boundary (inclusive of day 30).",
        ],
        recipe=[
            "CTE 1: MIN(booking_ts) per user, filtered to the period you care about.",
            "CTE 2: MIN(booking_ts) greater than the anchor, per user.",
            "Compute the day difference and compare with the inclusive threshold.",
            "Divide by the count of anchored users per segment.",
        ],
        gotchas=[
            "Using >= 30 silently excludes day-30 repeats, and the number moves by "
            "points.",
            "Anchoring on signup rather than first booking measures activation, not "
            "repeat.",
            "Same-day second bookings must count. Check the comparator.",
        ],
        reference=[("anchor", "first completed event, not signup"),
                   ("second event", "MIN(ts) where ts > anchor"),
                   ("day diff", "JULIANDAY(a) - JULIANDAY(b) in SQLite"),
                   ("window", "0 to 30 days inclusive")],
    ),
    "S5": dict(
        concept=[
            "A funnel is a set of conditional counts over one population, divided by one "
            "denominator. The moment each stage is divided by the previous stage, the "
            "four numbers stop describing the same thing.",
            "In CRM the denominator is sends, because that is the cost you incurred. "
            "Step-to-step rates belong in additional columns, not instead of the base "
            "rates.",
        ],
        recipe=[
            "Filter to the campaign in WHERE, before aggregating.",
            "COUNT(*) for sends, SUM(flag) for each stage count.",
            "Multiply by 100.0 before dividing, so integer division does not truncate.",
            "ROUND to the precision the prompt asks for.",
        ],
        gotchas=[
            "Integer division returns 0 in PostgreSQL when you write 100 * x / y.",
            "Mixing denominators makes variants incomparable.",
            "Stages in a CRM table are not always nested; check whether booked_7d implies "
            "redeemed.",
        ],
        reference=[("SUM(flag)", "count of ones, no CASE needed"),
                   ("denominator", "COUNT(*) sends"),
                   ("100.0", "force float before dividing"),
                   ("ROUND(x,2)", "match the requested precision")],
    ),
    "S6": dict(
        concept=[
            "The two-proportion test can be written entirely in SQL, which is worth being "
            "able to do because it removes the export step from a readout.",
            "The pooled standard error belongs in the z-statistic, because under the null "
            "both arms share one rate. The unpooled error belongs in the confidence "
            "interval, because there the rates differ.",
        ],
        recipe=[
            "Aggregate n and conversions per variant.",
            "CROSS JOIN the two arms into one row so both are available.",
            "Compute the pooled rate, then the pooled standard error.",
            "z = (rate_t - rate_c) / pooled_se.",
            "Report absolute lift, relative lift, n and z together.",
        ],
        gotchas=[
            "CASE-based pivoting gives NULL when a variant is missing, and the arithmetic "
            "silently returns NULL.",
            "Relative lift without the base rate hides how small the absolute effect is.",
            "A z around 1.3 is noise. Do not narrate it as a trend.",
        ],
        reference=[("pooled p", "(c1+c2)/(n1+n2)"),
                   ("pooled SE", "sqrt(p(1-p)(1/n1+1/n2))"),
                   ("z", "(p1-p2)/SE"),
                   ("|z|>1.96", "two-sided 5% significance")],
    ),
    "S7": dict(
        concept=[
            "Top-N per group is a window problem, not a GROUP BY problem. The join "
            "between the fact table and the dimension is where the grain gets lost.",
            "Tie handling is the scored detail. A prompt that says ties must be kept is "
            "asking you to choose RANK over ROW_NUMBER, and to say so.",
        ],
        recipe=[
            "Aggregate GMV to (group, entity) grain first.",
            "Rank inside the group with a window function.",
            "Filter on the rank in an outer query, never in WHERE of the same level.",
            "Add a deterministic secondary sort inside the window.",
        ],
        gotchas=[
            "ROW_NUMBER returns exactly N rows and drops a tie, which is wrong when the "
            "prompt says otherwise.",
            "Joining bookings to a one-to-many dimension inflates the sum.",
            "Ranking before aggregating ranks individual bookings, not entities.",
        ],
        reference=[("ROW_NUMBER", "exactly n rows"),
                   ("RANK", "ties kept, gaps after ties"),
                   ("DENSE_RANK", "n distinct values"),
                   ("filter", "outer query or CTE only")],
    ),
    "S8": dict(
        concept=[
            "A rolling window is a frame, and the frame counts rows unless you build a "
            "calendar. On a fact table with missing days, six preceding rows can span "
            "three weeks.",
            "The correct pattern is a date spine left-joined to the aggregate, with the "
            "frame expressed in rows over that spine, which now means days.",
        ],
        recipe=[
            "Build a calendar CTE covering the window.",
            "Aggregate the fact table per day.",
            "LEFT JOIN and COALESCE to zero.",
            "AVG over ROWS BETWEEN 6 PRECEDING AND CURRENT ROW on the calendar.",
        ],
        gotchas=[
            "A trailing average without zero-fill is an average of active days only, "
            "which is systematically higher.",
            "RANGE versus ROWS matters when dates are irregular.",
            "The first six days have a partial window. State whether that is acceptable.",
        ],
        reference=[("frame", "ROWS BETWEEN n-1 PRECEDING AND CURRENT ROW"),
                   ("spine", "CROSS JOIN or generated calendar"),
                   ("zero fill", "COALESCE(agg, 0)"),
                   ("RANGE vs ROWS", "values versus physical rows")],
    ),
    "S9": dict(
        concept=[
            "Latest-record-per-entity is the most reused pattern in analytics, because "
            "every event table is append-only and every report wants one row per entity.",
            "The deterministic version numbers rows inside the entity and filters. The "
            "tie-breaker is not decoration: duplicate timestamps are normal in event data.",
        ],
        recipe=[
            "ROW_NUMBER over PARTITION BY entity ORDER BY ts DESC, id DESC.",
            "Wrap in a CTE.",
            "Filter rn = 1.",
            "Keep the original columns so downstream joins stay available.",
        ],
        gotchas=[
            "DISTINCT on the entity drags arbitrary values from other columns.",
            "MAX(ts) grouped by entity has the same problem.",
            "Without a second sort key the answer changes between runs.",
        ],
        reference=[("ROW_NUMBER", "1,2,3 with a full ordering"),
                   ("PARTITION BY", "restart numbering per entity"),
                   ("tie-break", "id DESC as the second key"),
                   ("PostgreSQL", "DISTINCT ON is shorter but non-standard")],
    ),
    "S10": dict(
        concept=[
            "Gaps and islands: in a sorted list of dates, day number minus row number is "
            "constant within a consecutive run and jumps at every gap. That constant is "
            "the run identifier.",
            "Once every consecutive run shares an id, counting run lengths is a GROUP BY. "
            "The same trick handles login streaks and contiguous status periods.",
        ],
        recipe=[
            "DISTINCT to one row per entity per day.",
            "ROW_NUMBER per entity ordered by day.",
            "Subtract the row number from the day number to get the island id.",
            "GROUP BY entity, island id, then COUNT and ORDER BY the count.",
        ],
        gotchas=[
            "Without DISTINCT, three events on one day become a three-day streak.",
            "JULIANDAY returns a float. Cast it, or every island is unique.",
            "A one-day gap must break the run. Check your arithmetic with a hand example.",
        ],
        reference=[("island", "day_number - row_number"),
                   ("SQLite", "CAST(JULIANDAY(d) AS INTEGER) - ROW_NUMBER()"),
                   ("PostgreSQL", "d::date - ROW_NUMBER()::int"),
                   ("then", "GROUP BY entity, island")],
    ),
    "S11": dict(
        concept=[
            "Churn sets are anti-joins: active in one period, absent in the next. The "
            "query is easy; the trap is SQL's three-valued logic.",
            "NOT IN against a nullable column returns nothing at all, because every "
            "comparison against NULL is unknown and WHERE keeps only true.",
        ],
        recipe=[
            "Aggregate the first period per user.",
            "NOT EXISTS a matching row in the second period.",
            "Keep the status and date filters inside the subquery.",
            "Return the count and the value at risk, not just the count.",
        ],
        gotchas=[
            "NOT IN with a NULL in the subquery returns zero rows, silently.",
            "A LEFT JOIN with the right-table filter in WHERE collapses to an inner join.",
            "Aggregating the second period before the anti-join loses the per-user grain.",
        ],
        reference=[("NOT EXISTS", "NULL-safe anti-join"),
                   ("NOT IN", "breaks on NULL"),
                   ("LEFT JOIN + IS NULL", "keep filters in ON"),
                   ("value at risk", "GMV from the last active period")],
    ),
    "S12": dict(
        concept=[
            "Deciles and medians answer different questions. NTILE gives buckets of "
            "roughly equal count, while a percentile gives a value at a position.",
            "Medians matter for spend because the mean is dragged by a small heavy tail, "
            "and the mean is what a subsidy programme actually costs.",
        ],
        recipe=[
            "Aggregate spend per entity first.",
            "NTILE(10) over the spend order for deciles.",
            "For a true median use PERCENTILE_CONT in PostgreSQL.",
            "In SQLite, order by spend and take the middle row by OFFSET.",
        ],
        gotchas=[
            "NTILE bucket boundaries are not percentile values.",
            "AVG is not a median. Saying median when you computed a mean is a factual "
            "error in a readout.",
            "Deciles over a tiny population are unstable. Report n.",
        ],
        reference=[("NTILE(10)", "equal-count buckets"),
                   ("PERCENTILE_CONT", "PostgreSQL only"),
                   ("SQLite median", "ORDER BY x LIMIT 1 OFFSET (n-1)/2"),
                   ("report", "mean and median together")],
    ),
    "S13": dict(
        concept=[
            "Campaign value is the difference between treated and control, applied to the "
            "treated population. Observed bookings include people who would have booked "
            "anyway, so they overstate the programme.",
            "Cost per incremental action is the number a marketing lead can act on. ROI "
            "follows from that times the margin.",
        ],
        recipe=[
            "Aggregate n and conversions per variant within each campaign.",
            "Incremental rate = treatment rate minus control rate.",
            "Incremental actions = incremental rate times treated n.",
            "Cost comes from the cost table, joined on campaign.",
            "ROI = incremental revenue / total cost.",
        ],
        gotchas=[
            "Comparing the campaign window to last year is seasonality, not "
            "incrementality.",
            "Dividing cost by observed bookings understates cost per incremental booking, "
            "often by a factor of three.",
            "A missing control arm makes the whole calculation impossible. Say so rather "
            "than approximating.",
        ],
        reference=[("incremental", "(p_t - p_c) * n_t"),
                   ("cost per action", "cost / incremental actions"),
                   ("ROI", "incremental revenue / cost"),
                   ("margin", "use contribution, not GMV")],
    ),
    "S14": dict(
        concept=[
            "Joining a fact table to a send table multiplies rows, because one user can "
            "receive several sends. Every downstream SUM is inflated by the number of "
            "sends per user.",
            "The cure is to collapse the dimension to one row per user before joining, "
            "then aggregate once. Check the row count before and after any join.",
        ],
        recipe=[
            "Reduce sends to one row per user with MIN(sent_ts).",
            "Join bookings with the time window and status in the ON clause.",
            "Aggregate GMV per user, then per campaign.",
            "Compare row counts of the two inputs as a sanity check.",
        ],
        gotchas=[
            "DISTINCT on the final result hides the inflation without fixing the sum.",
            "Putting the window condition in WHERE turns the join into an inner join on "
            "the fact side and drops legitimate rows.",
            "Multiple sends on different days make the window ambiguous. Define it "
            "explicitly.",
        ],
        reference=[("fanout", "one-to-many join multiplies facts"),
                   ("fix", "pre-aggregate to the join grain"),
                   ("window", "condition inside ON, not WHERE"),
                   ("check", "row count before and after")],
    ),
    "S15": dict(
        concept=[
            "Value share and order share are different metrics, and prompts are precise "
            "about which one they want. The numerator decides, the denominator confirms.",
            "A share of total is a conditional aggregate, so the population must be the "
            "whole, not the promo subset. Filtering to promo rows first gives 100 percent.",
        ],
        recipe=[
            "Filter to completed bookings and the period in WHERE.",
            "SUM(CASE WHEN condition THEN value ELSE 0 END) for the numerator.",
            "SUM(value) for the denominator, over the same population.",
            "Multiply by 100.0 and round.",
        ],
        gotchas=[
            "Filtering to the subset before aggregating makes every share 100 percent.",
            "COUNT-based shares answer a different question than value-based ones.",
            "NULL is absence, not zero. IS NOT NULL is the correct test here.",
        ],
        reference=[("numerator", "SUM(CASE WHEN cond THEN v END)"),
                   ("denominator", "SUM(v) over the full population"),
                   ("test", "IS NOT NULL, not != ''"),
                   ("round", "two decimals as asked")],
    ),
}


def build_tasks():
    """Merge the verified SQL with its learning card into app task dicts."""
    tasks = []
    for i, d in enumerate(DRILLS, start=1):
        card = CARDS[d["id"]]
        tasks.append(dict(
            id=d["id"].lower(),
            kind="sql",
            pool="sql",
            title=d["title"],
            tags="SQL  ·  %s  ·  %s" % (d["pattern"], "medium"),
            prompt=d["prompt"],
            contract=d["contract"],
            reference=d["solution"],
            order_matters="ORDER BY" in d["solution"],
            starter="-- %s\nSELECT\n" % d["title"].lower(),
            learning=dict(
                concept=card["concept"],
                recipe=card["recipe"],
                gotchas=card["gotchas"] + [d["trap"]],
                reference=card["reference"] + [["dialect", d["dialect"]]],
            ),
            hints=[d["trap"].split(".")[0] + "."],
        ))
    return tasks


SQL_TASKS = build_tasks()

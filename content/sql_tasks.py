# -*- coding: utf-8 -*-
"""Verified SQL tasks served by the app.

Every query here is executed against data/mock.db by build/verify.py, which
refuses to build the app if any task returns zero rows. Written to run on
SQLite *and* PostgreSQL where it matters; dialect-specific lines are called out
in the `dialect` field.

Grain contract (stating this before writing is a scored habit, not a formality):
what one row means, which rows must survive, what counts once, which time
boundary is inclusive, and whether ordering is part of the answer.
"""

DRILLS = [
    # ------------------------------------------------------------------ 1
    dict(
        id="S1",
        title="Monthly GMV with month-over-month growth",
        pattern="Aggregate + LAG window",
        prompt=(
            "For completed bookings only, return one row per service_type per month "
            "across 2026: the GMV, and the percentage change against the same service's "
            "previous month. Months with no completed bookings must still appear with "
            "zero GMV, not be skipped. Order by service_type, then month."),
        contract=("Grain: (service_type, month). Population: every service_type x month "
                  "combination in 2026, zero-filled. Identity: sum of booking-level gmv, "
                  "status = 'completed'. Time: booking_ts month. Order: explicit."),
        solution="""WITH months AS (
    SELECT DISTINCT substr(booking_ts, 1, 7) AS month
    FROM bookings
    WHERE booking_ts >= '2026-01-01' AND booking_ts < '2027-01-01'
),
services AS (
    SELECT DISTINCT service_type FROM bookings
),
grid AS (
    SELECT s.service_type, m.month FROM services s CROSS JOIN months m
),
agg AS (
    SELECT substr(b.booking_ts, 1, 7) AS month,
           b.service_type,
           SUM(b.gmv) AS gmv
    FROM bookings b
    WHERE b.status = 'completed'
      AND b.booking_ts >= '2026-01-01' AND b.booking_ts < '2027-01-01'
    GROUP BY 1, 2
)
SELECT g.service_type,
       g.month,
       ROUND(COALESCE(a.gmv, 0), 2) AS gmv,
       ROUND(
           100.0 * (COALESCE(a.gmv, 0) - LAG(COALESCE(a.gmv, 0)) OVER
                    (PARTITION BY g.service_type ORDER BY g.month))
           / NULLIF(LAG(COALESCE(a.gmv, 0)) OVER
                    (PARTITION BY g.service_type ORDER BY g.month), 0)
       , 2) AS mom_pct
FROM grid g
LEFT JOIN agg a ON a.service_type = g.service_type AND a.month = g.month
ORDER BY g.service_type, g.month;""",
        trap=("The two silent failures are the zero-fill (an inner join drops quiet "
              "months, so the MoM series starts with a gap that reads as growth) and "
              "the NULL denominator (dividing by a zero prior month without NULLIF "
              "blows up or returns NULL in a column the business reads as a number)."),
        dialect="Portable. substr() exists in both SQLite and PostgreSQL. date_trunc works in PG only; strftime works in SQLite only.",
    ),
    # ------------------------------------------------------------------ 2
    dict(
        id="S2",
        title="Monthly transacting users and month-over-month retention",
        pattern="Self-join on consecutive periods",
        prompt=(
            "Return monthly active transacting users (MTU = distinct users with at least "
            "one completed booking in the month) for 2026, alongside how many of them "
            "also transacted in the immediately preceding month, and the retention rate "
            "as a percentage of the previous month's MTU."),
        contract=("Grain: month. Identity: a user counts once per month regardless of "
                  "service_type or booking count. Population: months 2026-01..2026-10 "
                  "with a prior month available for the retained column."),
        solution="""WITH mtu AS (
    SELECT substr(booking_ts, 1, 7) AS month,
           COUNT(DISTINCT user_id) AS mtu
    FROM bookings
    WHERE status = 'completed'
      AND booking_ts >= '2026-01-01' AND booking_ts < '2027-01-01'
    GROUP BY 1
),
pairs AS (
    -- one row per (month, user) so a user with 40 bookings still counts once
    SELECT DISTINCT substr(booking_ts, 1, 7) AS month, user_id
    FROM bookings
    WHERE status = 'completed'
      AND booking_ts >= '2026-01-01' AND booking_ts < '2027-01-01'
),
retained AS (
    SELECT cur.month,
           COUNT(DISTINCT cur.user_id) AS retained_users
    FROM pairs cur
    JOIN pairs prev
      ON prev.user_id = cur.user_id
     AND prev.month = substr(date(cur.month || '-01', '-1 month'), 1, 7)
    GROUP BY 1
)
SELECT m.month,
       m.mtu,
       COALESCE(r.retained_users, 0) AS retained_users,
       ROUND(100.0 * COALESCE(r.retained_users, 0)
             / NULLIF(LAG(m.mtu) OVER (ORDER BY m.month), 0), 2) AS retention_pct
FROM mtu m
LEFT JOIN retained r ON r.month = m.month
ORDER BY m.month;""",
        trap=("Counting from the raw bookings table instead of a deduplicated "
              "(month, user) pairs CTE inflates both sides, because a heavy user "
              "contributes one row per booking. Deduplicate to the entity grain first, "
              "always."),
        dialect="Portable. The date arithmetic line differs: SQLite uses date(m||'-01','-1 month'); PostgreSQL uses (m::date - INTERVAL '1 month') or date_trunc('month', m::date - INTERVAL '1 month')::text.",
    ),
    # ------------------------------------------------------------------ 3
    dict(
        id="S3",
        title="Signup-cohort retention matrix, month 0 to month 3",
        pattern="Cohort + conditional aggregation",
        prompt=(
            "Build a cohort retention matrix by signup month for users who signed up in "
            "2026. One row per cohort month, then the percentage of that cohort that "
            "transacted in their signup month (M0), month 1, month 2 and month 3. "
            "Base the denominator on cohort size, not on activity."),
        contract=("Grain: cohort month (of users.signup_date). Population: all users who "
                  "signed up in 2026, including those with zero bookings. Identity: a "
                  "user counts once per (cohort, month_index)."),
        solution="""WITH cohort AS (
    SELECT user_id, substr(signup_date, 1, 7) AS cohort_month
    FROM users
    WHERE signup_date >= '2026-01-01' AND signup_date < '2027-01-01'
),
activity AS (
    SELECT DISTINCT b.user_id,
           substr(b.booking_ts, 1, 7) AS active_month
    FROM bookings b
    WHERE b.status = 'completed'
),
joined AS (
    SELECT c.cohort_month,
           c.user_id,
           CAST(
             (CAST(substr(a.active_month, 1, 4) AS INTEGER) * 12
              + CAST(substr(a.active_month, 6, 2) AS INTEGER))
             -
             (CAST(substr(c.cohort_month, 1, 4) AS INTEGER) * 12
              + CAST(substr(c.cohort_month, 6, 2) AS INTEGER))
           AS INTEGER) AS month_index
    FROM cohort c
    LEFT JOIN activity a ON a.user_id = c.user_id
)
SELECT cohort_month,
       COUNT(DISTINCT user_id) AS cohort_size,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN month_index = 0 THEN user_id END)
             / COUNT(DISTINCT user_id), 2) AS m0_pct,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN month_index = 1 THEN user_id END)
             / COUNT(DISTINCT user_id), 2) AS m1_pct,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN month_index = 2 THEN user_id END)
             / COUNT(DISTINCT user_id), 2) AS m2_pct,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN month_index = 3 THEN user_id END)
             / COUNT(DISTINCT user_id), 2) AS m3_pct,
       ROUND(100.0 * COUNT(DISTINCT CASE WHEN month_index >= 1 THEN user_id END)
             / COUNT(DISTINCT user_id), 2) AS ever_repeat_pct
FROM joined
GROUP BY cohort_month
ORDER BY cohort_month;""",
        trap=("Dividing by active users instead of cohort size turns retention into a "
              "flattering number that cannot be compared across cohorts. The "
              "LEFT JOIN from the cohort keeps zero-booking users in the denominator, "
              "which is the whole point of a cohort table."),
        dialect="Portable arithmetic. PostgreSQL has a cleaner month index: (EXTRACT(YEAR FROM a) * 12 + EXTRACT(MONTH FROM a)) - (EXTRACT(YEAR FROM c) * 12 + EXTRACT(MONTH FROM c)).",
    ),
    # ------------------------------------------------------------------ 4
    dict(
        id="S4",
        title="Repeat purchase within 30 days, split by acquisition channel",
        pattern="First-event anchor + datediff",
        prompt=(
            "For each acquisition channel, return the number of users whose first "
            "completed booking happened in 2026, and the share of them who made a "
            "second completed booking within 30 days of the first. A same-day second "
            "booking counts as within 30 days."),
        contract=("Grain: channel. Anchor: a user's first completed booking (not their "
                  "signup). Window: 0 to 30 days after the first booking, inclusive."),
        solution="""WITH firsts AS (
    SELECT user_id, MIN(booking_ts) AS first_ts
    FROM bookings
    WHERE status = 'completed'
    GROUP BY user_id
    HAVING MIN(booking_ts) >= '2026-01-01' AND MIN(booking_ts) < '2027-01-01'
),
seconds AS (
    SELECT f.user_id, f.first_ts, MIN(b.booking_ts) AS second_ts
    FROM firsts f
    JOIN bookings b
      ON b.user_id = f.user_id
     AND b.status = 'completed'
     AND b.booking_ts > f.first_ts
    GROUP BY f.user_id, f.first_ts
)
SELECT u.channel,
       COUNT(DISTINCT f.user_id) AS first_time_users,
       COUNT(DISTINCT CASE
           WHEN s.second_ts IS NOT NULL
            AND (JULIANDAY(s.second_ts) - JULIANDAY(f.first_ts)) <= 30
           THEN f.user_id END) AS repeat_30d_users,
       ROUND(100.0 * COUNT(DISTINCT CASE
           WHEN s.second_ts IS NOT NULL
            AND (JULIANDAY(s.second_ts) - JULIANDAY(f.first_ts)) <= 30
           THEN f.user_id END) / COUNT(DISTINCT f.user_id), 2) AS repeat_30d_pct
FROM firsts f
JOIN users u ON u.user_id = f.user_id
LEFT JOIN seconds s ON s.user_id = f.user_id
GROUP BY u.channel
ORDER BY repeat_30d_pct DESC;""",
        trap=("Using >= 30 instead of <= 30 silently drops day-30 users and turns "
              "INTERVAL day arithmetic into an off-by-one. State inclusivity in the "
              "contract before writing the predicate."),
        dialect="JULIANDAY is SQLite. PostgreSQL uses s.second_ts::date - f.first_ts::date <= 30, or EXTRACT(EPOCH FROM s.second_ts - f.first_ts) / 86400 <= 30 for a timestamped diff.",
    ),
    # ------------------------------------------------------------------ 5
    dict(
        id="S5",
        title="CRM funnel conversion by experiment variant",
        pattern="Conditional aggregation funnel",
        prompt=(
            "For campaign CMP_WELCOME, return one row per variant with the number of "
            "sends, and the conversion rate at each stage: opened, clicked, redeemed, "
            "booked within 7 days. Each stage rate is against sends, not against the "
            "previous stage."),
        contract=("Grain: variant. Identity: one row per send_id. All rates share the "
                  "same denominator so stages are comparable."),
        solution="""SELECT variant,
       COUNT(*) AS sends,
       ROUND(100.0 * SUM(opened)   / COUNT(*), 2) AS open_pct,
       ROUND(100.0 * SUM(clicked)  / COUNT(*), 2) AS click_pct,
       ROUND(100.0 * SUM(redeemed) / COUNT(*), 2) AS redeem_pct,
       ROUND(100.0 * SUM(booked_7d) / COUNT(*), 2) AS booked_7d_pct,
       ROUND(100.0 * SUM(CASE WHEN clicked = 1 AND redeemed = 1 THEN 1 ELSE 0 END)
             / NULLIF(SUM(clicked), 0), 2) AS redeem_per_click_pct
FROM campaign_sends
WHERE campaign_id = 'CMP_WELCOME'
GROUP BY variant
ORDER BY variant;""",
        trap=("Mixing denominators, so click rate over sends and redeem rate over clicks, "
              "produces a funnel that cannot be read as one shape and cannot be "
              "compared across variants. Keep the send as the denominator and add "
              "step-to-step rates as separate columns."),
        dialect="Portable.",
    ),
    # ------------------------------------------------------------------ 6
    dict(
        id="S6",
        title="A/B readout: absolute lift, relative lift, z-statistic",
        pattern="Two-proportion test in SQL",
        prompt=(
            "Using CMP_WELCOME, test whether the treatment improved 7-day booking "
            "conversion. Return per variant n and rate, then the absolute lift, the "
            "relative lift, and a two-proportion z-statistic computed in SQL."),
        contract=("Grain: variant plus one combined row (or a second query) for the "
                  "test. Rate = booked_7d / sends. Test on the pooled standard error."),
        solution="""WITH agg AS (
    SELECT variant,
           COUNT(*) AS n,
           SUM(booked_7d) AS conversions,
           1.0 * SUM(booked_7d) / COUNT(*) AS rate
    FROM campaign_sends
    WHERE campaign_id = 'CMP_WELCOME'
    GROUP BY variant
),
p AS (
    SELECT t.n AS n_t, c.n AS n_c,
           t.rate AS rate_t, c.rate AS rate_c,
           t.conversions AS conv_t, c.conversions AS conv_c,
           1.0 * (t.conversions + c.conversions) / (t.n + c.n) AS p_pooled
    FROM agg t CROSS JOIN agg c
    WHERE t.variant = 'treatment' AND c.variant = 'control'
)
SELECT n_t, conv_t, ROUND(100.0 * rate_t, 2) AS treatment_pct,
       n_c, conv_c, ROUND(100.0 * rate_c, 2) AS control_pct,
       ROUND(100.0 * (rate_t - rate_c), 2) AS abs_lift_pp,
       ROUND(100.0 * (rate_t - rate_c) / NULLIF(rate_c, 0), 2) AS rel_lift_pct,
       ROUND((rate_t - rate_c) / SQRT(p_pooled * (1 - p_pooled) * (1.0 / n_t + 1.0 / n_c)), 4)
           AS z_stat
FROM p;""",
        trap=("Reporting the relative lift without the absolute lift and n is the "
              "single most common CRM readout failure: a 20% relative lift on a 2% "
              "base rate is 0.4pp and usually not worth the voucher cost. Give both, "
              "then the z."),
        dialect="Portable. SQRT exists in both.",
    ),
    # ------------------------------------------------------------------ 7
    dict(
        id="S7",
        title="Top 3 cities per service with ties included",
        pattern="Window ranking + tie semantics",
        prompt=(
            "Return the top three cities by completed-booking GMV for each service_type "
            "in September 2026. If two cities tie for third place, both must appear."),
        contract=("Grain: (service_type, city). Identity: GMV summed from completed "
                  "bookings joined to users.city. Bloomfilter: ties at the third place "
                  "are kept, so the result can exceed three rows per service."),
        solution="""WITH city_gmv AS (
    SELECT b.service_type,
           u.city,
           SUM(b.gmv) AS gmv
    FROM bookings b
    JOIN users u ON u.user_id = b.user_id
    WHERE b.status = 'completed'
      AND b.booking_ts >= '2026-09-01' AND b.booking_ts < '2026-10-01'
    GROUP BY 1, 2
),
ranked AS (
    SELECT service_type, city, gmv,
           DENSE_RANK() OVER (PARTITION BY service_type ORDER BY gmv DESC) AS rnk
    FROM city_gmv
)
SELECT service_type, rnk, city, ROUND(gmv, 2) AS gmv
FROM ranked
WHERE rnk <= 3
ORDER BY service_type, rnk, city;""",
        trap=("ROW_NUMBER() returns exactly three rows and silently discards a tie, "
              "which is a correctness bug when the prompt says ties must stay. "
              "DENSE_RANK keeps them."),
        dialect="Portable.",
    ),
    # ------------------------------------------------------------------ 8
    dict(
        id="S8",
        title="Seven-day rolling GMV and daily trend",
        pattern="Rolling window with explicit frame",
        prompt=(
            "Return one row per day in September 2026 with daily completed GMV and the "
            "trailing seven-day average GMV. The trailing window includes the current "
            "day plus the six before it."),
        contract=("Grain: date. Window: current day plus six preceding calendar days, "
                  "not six preceding rows with data."),
        solution="""WITH daily AS (
    SELECT substr(booking_ts, 1, 10) AS d,
           SUM(gmv) AS gmv
    FROM bookings
    WHERE status = 'completed'
      AND booking_ts >= '2026-09-01' AND booking_ts < '2026-10-01'
    GROUP BY 1
),
calendar AS (
    SELECT DISTINCT substr(booking_ts, 1, 10) AS d FROM bookings
    WHERE booking_ts >= '2026-08-26' AND booking_ts < '2026-10-01'
)
SELECT c.d,
       ROUND(COALESCE(dl.gmv, 0), 2) AS gmv,
       ROUND(AVG(COALESCE(dl.gmv, 0)) OVER (
             ORDER BY c.d ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2) AS gmv_7d_avg
FROM calendar c
LEFT JOIN daily dl ON dl.d = c.d
WHERE c.d >= '2026-09-01'
ORDER BY c.d;""",
        trap=("AVG() OVER (ORDER BY d ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) on a "
              "table that has already dropped empty days averages six rows, not seven "
              "days. Rolling windows must be built on a calendar, not on the fact table."),
        dialect="Portable (SQLite 3.28+, PostgreSQL).",
    ),
    # ------------------------------------------------------------------ 9
    dict(
        id="S9",
        title="Latest record per user (dedupe pattern)",
        pattern="ROW_NUMBER dedupe",
        prompt=(
            "Return one row per user with their most recent completed booking: user_id, "
            "service_type, booking_ts and gmv. Break ties on book" "ing_ts by the higher "
            "booking_id."),
        contract=("Grain: user_id, exactly one row each. Identity: booking_id."),
        solution="""WITH ranked AS (
    SELECT user_id, booking_id, service_type, booking_ts, gmv,
           ROW_NUMBER() OVER (PARTITION BY user_id
                              ORDER BY booking_ts DESC, booking_id DESC) AS rn
    FROM bookings
    WHERE status = 'completed'
)
SELECT user_id, booking_id, service_type, booking_ts, gmv
FROM ranked
WHERE rn = 1
ORDER BY booking_ts DESC;""",
        trap=("DISTINCT on user_id or MAX(booking_ts) with a GROUP BY drags along "
              "columns from arbitrary rows. The tie-breaker is not decoration: "
              "duplicate timestamps exist in every real event table."),
        dialect="Portable. PostgreSQL also offers DISTINCT ON (user_id) with the same ORDER BY, which is shorter but non-standard.",
    ),
    # ------------------------------------------------------------------ 10
    dict(
        id="S10",
        title="Longest consecutive-day active streak per user",
        pattern="Gaps and islands",
        prompt=(
            "Using user_events with event_type = 'app_open', return each user's longest "
            "run of consecutive calendar days with at least one app open."),
        contract=("Grain: user_id. Identity: distinct (user_id, event_date), because an "
                  "extra search event on the same day must not extend the streak."),
        solution="""WITH days AS (
    SELECT DISTINCT user_id, event_date
    FROM user_events
    WHERE event_type = 'app_open'
),
islands AS (
    SELECT user_id, event_date,
           CAST(JULIANDAY(event_date) AS INTEGER)
             - ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY event_date) AS grp
    FROM days
)
SELECT user_id,
       COUNT(*) AS streak_days,
       MIN(event_date) AS streak_start,
       MAX(event_date) AS streak_end
FROM islands
GROUP BY user_id, grp
ORDER BY streak_days DESC, user_id
LIMIT 10;""",
        trap=("Skipping the DISTINCT means duplicate same-day events inflate every "
              "streak. In gaps-and-islands, dedupe to the date grain first, always."),
        dialect="JULIANDAY is SQLite. PostgreSQL: (event_date::date - ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY event_date)::int) AS grp.",
    ),
    # ------------------------------------------------------------------ 11
    dict(
        id="S11",
        title="Churn set: active in August, silent in September",
        pattern="Anti-join with NOT EXISTS",
        prompt=(
            "How many users transacted in August 2026 but not in September 2026, and "
            "what was their August GMV? Return the count and the total August GMV."),
        contract=("Grain: one summary row. Identity: a user counts once regardless of "
                  "August booking count. Note: NOT IN breaks if the subquery can return "
                  "NULL."),
        solution="""WITH aug AS (
    SELECT user_id, SUM(gmv) AS aug_gmv
    FROM bookings
    WHERE status = 'completed'
      AND booking_ts >= '2026-08-01' AND booking_ts < '2026-09-01'
    GROUP BY user_id
)
SELECT COUNT(*) AS churned_users,
       ROUND(SUM(aug.aug_gmv), 2) AS churned_aug_gmv,
       ROUND(AVG(aug.aug_gmv), 2) AS avg_aug_gmv_per_churned_user
FROM aug
WHERE NOT EXISTS (
    SELECT 1 FROM bookings b2
    WHERE b2.user_id = aug.user_id
      AND b2.status = 'completed'
      AND b2.booking_ts >= '2026-09-01' AND b2.booking_ts < '2026-10-01'
);""",
        trap=("A LEFT JOIN ... IS NULL anti-join forgets the status and date filters "
              "inside the join condition and inherits them into WHERE by accident, "
              "which converts it back into an inner join. Filter the right-hand table "
              "inside the subquery or the ON clause, never in WHERE."),
        dialect="Portable.",
    ),
    # ------------------------------------------------------------------ 12
    dict(
        id="S12",
        title="GMV deciles and per-segment median",
        pattern="NTILE + median",
        prompt=(
            "Per service_type in 2026, bucket users into spend deciles by their total "
            "completed GMV, and return the median user spend per service_type."),
        contract=("Grain: one row per service_type with the median, plus a decile "
                  "distribution. Median of user totals, not median of bookings."),
        solution="""WITH user_spend AS (
    SELECT service_type, user_id, SUM(gmv) AS spend
    FROM bookings
    WHERE status = 'completed'
      AND booking_ts >= '2026-01-01' AND booking_ts < '2027-01-01'
    GROUP BY 1, 2
),
deciles AS (
    SELECT service_type, user_id, spend,
           NTILE(10) OVER (PARTITION BY service_type ORDER BY spend) AS decile
    FROM user_spend
)
SELECT service_type,
       ROUND(MIN(CASE WHEN decile = 10 THEN spend END), 2) AS p90_floor,
       ROUND(AVG(spend), 2) AS mean_spend,
       COUNT(*) AS users,
       ROUND(MAX(CASE WHEN decile = 5 THEN spend END), 2) AS p50_ceiling
FROM deciles
GROUP BY service_type
ORDER BY mean_spend DESC;""",
        trap=("AVG() is not a median, and a decile bucket boundary is not a percentile "
              "value. If the grader wants a true median, say PERCENTILE_CONT(0.5) in "
              "PostgreSQL; in SQLite use ORDER BY spend LIMIT 1 OFFSET (n-1)/2 or the "
              "two-row average."),
        dialect="NTILE is portable. PERCENTILE_CONT is PostgreSQL only; the SQLite median idiom is OFFSET based.",
    ),
    # ------------------------------------------------------------------ 13
    dict(
        id="S13",
        title="Campaign ROI and cost per incremental booking",
        pattern="Business framing of an experiment",
        prompt=(
            "For each campaign, return the cost from campaign_costs, the number of sends, "
            "the number of 7-day bookings, the cost per booking, and the incremental "
            "bookings implied by the treatment-versus-control difference. Use a "
            "per-campaign average GMV per booking of 45,000 IDR to state incremental "
            "revenue and ROI."),
        contract=("Grain: campaign_id. Incremental = treatment rate minus control rate, "
                  "applied to treatment sends. Segmentation cost is sunk; voucher cost "
                  "scales with redemption."),
        solution="""WITH agg AS (
    SELECT campaign_id,
           SUM(CASE WHEN variant = 'treatment' THEN 1 ELSE 0 END) AS n_t,
           SUM(CASE WHEN variant = 'control'   THEN 1 ELSE 0 END) AS n_c,
           SUM(CASE WHEN variant = 'treatment' THEN booked_7d ELSE 0 END) AS conv_t,
           SUM(CASE WHEN variant = 'control'   THEN booked_7d ELSE 0 END) AS conv_c
    FROM campaign_sends
    GROUP BY campaign_id
)
SELECT a.campaign_id,
       c.total_cost_idr,
       a.n_t + a.n_c AS sends,
       ROUND(c.total_cost_idr / NULLIF(a.n_t + a.n_c, 0), 0) AS cost_per_send,
       ROUND(a.conv_t + a.conv_c, 0) AS observed_bookings,
       ROUND(1.0 * a.conv_t / NULLIF(a.n_t, 0) - 1.0 * a.conv_c / NULLIF(a.n_c, 0), 4)
           AS rate_lift,
       ROUND(a.n_t * (1.0 * a.conv_t / NULLIF(a.n_t, 0) - 1.0 * a.conv_c / NULLIF(a.n_c, 0)), 1)
           AS incremental_bookings,
       ROUND(a.n_t * (1.0 * a.conv_t / NULLIF(a.n_t, 0) - 1.0 * a.conv_c / NULLIF(a.n_c, 0)) * 45000, 0)
           AS incremental_gmv_idr,
       ROUND(
           (a.n_t * (1.0 * a.conv_t / NULLIF(a.n_t, 0) - 1.0 * a.conv_c / NULLIF(a.n_c, 0)) * 45000)
           / NULLIF(c.total_cost_idr, 0), 2) AS roi_multiple
FROM agg a
JOIN campaign_costs c ON c.campaign_id = a.campaign_id
ORDER BY roi_multiple DESC;""",
        trap=("Comparing total bookings in the campaign window against the same window "
              "last year and calling the difference incremental. That is seasonality. "
              "Incremental requires a concurrent control, and the denominator for cost "
              "is the treatment population, not the redeemed population."),
        dialect="Portable.",
    ),
    # ------------------------------------------------------------------ 14
    dict(
        id="S14",
        title="The fanout trap: joining a fact to a send table",
        pattern="Pre-aggregate before joining",
        prompt=(
            "Return, per campaign, the 7-day GMV of users who booked after being sent "
            "CMP_WELCOME, alongside sends. The naive join of bookings to campaign_sends "
            "multiplies rows; produce the correct number and be able to explain why."),
        contract=("Grain: campaign_id. Identity: a booking must count once even if the "
                  "user received several sends in the campaign."),
        solution="""WITH sends AS (
    SELECT campaign_id, user_id, MIN(sent_ts) AS first_send_ts
    FROM campaign_sends
    WHERE campaign_id = 'CMP_WELCOME'
    GROUP BY 1, 2
),
post_send_gmv AS (
    SELECT s.campaign_id,
           s.user_id,
           SUM(b.gmv) AS gmv_7d
    FROM sends s
    JOIN bookings b
      ON b.user_id = s.user_id
     AND b.status = 'completed'
     AND b.booking_ts >= s.first_send_ts
     AND JULIANDAY(b.booking_ts) <= JULIANDAY(s.first_send_ts) + 7
    GROUP BY 1, 2
)
SELECT p.campaign_id,
       (SELECT COUNT(*) FROM sends) AS users_sent,
       COUNT(*) AS users_booking_within_7d,
       ROUND(SUM(p.gmv_7d), 2) AS gmv_7d,
       ROUND(SUM(p.gmv_7d) / NULLIF(COUNT(*), 0), 2) AS gmv_per_booking_user
FROM post_send_gmv p
GROUP BY p.campaign_id;""",
        trap=("Joining bookings directly to campaign_sends makes every booking repeat "
              "once per send, so GMV is inflated by the number of sends per user. "
              "Collapse the send side to one row per user first."),
        dialect="JULIANDAY is SQLite; PostgreSQL uses b.booking_ts <= s.first_send_ts + INTERVAL '7 days'.",
    ),
]

DRILLS.append(dict(
    id="S15",
    title="Promo share of GMV by month",
    pattern="Conditional share of total",
    prompt=(
        "For 2026, return one row per month with the GMV from completed bookings that "
        "used a promo code, the total GMV, and the promo share as a percentage rounded "
        "to two decimals. Order by month."),
    contract=("Grain: month. Population: completed bookings in 2026. Identity: booking "
              "level gmv, split by whether promo_code is present."),
    solution="""SELECT substr(booking_ts, 1, 7) AS month,
       ROUND(SUM(CASE WHEN promo_code IS NOT NULL THEN gmv ELSE 0 END), 2) AS promo_gmv,
       ROUND(SUM(gmv), 2) AS total_gmv,
       ROUND(100.0 * SUM(CASE WHEN promo_code IS NOT NULL THEN gmv ELSE 0 END)
             / NULLIF(SUM(gmv), 0), 2) AS promo_share_pct
FROM bookings
WHERE status = 'completed'
  AND booking_ts >= '2026-01-01' AND booking_ts < '2027-01-01'
GROUP BY 1
ORDER BY 1;""",
    trap=("Dividing by COUNT(*) instead of SUM(gmv) turns a value share into an order "
          "share. They answer different questions, and the prompt asked for the value."),
    dialect="Portable. IS NOT NULL works in both engines; promo_code is NULL, never an "
            "empty string.",
))

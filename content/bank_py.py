# -*- coding: utf-8 -*-
"""Ten Python tasks, standard library only.

Deliberately no pandas: the browser runtime loads Python without extra packages, and
the assessment coding environment may not have them either. Every reference function
below is executed by build/verify.py, and its return value becomes the expected output.
"""
import datetime as dt
import math


# ------------------------------------------------------------------ 1
def t1_sessionize(raw):
    rows = []
    for line in raw.strip().splitlines():
        parts = line.strip().split("|")
        if len(parts) != 3:
            continue
        uid, ts, _ev = [p.strip() for p in parts]
        if not uid or not ts:
            continue
        try:
            stamp = dt.datetime.fromisoformat(ts)
        except ValueError:
            continue
        rows.append((uid, stamp))
    if not rows:
        return []
    rows.sort()
    out, last_user, last_ts, sess, count = [], None, None, 0, 0
    for uid, stamp in rows:
        if uid != last_user:
            if last_user is not None:
                out.append([last_user, sess, count])
            last_user, last_ts, sess, count = uid, stamp, 1, 1
        elif (stamp - last_ts).total_seconds() > 30 * 60:
            out.append([last_user, sess, count])
            sess += 1
            count = 1
        else:
            count += 1
        last_ts = stamp
    out.append([last_user, sess, count])
    return out


# ------------------------------------------------------------------ 2
def t2_readout(conv_t, n_t, conv_c, n_c):
    p_t, p_c = conv_t / n_t, conv_c / n_c
    p_pool = (conv_t + conv_c) / (n_t + n_c)
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n_t + 1 / n_c))
    z = (p_t - p_c) / se if se else 0.0
    p_value = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return {"abs_lift_pp": round(100 * (p_t - p_c), 3),
            "rel_lift_pct": round(100 * (p_t - p_c) / p_c, 3),
            "z": round(z, 3),
            "p_value": round(p_value, 3)}


# ------------------------------------------------------------------ 3
def t3_sample_size(baseline, mde_rel, power=0.8):
    z_a = 1.959964
    z_b = {0.8: 0.841621, 0.9: 1.281552}[power]
    p1 = baseline
    p2 = baseline * (1 + mde_rel)
    p_bar = (p1 + p2) / 2
    n = ((z_a * math.sqrt(2 * p_bar * (1 - p_bar))
          + z_b * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))) ** 2) / ((p2 - p1) ** 2)
    return math.ceil(n)


# ------------------------------------------------------------------ 4
def t4_retention(rows):
    """rows: dicts with user, signup (YYYY-MM), active (YYYY-MM)."""
    def idx(a, c):
        ya, ma = int(a[:4]), int(a[5:7])
        yc, mc = int(c[:4]), int(c[5:7])
        return (ya - yc) * 12 + (ma - mc)

    cohort = {r["user"]: r["signup"] for r in rows}
    sizes = {}
    for c in cohort.values():
        sizes[c] = sizes.get(c, 0) + 1

    hits = {}
    for r in rows:
        k = idx(r["active"], cohort[r["user"]])
        if 0 <= k <= 1:
            hits.setdefault((cohort[r["user"]], k), set()).add(r["user"])

    out = []
    for c in sorted(sizes):
        n = sizes[c]
        m0 = round(100 * len(hits.get((c, 0), set())) / n, 1)
        m1 = round(100 * len(hits.get((c, 1), set())) / n, 1)
        out.append([c, n, m0, m1])
    return out


# ------------------------------------------------------------------ 5
def t5_latest(records):
    """records: dicts with user, ts (ISO string), rid. Return [user, rid] sorted by user."""
    best = {}
    for r in records:
        cur = best.get(r["user"])
        if cur is None or (r["ts"], r["rid"]) > (cur["ts"], cur["rid"]):
            best[r["user"]] = r
    return [[u, best[u]["rid"]] for u in sorted(best)]


# ------------------------------------------------------------------ 6
def t6_window(timestamps, window):
    best, start, left = 0, None, 0
    for right, t in enumerate(timestamps):
        while t - timestamps[left] > window:
            left += 1
        if right - left + 1 > best:
            best, start = right - left + 1, timestamps[left]
    return [best, start]


# ------------------------------------------------------------------ 7
def t7_rfm(users):
    """users: dicts with recency_days and orders_90d. Label by simple thresholds."""
    out = []
    for u in users:
        r, f = u["recency_days"], u["orders_90d"]
        if r <= 7 and f >= 3:
            label = "champion"
        elif r <= 14:
            label = "loyal"
        elif r <= 45:
            label = "at_risk"
        else:
            label = "lost"
        out.append([u["user"], label])
    return out


# ------------------------------------------------------------------ 8
def t8_cuped(xs, ys):
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (n - 1)
    var_x = sum((x - mx) ** 2 for x in xs) / (n - 1)
    theta = cov / var_x if var_x else 0.0
    adj = [y - theta * (x - mx) for x, y in zip(xs, ys)]
    var_y = sum((y - my) ** 2 for y in ys) / (n - 1)
    ma = sum(adj) / n
    var_adj = sum((a - ma) ** 2 for a in adj) / (n - 1)
    return [round(theta, 4), round(100 * (1 - var_adj / var_y), 2)]


# ------------------------------------------------------------------ 9
def t9_rolling7(daily):
    """daily: list of [date_str, value] with gaps. Return [date, 7d average] per day."""
    vals = {}
    for d, v in daily:
        vals[dt.date.fromisoformat(d)] = vals.get(dt.date.fromisoformat(d), 0) + v
    start, end = min(vals), max(vals)
    out, day, window = [], start, []
    while day <= end:
        window.append(vals.get(day, 0))
        if len(window) > 7:
            window.pop(0)
        out.append([day.isoformat(), round(sum(window) / len(window), 2)])
        day += dt.timedelta(days=1)
    return out[-3:]


# ------------------------------------------------------------------ 10
def t10_month_counts(lines):
    counts = {}
    for line in lines:
        part = line.split(",")[1].strip() if "," in line else ""
        if not part:
            continue
        try:
            d = dt.date.fromisoformat(part)
        except ValueError:
            continue
        key = "%04d-%02d" % (d.year, d.month)
        counts[key] = counts.get(key, 0) + 1
    return [[k, counts[k]] for k in sorted(counts)]


# ================================================================== metadata
PY_TASKS = [
    dict(
        id="py-1", pool="py", kind="python", title="Sessionise an event log",
        tags="Python  ·  parsing and gaps",
        prompt="Write sessionize(raw) taking a multi-line string of 'user_id|ISO_timestamp|event'. "
               "A new session starts when the gap from the previous event for that user exceeds "
               "30 minutes. Return a list of [user_id, session_number, n_events], session_number "
               "starting at 1 per user, sorted by user_id then session_number. Skip malformed "
               "lines, empty user ids and unparseable timestamps.",
        entry="sessionize", reference_fn=t1_sessionize,
        fixture_py=('RAW = ("u1|2026-09-01T09:00:00|open\\nu1|2026-09-01T09:10:00|search\\n'
                    'u1|2026-09-01T10:05:00|checkout\\nu2|2026-09-01T08:00:00|open\\n'
                    'u2|bogus-timestamp|open\\njunk line without pipes\\n'
                    '|2026-09-01T11:00:00|open\\nu3|2026-09-01T12:00:00|open\\n'
                    'u3|2026-09-01T12:29:00|open\\nu3|2026-09-01T12:31:00|open\\n'
                    'u3|2026-09-02T09:00:00|open")'),
        call="sessionize(RAW)",
        starter="def sessionize(raw):\n    # return list of [user_id, session_number, n_events]\n    pass\n",
        learning=dict(
            concept=["Messy input, a time rule and a strict output format. The grader compares "
                     "values, so an off-by-one in session numbering fails as hard as a wrong parse.",
                     "Two decisions come first: sort by (user, timestamp), and decide whether the "
                     "threshold is strictly greater than 30 minutes. 'Exceeds' means strictly."],
            recipe=["Parse defensively and skip bad lines instead of raising.",
                    "Sort once by (user, timestamp). Everything after that is a single pass.",
                    "Keep the previous timestamp for the current user; open a new session when "
                    "the gap exceeds 1800 seconds.",
                    "Flush the final session after the loop."],
            gotchas=["Forgetting the flush after the loop loses the last session of every user.",
                     "fromisoformat rejects most human date formats. Catch ValueError and skip.",
                     "A line with trailing spaces and an empty user id still has three fields."],
            reference=[["split", "s.split('|') keeps empty fields"],
                       ["delta", "(a - b).total_seconds()"],
                       ["threshold", "exceeds 30 min means > 1800s"],
                       ["flush", "emit the last session explicitly"]],
        ),
        hints=["Sort by user and time first. The rest is a single pass with state.",
               "Track previous timestamp per current user; when the user changes, flush and reset.",
               "Do not forget the final flush after the loop ends."],
    ),
    dict(
        id="py-2", pool="py", kind="python", title="Two-proportion readout",
        tags="Python  ·  statistics without scipy",
        prompt="Write readout(conv_t, n_t, conv_c, n_c) returning a dict with keys "
               "abs_lift_pp, rel_lift_pct, z and p_value. Use the pooled standard error for z "
               "and a two-sided p-value. Round every value to 3 decimals. No scipy: use math.erf.",
        entry="readout", reference_fn=t2_readout,
        fixture_py="FIXTURES = [(120, 500, 98, 500), (45, 400, 30, 400)]",
        call="[readout(*f) for f in FIXTURES]",
        starter="import math\n\ndef readout(conv_t, n_t, conv_c, n_c):\n    # keys: abs_lift_pp, rel_lift_pct, z, p_value\n    pass\n",
        learning=dict(
            concept=["The environment may have only the standard library, so the test is worth "
                     "writing from memory. Two standard errors appear and they are not "
                     "interchangeable: pooled for the test, unpooled for the interval.",
                     "The normal CDF has no math.norm. It is 0.5 * (1 + erf(x / sqrt(2)))."],
            recipe=["p_t and p_c from the counts.",
                    "p_pooled = (conv_t + conv_c) / (n_t + n_c).",
                    "se = sqrt(p_pooled * (1 - p_pooled) * (1/n_t + 1/n_c)).",
                    "z = (p_t - p_c) / se.",
                    "p = 2 * (1 - Phi(|z|)). Round only at the end."],
            gotchas=["Rounding intermediates compounds error. Round the outputs only.",
                     "A zero denominator must be handled or the edge case crashes.",
                     "Using the unpooled error in z is the wrong test."],
            reference=[["Phi(x)", "0.5 * (1 + erf(x/sqrt(2)))"],
                       ["pooled SE", "sqrt(p(1-p)(1/n1+1/n2))"],
                       ["unpooled SE", "sqrt(p1(1-p1)/n1 + p2(1-p2)/n2)"],
                       ["two-sided", "double the upper tail"]],
        ),
        hints=["Compute the pooled rate first; both the standard error and z follow from it.",
               "The CDF is 0.5*(1+erf(z/sqrt(2))). A two-sided p doubles the upper tail.",
               "Round at the return statement, not before."],
    ),
    dict(
        id="py-3", pool="py", kind="python", title="Sample size per arm",
        tags="Python  ·  power calculation",
        prompt="Write sample_size(baseline, mde_rel, power=0.8) returning the integer number of "
               "users needed per arm to detect a relative lift of mde_rel on a baseline rate, "
               "two-sided alpha 0.05. Use z_alpha 1.959964 and z_beta 0.841621 for 80% power "
               "(1.281552 for 90%). Round up.",
        entry="sample_size", reference_fn=t3_sample_size,
        fixture_py="FIXTURES = [(0.02, 0.10), (0.05, 0.05), (0.30, 0.20, 0.9)]",
        call="[sample_size(*f) for f in FIXTURES]",
        starter="import math\n\ndef sample_size(baseline, mde_rel, power=0.8):\n    pass\n",
        learning=dict(
            concept=["Sample size is the price of a detectable effect. The formula balances two "
                     "errors: the chance of a false positive and the chance of missing a real "
                     "effect of the size you care about.",
                     "The practical reading: small relative effects on small rates cost millions "
                     "of users. Say that out loud in an interview and you sound like someone who "
                     "has sized a test before."],
            recipe=["p1 = baseline, p2 = baseline * (1 + mde_rel).",
                    "p_bar = (p1 + p2) / 2.",
                    "n = (z_a*sqrt(2 p_bar (1-p_bar)) + z_b*sqrt(p1(1-p1)+p2(1-p2)))^2 / (p2-p1)^2.",
                    "ceil the result, and quote it per arm."],
            gotchas=["Forgetting to take both standard errors: the first term uses the pooled "
                     "rate, the second uses the two rates separately.",
                     "Quoting total n instead of per-arm n halves the budget plan.",
                     "A relative MDE must be converted to an absolute delta before squaring."],
            reference=[["z_alpha", "1.959964 for 95% two-sided"],
                       ["z_beta", "0.841621 for 80%, 1.281552 for 90%"],
                       ["shortcut", "16 * p(1-p) / delta^2"],
                       ["output", "users per arm, rounded up"]],
        ),
        hints=["Convert the relative lift into an absolute delta before anything else.",
               "The two standard errors are different: pooled for the first term, separate "
               "rates for the second.",
               "Round up at the end. A fractional user is a full user."],
    ),
    dict(
        id="py-4", pool="py", kind="python", title="Cohort retention table",
        tags="Python  ·  index arithmetic",
        prompt="Write retention(rows) where rows are dicts with user, signup (YYYY-MM) and active "
               "(YYYY-MM). Return one row per signup cohort, sorted by cohort: "
               "[cohort, cohort_size, m0_pct, m1_pct], percentages rounded to one decimal, "
               "denominator equal to cohort size.",
        entry="retention", reference_fn=t4_retention,
        fixture_py=('ROWS = [\n'
                    '    {"user": "a", "signup": "2026-01", "active": "2026-01"},\n'
                    '    {"user": "a", "signup": "2026-01", "active": "2026-02"},\n'
                    '    {"user": "b", "signup": "2026-01", "active": "2026-02"},\n'
                    '    {"user": "c", "signup": "2026-01", "active": "2026-03"},\n'
                    '    {"user": "d", "signup": "2026-02", "active": "2026-02"},\n'
                    '    {"user": "e", "signup": "2026-02", "active": "2026-03"},\n'
                    '    {"user": "f", "signup": "2026-02", "active": "2026-03"},\n'
                    '    {"user": "g", "signup": "2026-03", "active": "2026-03"},\n'
                    ']'),
        call="retention(ROWS)",
        starter="def retention(rows):\n    # rows: user, signup, active (YYYY-MM)\n    pass\n",
        learning=dict(
            concept=["Cohort size is fixed at signup, and every later column is a fraction of "
                     "that same base. The month index is arithmetic: 12 times the year difference "
                     "plus the month difference.",
                     "Users with no activity at all still belong in the denominator. That is the "
                     "difference between a cohort table and an activity table."],
            recipe=["Build cohort = user to signup month.",
                    "Count cohort sizes.",
                    "For each row, compute the index and record the user under (cohort, index).",
                    "Per cohort, divide distinct users at index k by cohort size."],
            gotchas=["Dividing by active users instead of cohort size inflates every column.",
                     "A user active in month 3 but not month 1 still counts at index 3 only. Do "
                     "not carry activity forward.",
                     "Duplicate (user, active) rows double-count unless you use a set."],
            reference=[["index", "12*(y2-y1) + (m2-m1)"],
                       ["denominator", "cohort size"],
                       ["M0", "activity in the signup month"],
                       ["set", "dedupe user per (cohort, index)"]],
        ),
        hints=["Fix the denominator first: cohort sizes come from the user list, not from activity.",
               "Month index is 12*(year diff) + (month diff). Write a helper.",
               "Per (cohort, index) keep a set of users so duplicates cannot double-count."],
    ),
    dict(
        id="py-5", pool="py", kind="python", title="Latest record per user",
        tags="Python  ·  dedupe and tie-break",
        prompt="Write latest(records) where each record is a dict with user, ts (ISO string) and "
               "rid. Return a list of [user, rid] for the latest record per user, sorted by user. "
               "Break ties on ts with the higher rid.",
        entry="latest", reference_fn=t5_latest,
        fixture_py=('RECS = [\n'
                    '    {"user": "b", "ts": "2026-09-02T10:00:00", "rid": 3},\n'
                    '    {"user": "a", "ts": "2026-09-01T10:00:00", "rid": 1},\n'
                    '    {"user": "b", "ts": "2026-09-02T10:00:00", "rid": 4},\n'
                    '    {"user": "a", "ts": "2026-08-15T10:00:00", "rid": 2},\n'
                    '    {"user": "c", "ts": "2026-07-20T10:00:00", "rid": 5},\n'
                    ']'),
        call="latest(RECS)",
        starter="def latest(records):\n    # return [[user, rid], ...] sorted by user\n    pass\n",
        learning=dict(
            concept=["Sort then take the last per entity, or compare tuple keys on the fly. The "
                     "requirement that makes it a test rather than an exercise is the tie-break.",
                     "ISO strings sort lexicographically the same way they sort chronologically, "
                     "which is why this works without parsing."],
            recipe=["Keep a dict from user to best record.",
                    "Compare (ts, rid) tuples so the tie-break is automatic.",
                    "Emit sorted by user."],
            gotchas=["Comparing ts only leaves duplicates resolving arbitrarily.",
                     "Mixed date formats break lexicographic ordering. Parse if the format is "
                     "not fixed-width ISO.",
                     "Returning the whole record instead of the requested columns fails the "
                     "output contract."],
            reference=[["sort key", "(ts, rid) as a tuple"],
                       ["dict", "user to best record"],
                       ["output", "only the columns asked for"],
                       ["stability", "tie-break makes it deterministic"]],
        ),
        hints=["A dict from user to best record makes this a single pass.",
               "Compare tuples so timestamp and id are handled together.",
               "Sort the output by user at the end."],
    ),
    dict(
        id="py-6", pool="py", kind="python", title="Busiest window",
        tags="Python  ·  two pointers",
        prompt="Write window_max(timestamps, window) taking sorted integer timestamps and a window "
               "length, returning [max_events, window_start] for the window containing the most "
               "events. Two events exactly window apart count as inside.",
        entry="window_max", reference_fn=t6_window,
        fixture_py="CASES = [([1, 2, 61, 62, 63, 121], 60), ([], 60), ([5], 10)]",
        call="[window_max(*c) for c in CASES]",
        starter="def window_max(timestamps, window):\n    pass\n",
        learning=dict(
            concept=["A sliding window over sorted input is the standard O(n) answer. The left "
                     "pointer advances only while the constraint is violated, so each element "
                     "enters and leaves once.",
                     "The boundary condition is where marks are lost: 'exactly window apart counts "
                     "as inside' means the violation test is strictly greater than window."],
            recipe=["left = 0, best = 0.",
                    "For each right, advance left while ts[right] - ts[left] > window.",
                    "Size is right - left + 1. Track the best and its start.",
                    "Handle the empty input before the loop."],
            gotchas=["Using >= instead of > drops the boundary case and returns a smaller window.",
                     "Assuming sorted input when it is not: sort first, or say the assumption out "
                     "loud.",
                     "An empty list crashes the naive implementation on timestamps[0]."],
            reference=[["complexity", "O(n) after sorting"],
                       ["violation", "ts[r] - ts[l] > window"],
                       ["size", "r - l + 1"],
                       ["boundary", "equal to window is inside"]],
        ),
        hints=["Two pointers, and the left one only moves forward.",
               "The condition to shrink is ts[right] - ts[left] greater than window, strictly.",
               "Guard the empty input before touching index 0."],
    ),
    dict(
        id="py-7", pool="py", kind="python", title="RFM bucket labels",
        tags="Python  ·  rule-based segmentation",
        prompt="Write rfm(users) where users are dicts with user, recency_days and orders_90d. "
               "Label each: champion if recency <= 7 and orders >= 3, loyal if recency <= 14, "
               "at_risk if recency <= 45, otherwise lost. Return [[user, label], ...] in input "
               "order.",
        entry="rfm", reference_fn=t7_rfm,
        fixture_py=('USERS = [\n'
                    '    {"user": "a", "recency_days": 3, "orders_90d": 4},\n'
                    '    {"user": "b", "recency_days": 3, "orders_90d": 1},\n'
                    '    {"user": "c", "recency_days": 12, "orders_90d": 2},\n'
                    '    {"user": "d", "recency_days": 40, "orders_90d": 1},\n'
                    '    {"user": "e", "recency_days": 120, "orders_90d": 0},\n'
                    ']'),
        call="rfm(USERS)",
        starter="def rfm(users):\n    pass\n",
        learning=dict(
            concept=["Rule-based segmentation is order-sensitive: the first matching rule wins, so "
                     "the champion test must include both conditions before the loyal test runs.",
                     "This is the honest version of segmentation in an interview. Clustering is "
                     "for discovery, rules are for campaigns you have to explain to marketing."],
            recipe=["Evaluate rules in priority order with if and elif.",
                    "Combine recency and frequency with and, not or.",
                    "Preserve input order so the output is predictable."],
            gotchas=["Using separate if statements lets a user collect two labels.",
                     "Boundary values are specified as <=, so 7 days is still a champion.",
                     "An 'and' written as 'or' makes almost everyone a champion."],
            reference=[["priority", "if / elif, first match wins"],
                       ["boundaries", "inclusive as written"],
                       ["labels", "fixed vocabulary, exact strings"],
                       ["order", "input order preserved"]],
        ),
        hints=["Use if and elif so only one label can apply.",
               "The champion rule needs both conditions true.",
               "Boundaries are inclusive: exactly 7 days still qualifies."],
    ),
    dict(
        id="py-8", pool="py", kind="python", title="CUPED adjustment",
        tags="Python  ·  variance reduction",
        prompt="Write cuped(xs, ys) returning [theta, variance_reduction_pct], theta rounded to 4 "
               "decimals and the reduction to 2. theta is cov(x,y)/var(x) with sample (n-1) "
               "denominators; the adjusted metric is y - theta*(x - mean x).",
        entry="cuped", reference_fn=t8_cuped,
        fixture_py=("XS = [10, 12, 9, 15, 20, 8, 11, 14, 16, 13]\n"
                    "YS = [11, 16, 8, 19, 22, 10, 14, 15, 21, 12]"),
        call="cuped(XS, YS)",
        starter="def cuped(xs, ys):\n    pass\n",
        learning=dict(
            concept=["CUPED removes the part of the post-period metric that the pre-period "
                     "covariate already explains. Because the covariate is measured before "
                     "randomisation, the adjustment cannot bias the treatment effect.",
                     "The payoff is effective sample size for free: 40% variance reduction is "
                     "roughly the same as a 1.7x larger experiment."],
            recipe=["Means of x and y.",
                    "cov and var with n-1 denominators.",
                    "theta = cov / var_x.",
                    "adjusted = [y - theta*(x - mean_x)].",
                    "variance reduction = 1 - var(adj) / var(y)."],
            gotchas=["Using the population denominator in one place and sample in another makes "
                     "theta slightly wrong and the variance reduction look better than it is.",
                     "Covariate from the experiment period leaks the treatment into the adjustment.",
                     "Rounding theta before applying it changes the adjusted values."],
            reference=[["theta", "cov(x,y) / var(x)"],
                       ["adjust", "y - theta*(x - mean x)"],
                       ["reduction", "1 - var(adj)/var(y)"],
                       ["requirement", "pre-period covariate only"]],
        ),
        hints=["Compute means, then covariance and variance with the same denominator.",
               "theta is the regression slope of y on x. Apply it to the centred covariate.",
               "Report the reduction as a percentage of the raw variance."],
    ),
    dict(
        id="py-9", pool="py", kind="python", title="Rolling seven-day average",
        tags="Python  ·  calendar fill and window",
        prompt="Write rolling7(daily) where daily is a list of [YYYY-MM-DD, value] pairs with "
               "missing dates. Walk every calendar day from the first to the last date, carry a "
               "trailing seven-day mean (growing window at the start), and return the last three "
               "days as [[date, mean], ...] with means rounded to 2 decimals.",
        entry="rolling7", reference_fn=t9_rolling7,
        fixture_py=('DAILY = [["2026-09-01", 10], ["2026-09-02", 20], ["2026-09-04", 30],\n'
                    '         ["2026-09-05", 10], ["2026-09-08", 40], ["2026-09-09", 50]]'),
        call="rolling7(DAILY)",
        starter="import datetime as dt\n\ndef rolling7(daily):\n    pass\n",
        learning=dict(
            concept=["A trailing average needs a calendar, not a list of rows with data. Missing "
                     "days are zeros in the average, and skipping them makes the metric look "
                     "better than it is.",
                     "This is the Python equivalent of the SQL calendar-spine problem, and it "
                     "shows up in every daily-metric dashboard."],
            recipe=["Aggregate values into a dict keyed by date.",
                    "Iterate from min to max date with timedelta(days=1).",
                    "Keep a list of at most seven values, append and pop.",
                    "Average whatever is in the window, which handles the ramp-up."],
            gotchas=["A fixed divisor of seven at the start understates the first days unless the "
                     "prompt says to treat them as partial. Read which one is asked.",
                     "Comparing strings to dates silently mismatches formats.",
                     "Duplicate dates must be summed, not overwritten."],
            reference=[["window", "list of at most 7 values"],
                       ["fill", "dict.get(date, 0)"],
                       ["ramp", "growing window at the start"],
                       ["round", "2 decimals at output"]],
        ),
        hints=["Aggregate into a dict keyed by date first.",
               "Iterate calendar days, not the input rows. Missing days contribute zero.",
               "Keep the window list at seven entries by popping the oldest."],
    ),
    dict(
        id="py-10", pool="py", kind="python", title="Dirty date parsing",
        tags="Python  ·  defensive parsing",
        prompt="Write month_counts(lines) where each line is 'name,date' or malformed. Return "
               "[[YYYY-MM, count], ...] sorted by month, counting only lines whose date parses "
               "as ISO (YYYY-MM-DD). Skip lines with no comma, an empty date, or an invalid date.",
        entry="month_counts", reference_fn=t10_month_counts,
        fixture_py=('LINES = ["a,2026-09-01", "b,2026-09-15", "c,not-a-date", "d,",\n'
                    '         "no comma here", "e,2026-10-02", "f,2026-02-30", "g,2026-08-31"]'),
        call="month_counts(LINES)",
        starter="import datetime as dt\n\ndef month_counts(lines):\n    pass\n",
        learning=dict(
            concept=["Defensive parsing is graded as much as the counting. The task includes "
                     "three kinds of bad input on purpose: no comma, empty field, and a date that "
                     "looks valid but is not.",
                     "2026-02-30 is the interesting case. fromisoformat rejects it, so a correct "
                     "implementation drops it rather than producing a February count."],
            recipe=["Split on the comma and check there are at least two parts.",
                    "Strip the date field and skip if empty.",
                    "Parse with date.fromisoformat inside try/except ValueError.",
                    "Key the count by year and month, then sort keys."],
            gotchas=["Splitting and indexing without checking raises IndexError on a comma-less "
                     "line.",
                     "A regex that matches the shape of a date accepts 2026-02-30. Parsing does "
                     "not.",
                     "Sorting string keys works for ISO months and fails for formats like '9/1'."],
            reference=[["parse", "date.fromisoformat in try/except"],
                       ["skip", "empty, malformed, impossible dates"],
                       ["key", "%04d-%02d formatting"],
                       ["sort", "string sort works for ISO"]],
        ),
        hints=["Check for the comma before splitting by index.",
               "Wrap the parse in try/except and drop failures silently.",
               "Key by formatted year and month so sorting is lexicographic."],
    ),
]

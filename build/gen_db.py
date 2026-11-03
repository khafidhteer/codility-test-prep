# -*- coding: utf-8 -*-
"""Builds the assessment database embedded in the web app.

Deliberately the same shape as practice/grab_like.db but a shorter window and a
different seed, so the mock feels like a fresh dataset rather than a repeat of
the drills you already ran.

Run: python3 build/gen_db.py
Out: data/mock.db
"""
import datetime as dt
import os
import random
import sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DB = os.path.join(ROOT, "data", "mock.db")

rng = random.Random(7741)

CITIES = [("Jakarta", 0.40), ("Bandung", 0.13), ("Surabaya", 0.14),
          ("Medan", 0.09), ("Semarang", 0.08), ("Makassar", 0.06),
          ("Denpasar", 0.06), ("Yogyakarta", 0.04)]
CITY_NAMES = [c for c, _ in CITIES]
CITY_W = [w for _, w in CITIES]

CHANNELS = ["organic", "referral", "paid_social", "grab_ads", "partner"]
SERVICES = ["Mobility", "Food", "Mart", "Express", "PayLater"]
SERVICE_W = [0.45, 0.35, 0.10, 0.07, 0.03]

START = dt.date(2025, 4, 1)
END = dt.date(2026, 9, 30)


def daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += dt.timedelta(days=1)


def main():
    os.makedirs(os.path.dirname(DB), exist_ok=True)
    if os.path.exists(DB):
        os.remove(DB)
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.executescript("""
    DROP TABLE IF EXISTS users;
    DROP TABLE IF EXISTS bookings;
    DROP TABLE IF EXISTS campaign_sends;
    DROP TABLE IF EXISTS user_events;
    DROP TABLE IF EXISTS campaign_costs;

    CREATE TABLE users (
        user_id      INTEGER PRIMARY KEY,
        signup_date  TEXT NOT NULL,
        city         TEXT NOT NULL,
        country      TEXT NOT NULL,
        channel      TEXT NOT NULL,
        is_unlimited INTEGER NOT NULL
    );

    CREATE TABLE bookings (
        booking_id   INTEGER PRIMARY KEY,
        user_id      INTEGER NOT NULL,
        service_type TEXT NOT NULL,
        booking_ts   TEXT NOT NULL,
        gmv          REAL NOT NULL,
        promo_code   TEXT,
        status       TEXT NOT NULL
    );

    CREATE TABLE campaign_sends (
        send_id     INTEGER PRIMARY KEY,
        campaign_id TEXT NOT NULL,
        user_id     INTEGER NOT NULL,
        variant     TEXT NOT NULL,
        sent_ts     TEXT NOT NULL,
        opened      INTEGER NOT NULL,
        clicked     INTEGER NOT NULL,
        redeemed    INTEGER NOT NULL,
        booked_7d   INTEGER NOT NULL
    );

    CREATE TABLE user_events (
        user_id    INTEGER NOT NULL,
        event_date TEXT NOT NULL,
        event_type TEXT NOT NULL
    );

    CREATE TABLE campaign_costs (
        campaign_id    TEXT PRIMARY KEY,
        region         TEXT NOT NULL,
        total_cost_idr REAL NOT NULL,
        sent_at        TEXT NOT NULL
    );
    """)

    users, uid = [], 5000
    for i in range(1100):
        signup = START + dt.timedelta(days=rng.randrange((END - START).days + 1))
        users.append((uid + i, signup.isoformat(), rng.choices(CITY_NAMES, CITY_W)[0],
                      "ID", rng.choices(CHANNELS, [0.38, 0.14, 0.22, 0.18, 0.08])[0],
                      1 if rng.random() < 0.2 else 0))
    cur.executemany("INSERT INTO users VALUES (?,?,?,?,?,?)", users)

    bookings, bid = [], 1
    for u in users:
        uid_, signup, city, _c, _ch, unlimited = u
        signup_d = dt.date.fromisoformat(signup)
        base = {"organic": 1.0, "referral": 1.15, "paid_social": 0.7,
                "grab_ads": 0.85, "partner": 0.9}[_ch] * (1.9 if unlimited else 1.0)
        lifetime = min((END - signup_d).days, int(rng.expovariate(1.0 / (40 * base))))
        churn = signup_d + dt.timedelta(days=lifetime)
        tenure = 0
        for d in daterange(signup_d, min(churn, END)):
            if rng.random() < 0.22 * base * (0.45 + 0.55 * (2.718 ** (-tenure / 45.0))):
                for _ in range(rng.choice([1, 1, 1, 2, 2])):
                    svc = rng.choices(SERVICES, SERVICE_W)[0]
                    ts = dt.datetime(d.year, d.month, d.day, rng.randrange(6, 23),
                                     rng.randrange(60), rng.randrange(60))
                    gmv = round({"Mobility": rng.uniform(9000, 95000),
                                 "Food": rng.uniform(18000, 260000),
                                 "Mart": rng.uniform(25000, 420000),
                                 "Express": rng.uniform(12000, 60000),
                                 "PayLater": rng.uniform(40000, 600000)}[svc], 2)
                    promo = "PROMO_%02d" % rng.randrange(1, 13) if rng.random() < 0.22 else None
                    status = rng.choices(["completed", "cancelled", "driver_no_show"],
                                         [0.93, 0.05, 0.02])[0]
                    bookings.append((bid, uid_, svc, ts.strftime("%Y-%m-%d %H:%M:%S"),
                                     gmv, promo, status))
                    bid += 1
            tenure += 1
    cur.executemany("INSERT INTO bookings VALUES (?,?,?,?,?,?,?)", bookings)

    # ---------------------------------------------------------------- campaign
    SEND_WELCOME = "2026-06-15 09:00:00"
    recent = [u for u in users if u[1] >= "2026-02-01"]
    sends, sid = [], 1
    for u in recent:
        variant = "treatment" if rng.random() < 0.5 else "control"
        opened = 1 if rng.random() < (0.44 if variant == "treatment" else 0.20) else 0
        clicked = 1 if (opened and rng.random() < (0.34 if variant == "treatment" else 0.27)) else 0
        redeemed = 1 if (clicked and rng.random() < (0.52 if variant == "treatment" else 0.44)) else 0
        booked = 1 if rng.random() < (0.30 if variant == "treatment" else 0.22) else 0
        sends.append((sid, "CMP_WELCOME", u[0], variant, SEND_WELCOME,
                      opened, clicked, redeemed, booked))
        sid += 1
    cur.executemany("INSERT INTO campaign_sends VALUES (?,?,?,?,?,?,?,?,?)", sends)
    n_t = sum(1 for s in sends if s[3] == "treatment")
    n_redeem = sum(s[7] for s in sends)
    cur.execute("INSERT INTO campaign_costs VALUES (?,?,?,?)",
                ("CMP_WELCOME", "ID-Jakarta", round(len(sends) * 150 + n_redeem * 9000, 2),
                 SEND_WELCOME))

    # ---------------------------------------------------------------- streaks
    ev = []
    for u in rng.sample(users, 260):
        start = max(dt.date.fromisoformat(u[1]), dt.date(2026, 7, 1))
        s0 = start + dt.timedelta(days=rng.randrange(0, 40))
        for k in range(rng.choice([1, 2, 3, 4, 5, 6, 8, 10, 13])):
            d = s0 + dt.timedelta(days=k)
            if d > END:
                break
            ev.append((u[0], d.isoformat(), "app_open"))
            if rng.random() < 0.35:
                ev.append((u[0], d.isoformat(), "search"))
    cur.executemany("INSERT INTO user_events VALUES (?,?,?)", ev)

    con.commit()
    for t in ("users", "bookings", "campaign_sends", "user_events", "campaign_costs"):
        print("%-16s %6d" % (t, cur.execute("SELECT COUNT(*) FROM %s" % t).fetchone()[0]))
    con.close()
    print("size: %.0f KB -> %s" % (os.path.getsize(DB) / 1024, DB))


if __name__ == "__main__":
    main()

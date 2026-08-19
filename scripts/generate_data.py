#!/usr/bin/env python3
"""Generate reproducible synthetic marketing data for the project."""

from __future__ import annotations

import argparse
import csv
import math
import random
import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta
from pathlib import Path

SEED = 20260819
START = date(2026, 2, 1)
END = date(2026, 7, 31)
COUNTRIES = ["India", "United States", "United Kingdom", "Germany", "Singapore"]
COUNTRY_WEIGHTS = [0.42, 0.25, 0.14, 0.11, 0.08]
DEVICES = ["Android", "iOS", "Desktop"]
DEVICE_WEIGHTS = [0.52, 0.28, 0.20]
CHANNELS = ["Google Ads", "Meta Ads", "Organic Search", "Email", "Referral", "Direct"]
CHANNEL_WEIGHTS = [0.24, 0.19, 0.23, 0.11, 0.08, 0.15]
CITY_BY_COUNTRY = {
    "India": ["Bengaluru", "Mumbai", "Delhi", "Hyderabad"],
    "United States": ["New York", "San Francisco", "Austin", "Chicago"],
    "United Kingdom": ["London", "Manchester", "Bristol"],
    "Germany": ["Berlin", "Munich", "Hamburg"],
    "Singapore": ["Singapore"],
}


def ident(prefix: str, number: int) -> str:
    return f"{prefix}_{number:07d}"


def write_csv(output: Path, name: str, rows: list[dict]) -> None:
    path = output / f"{name}.csv"
    fields = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"{path}: {len(rows):,} rows")


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def main(output: Path, customer_count: int) -> None:
    rng = random.Random(SEED)
    output.mkdir(parents=True, exist_ok=True)

    campaigns = [
        ("cmp_001", "Always_On_Search", "Google Ads", "Google Ads", 75000),
        ("cmp_002", "Brand_Search", "Google Ads", "Google Ads", 42000),
        ("cmp_003", "Meta_Prospecting", "Meta Ads", "Meta Ads", 60000),
        ("cmp_004", "Meta_Summer_Lift", "Meta Ads", "Meta Ads", 70000),
        ("cmp_005", "Organic_Content", "Organic Search", "Organic Search", 8000),
        ("cmp_006", "Lifecycle_Email", "Email", "Email", 9000),
        ("cmp_007", "Partner_Referral", "Referral", "Referral", 12000),
        ("cmp_008", "Direct_Unattributed", "Direct", "Direct", 0),
    ]
    campaign_by_channel = defaultdict(list)
    for campaign in campaigns:
        campaign_by_channel[campaign[3]].append(campaign[0])

    customers = []
    for number in range(1, customer_count + 1):
        country = rng.choices(COUNTRIES, COUNTRY_WEIGHTS)[0]
        device = rng.choices(DEVICES, DEVICE_WEIGHTS)[0]
        channel = rng.choices(CHANNELS, CHANNEL_WEIGHTS)[0]
        signup = START - timedelta(days=rng.randint(0, 300))
        customers.append({
            "customer_id": ident("cus", number), "signup_date": signup.isoformat(),
            "country": country, "city": rng.choice(CITY_BY_COUNTRY[country]),
            "age_group": rng.choice(["18-24", "25-34", "25-34", "35-44", "45-54", "55+"]),
            "device_type": device, "acquisition_channel": channel,
            "customer_segment": rng.choices(["New", "Occasional", "Loyal", "High Value"], [0.3, 0.38, 0.24, 0.08])[0],
        })

    sessions, funnel, conversions = [], [], []
    session_number = conversion_number = 0
    product_ids = [f"prd_{n:03d}" for n in range(1, 21)]
    customer_lookup = {row["customer_id"]: row for row in customers}
    customer_ids = list(customer_lookup)

    for day in daterange(START, END):
        weekly = 1.12 if day.weekday() in (5, 6) else 1.0
        monthly = 1 + 0.09 * math.sin((day - START).days * 2 * math.pi / 30)
        count = max(25, int(customer_count * 0.042 * weekly * monthly + rng.gauss(0, 6)))
        for _ in range(count):
            session_number += 1
            customer_id = rng.choice(customer_ids)
            customer = customer_lookup[customer_id]
            device = customer["device_type"] if rng.random() < 0.86 else rng.choice(DEVICES)
            country = customer["country"] if rng.random() < 0.91 else rng.choices(COUNTRIES, COUNTRY_WEIGHTS)[0]
            channel_weights = list(CHANNEL_WEIGHTS)
            if date(2026, 6, 15) <= day <= date(2026, 6, 30):
                channel_weights[2] *= 0.50  # simulated ranking change
            channel = rng.choices(CHANNELS, channel_weights)[0]
            campaign_id = rng.choice(campaign_by_channel[channel])
            if channel == "Meta Ads" and day >= date(2026, 7, 1) and rng.random() < 0.62:
                campaign_id = "cmp_004"
            if date(2026, 5, 10) <= day <= date(2026, 5, 16) and rng.random() < 0.22:
                campaign_id = ""  # attribution tracking failure
            stamp = datetime.combine(day, time(rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59)))
            session_id = ident("ses", session_number)
            sessions.append({
                "session_id": session_id, "customer_id": customer_id, "timestamp": stamp.isoformat(),
                "device": device, "country": country, "traffic_source": channel,
                "campaign_id": campaign_id, "landing_page": rng.choice(["/", "/pricing", "/products", "/sale"]),
                "session_duration_seconds": max(5, int(rng.lognormvariate(4.7, 0.65))),
                "pages_viewed": max(1, min(18, int(rng.gauss(4.2, 2.1)))),
            })
            steps = ["landing_page"]
            if rng.random() < 0.72: steps.append("product_view")
            if len(steps) == 2 and rng.random() < 0.38: steps.append("add_to_cart")
            if len(steps) == 3 and rng.random() < 0.61: steps.append("checkout_started")
            payment_probability = 0.82
            if device == "Android" and date(2026, 7, 20) <= day <= date(2026, 7, 26):
                payment_probability = 0.42
            if len(steps) == 4 and rng.random() < payment_probability: steps.append("payment_started")
            purchase_probability = 0.80
            if country == "India" and date(2026, 7, 20) <= day <= date(2026, 7, 26):
                purchase_probability *= 0.62
            if campaign_id == "cmp_004" and day >= date(2026, 7, 1):
                purchase_probability = min(0.96, purchase_probability * 1.22)
            if len(steps) == 5 and rng.random() < purchase_probability: steps.append("purchase_completed")
            for step_index, event in enumerate(steps):
                funnel.append({"customer_id": customer_id, "session_id": session_id,
                               "timestamp": (stamp + timedelta(seconds=step_index * rng.randint(20, 90))).isoformat(),
                               "event_name": event})
            if steps[-1] == "purchase_completed":
                conversion_number += 1
                base = rng.lognormvariate(4.2, 0.48)
                if country == "India": base *= 0.72
                conversions.append({
                    "conversion_id": ident("cnv", conversion_number), "session_id": session_id,
                    "customer_id": customer_id, "timestamp": (stamp + timedelta(minutes=rng.randint(3, 18))).isoformat(),
                    "product_id": rng.choice(product_ids), "revenue": f"{base:.2f}",
                    "discount": f"{rng.choice([0, 0, 0, 5, 10, 15]):.2f}", "conversion_type": "purchase",
                })

    daily_metrics = []
    campaign_totals = defaultdict(lambda: defaultdict(float))
    campaign_meta = {row[0]: row for row in campaigns}
    for day in daterange(START, END):
        for campaign_id, _, platform, channel, _ in campaigns:
            impressions = max(100, int(rng.gauss(4500, 700)))
            ctr = 0.035 if channel in ("Google Ads", "Meta Ads") else 0.018
            clicks = max(1, int(impressions * max(0.005, rng.gauss(ctr, 0.005))))
            cpc = {"Google Ads": 1.45, "Meta Ads": 1.10}.get(channel, 0.20)
            if channel == "Google Ads" and date(2026, 6, 1) <= day <= date(2026, 6, 14): cpc *= 1.38
            spend = clicks * max(0, rng.gauss(cpc, cpc * 0.08))
            conv = max(0, int(clicks * rng.uniform(0.025, 0.055)))
            revenue = conv * rng.uniform(55, 95)
            row = {"date": day.isoformat(), "campaign_id": campaign_id, "impressions": impressions,
                   "clicks": clicks, "spend": f"{spend:.2f}", "conversions": conv, "revenue": f"{revenue:.2f}"}
            daily_metrics.append(row)
            for key in ("impressions", "clicks", "spend", "conversions", "revenue"):
                campaign_totals[campaign_id][key] += float(row[key])

    campaign_rows = []
    for campaign_id, name, platform, channel, budget in campaigns:
        totals = campaign_totals[campaign_id]
        campaign_rows.append({"campaign_id": campaign_id, "campaign_name": name, "platform": platform,
                              "channel": channel, "start_date": START.isoformat(), "end_date": END.isoformat(),
                              "budget": f"{budget:.2f}", "spend": f"{totals['spend']:.2f}",
                              "impressions": int(totals["impressions"]), "clicks": int(totals["clicks"]),
                              "conversions": int(totals["conversions"]), "revenue": f"{totals['revenue']:.2f}"})

    reviews = []
    positive = ["Easy to use and fast", "Great offers and smooth checkout", "Love the new design"]
    negative = ["Payment keeps failing on Android", "App crash during checkout", "Login is slow", "Refund is delayed"]
    for number in range(1, 701):
        review_day = START + timedelta(days=rng.randint(0, (END - START).days))
        incident = date(2026, 7, 20) <= review_day <= date(2026, 7, 31)
        bad = rng.random() < (0.62 if incident else 0.18)
        reviews.append({"review_id": ident("rev", number), "timestamp": datetime.combine(review_day, time(rng.randint(0, 23))).isoformat(),
                        "rating": rng.choice([1, 2]) if bad else rng.choice([4, 5]),
                        "review_text": rng.choice(negative if bad else positive), "app_version": "6.4.0" if incident else "6.3.2",
                        "device": rng.choices(DEVICES, [0.7, 0.2, 0.1])[0], "country": rng.choices(COUNTRIES, COUNTRY_WEIGHTS)[0]})

    experiments = []
    for number, customer in enumerate(rng.sample(customers, min(900, len(customers))), 1):
        variant = "treatment" if number % 2 == 0 else "control"
        probability = 0.14 if variant == "treatment" else 0.10
        converted = int(rng.random() < probability)
        experiments.append({"experiment_id": "exp_checkout_copy_001", "experiment_name": "Checkout reassurance copy",
                            "variant": variant, "customer_id": customer["customer_id"], "exposure_date": "2026-07-01",
                            "conversion": converted, "revenue": f"{rng.uniform(45, 110):.2f}" if converted else "0.00"})

    incidents = [
        {"incident_id": "inc_001", "incident_date": "2026-07-20", "title": "Android checkout regression", "description": "Payment-start events and completed purchases fell after app 6.4.0 rollout.", "affected_metric": "checkout_completion_rate", "affected_channel": "All", "root_cause": "Android payment SDK regression", "resolution": "Rollback SDK and release 6.4.1", "impact": "High"},
        {"incident_id": "inc_002", "incident_date": "2026-06-01", "title": "Google Ads auction inflation", "description": "Search CPC increased while conversion volume remained broadly flat.", "affected_metric": "cpc", "affected_channel": "Google Ads", "root_cause": "Competitor bidding pressure", "resolution": "Tighten bids and negative keywords", "impact": "Medium"},
        {"incident_id": "inc_003", "incident_date": "2026-06-15", "title": "Organic ranking decline", "description": "Organic sessions declined following a simulated ranking update.", "affected_metric": "sessions", "affected_channel": "Organic Search", "root_cause": "Search ranking change", "resolution": "Refresh affected landing pages", "impact": "Medium"},
    ]
    metric_definitions = [
        ("revenue", "Sum of recognized purchase revenue", "SUM(conversions.revenue)", "conversions.revenue", "country,device,channel,campaign,product", "Finance Analytics"),
        ("conversion_rate", "Share of sessions producing a purchase", "purchase sessions / sessions", "sessions.session_id; conversions.session_id", "country,device,channel,campaign", "Growth Analytics"),
        ("average_order_value", "Average revenue per purchase", "revenue / conversions", "conversions.revenue; conversions.conversion_id", "country,device,channel,campaign,product", "Finance Analytics"),
        ("ctr", "Share of impressions resulting in clicks", "clicks / impressions", "daily_campaign_metrics.clicks; daily_campaign_metrics.impressions", "campaign,channel,date", "Performance Marketing"),
        ("cpc", "Average advertising cost per click", "spend / clicks", "daily_campaign_metrics.spend; daily_campaign_metrics.clicks", "campaign,channel,date", "Performance Marketing"),
        ("roas", "Revenue returned per unit of advertising spend", "revenue / spend", "daily_campaign_metrics.revenue; daily_campaign_metrics.spend", "campaign,channel,date", "Performance Marketing"),
        ("checkout_completion_rate", "Share of checkout starts ending in purchase", "purchase_completed / checkout_started", "funnel_events.event_name", "country,device,channel,date", "Product Analytics"),
    ]
    metric_rows = [{"metric_name": x[0], "definition": x[1], "formula": x[2], "required_columns": x[3], "allowed_dimensions": x[4], "business_context": "Official project KPI", "owner": x[5]} for x in metric_definitions]
    ground_truth = [
        {"scenario_id": "scn_001", "start_date": "2026-07-20", "end_date": "2026-07-26", "affected_metric": "checkout_completion_rate", "affected_dimension": "device=Android", "expected_direction": "decrease", "root_cause": "Android payment SDK regression", "severity": "high"},
        {"scenario_id": "scn_002", "start_date": "2026-06-01", "end_date": "2026-06-14", "affected_metric": "cpc", "affected_dimension": "channel=Google Ads", "expected_direction": "increase", "root_cause": "Competitor bidding pressure", "severity": "medium"},
        {"scenario_id": "scn_003", "start_date": "2026-06-15", "end_date": "2026-06-30", "affected_metric": "sessions", "affected_dimension": "channel=Organic Search", "expected_direction": "decrease", "root_cause": "Search ranking change", "severity": "medium"},
        {"scenario_id": "scn_004", "start_date": "2026-05-10", "end_date": "2026-05-16", "affected_metric": "attribution_completeness", "affected_dimension": "campaign_id=NULL", "expected_direction": "decrease", "root_cause": "Campaign attribution tracking failure", "severity": "medium"},
        {"scenario_id": "scn_005", "start_date": "2026-07-20", "end_date": "2026-07-31", "affected_metric": "negative_review_rate", "affected_dimension": "topic=payment/crash/login/refund", "expected_direction": "increase", "root_cause": "Android checkout regression", "severity": "high"},
        {"scenario_id": "scn_006", "start_date": "2026-07-01", "end_date": "2026-07-31", "affected_metric": "conversion_rate", "affected_dimension": "campaign=Meta_Summer_Lift", "expected_direction": "increase", "root_cause": "High-performing Meta creative", "severity": "positive"},
        {"scenario_id": "scn_007", "start_date": "2026-07-20", "end_date": "2026-07-26", "affected_metric": "revenue", "affected_dimension": "country=India", "expected_direction": "decrease", "root_cause": "Payment completion failure concentrated in India", "severity": "high"},
    ]

    for name, rows in (("customers", customers), ("sessions", sessions), ("conversions", conversions),
                       ("campaigns", campaign_rows), ("daily_campaign_metrics", daily_metrics),
                       ("funnel_events", funnel), ("app_reviews", reviews), ("experiments", experiments),
                       ("marketing_incidents", incidents), ("metric_definitions", metric_rows),
                       ("anomaly_ground_truth", ground_truth)):
        write_csv(output, name, rows)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/synthetic"))
    parser.add_argument("--customers", type=int, default=1500)
    args = parser.parse_args()
    main(args.output, args.customers)

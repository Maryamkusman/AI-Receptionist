PLANS = {
    "starter": {
        "label": "Starter", "setup": 500, "monthly": 199,
        "features": {"text", "instagram", "booking", "deposits", "dashboard"},
    },
    "pro": {
        "label": "Pro", "setup": 1000, "monthly": 399,
        "features": {"text", "instagram", "booking", "deposits", "dashboard", "voice", "refill"},
    },
    "growth": {
        "label": "Growth", "setup": 1500, "monthly": 699,
        "features": {"text", "instagram", "booking", "deposits", "dashboard", "voice", "refill",
                     "nudges", "multi_location", "performance_review"},
    },
}


def has_feature(salon, feature: str) -> bool:
    return feature in PLANS.get(salon.plan, PLANS["pro"])["features"]

"""
Two-layer betting model for UFC fight markets.

Layer 1 (market baseline): de-vig the moneyline to get each fighter's fair
win probability. Method-of-victory and "fight distance"/round-total props
are reported at their raw market-implied probability (Layer 1 = market for
these, since there's no generative model linking them to win probability
without a joint model).

Layer 2 (research tilt): a small, explicitly-justified percentage-point
adjustment to the win probability based on team-news/form research not yet
reflected in Layer 1 (injuries, recent form, layoffs, style matchups).
Method-of-victory props for a fighter are rescaled by that fighter's
Layer2/Layer1 win-probability ratio (their method mix is assumed unchanged,
just their overall chance of winning shifts). The "fight distance" market
gets its own small explicit tilt where research specifically supports a
faster/slower finish than the market price implies.

Usage: python3 model.py
"""


def american_to_prob(odds):
    if odds > 0:
        return 100 / (odds + 100)
    return -odds / (-odds + 100)


def american_to_decimal(odds):
    if odds > 0:
        return 1 + odds / 100
    return 1 + 100 / (-odds)


def devig(probs):
    s = sum(probs)
    return [p / s for p in probs]


def fair_odds(p):
    if p <= 0 or p >= 1:
        return "n/a"
    if p >= 0.5:
        return f"{-round(p / (1 - p) * 100):.0f}"
    return f"+{round((1 - p) / p * 100):.0f}"


def edge_report(model_prob, american_odds):
    implied = american_to_prob(american_odds)
    decimal = american_to_decimal(american_odds)
    edge = model_prob - implied
    ev = model_prob * decimal - 1
    return {
        "model_prob": model_prob,
        "implied_prob": implied,
        "edge_pp": edge * 100,
        "ev_per_dollar": ev,
        "american_odds": american_odds,
        "decimal_odds": decimal,
    }


def print_edge_line(label, rep):
    print(
        f"  {label:32s} model={rep['model_prob']*100:5.1f}%  implied={rep['implied_prob']*100:5.1f}%  "
        f"edge={rep['edge_pp']:+5.1f}pp  EV/$1={rep['ev_per_dollar']:+.3f}  @ {rep['american_odds']:+d}"
    )


def run_fight(name, fighter_a, fighter_b, rounds, ml_odds,
              method_odds_a=None, method_odds_b=None,
              distance_market=None,
              win_tilt=0.0, tilt_desc="",
              distance_tilt=0.0, distance_tilt_desc=""):
    """
    ml_odds: (odds_a, odds_b) moneyline American odds
    method_odds_a/b: dict {prop_label: american_odds} for "fighter wins by <method/prop>"
        markets quoted for that fighter only (e.g. {"KO/TKO": -210}).
    distance_market: dict with 'yes_label'/'no_label' (longer vs shorter fight)
        and 'yes_odds'/'no_odds' (either may be None if only one side is quoted).
    win_tilt: pp added to fighter_a's Layer-1 win probability for Layer 2
        (positive favors A), then renormalized.
    distance_tilt: pp added to the "yes" (longer-fight) probability for Layer 2.
    """
    print("=" * 70)
    print(f"{name}  ({rounds}-round fight)")
    print("=" * 70)

    p1_a, p1_b = devig([american_to_prob(o) for o in ml_odds])
    print(f"Layer 1 (de-vigged moneyline): {fighter_a} {p1_a*100:.1f}% / {fighter_b} {p1_b*100:.1f}%")
    print("  -- Moneyline edge vs quoted (Layer 1; near-zero = just the vig) --")
    print_edge_line(f"{fighter_a} ML", edge_report(p1_a, ml_odds[0]))
    print_edge_line(f"{fighter_b} ML", edge_report(p1_b, ml_odds[1]))

    p2_a = min(max(p1_a + win_tilt, 0.01), 0.99)
    p2_b = 1 - p2_a
    print(f"\nLayer 2 (research tilt: {tilt_desc})")
    print(f"  Model win prob: {fighter_a} {p2_a*100:.1f}% / {fighter_b} {p2_b*100:.1f}%")
    print("  -- Moneyline edge vs quoted (Layer 2) --")
    print_edge_line(f"{fighter_a} ML", edge_report(p2_a, ml_odds[0]))
    print_edge_line(f"{fighter_b} ML", edge_report(p2_b, ml_odds[1]))

    for fighter, method_odds, p1, p2 in (
        (fighter_a, method_odds_a, p1_a, p2_a),
        (fighter_b, method_odds_b, p1_b, p2_b),
    ):
        if not method_odds:
            continue
        scale = p2 / p1
        print(f"\n  -- {fighter} method/prop odds (Layer 2 scales Layer 1 by x{scale:.3f}) --")
        for label, odds in method_odds.items():
            l1 = american_to_prob(odds)
            l2 = l1 * scale
            print_edge_line(f"{fighter} {label}", edge_report(l2, odds))

    if distance_market:
        dm = distance_market
        if dm.get("yes_odds") is not None and dm.get("no_odds") is not None:
            d1_yes, d1_no = devig([american_to_prob(dm["yes_odds"]), american_to_prob(dm["no_odds"])])
        elif dm.get("yes_odds") is not None:
            d1_yes = american_to_prob(dm["yes_odds"])
            d1_no = 1 - d1_yes
        else:
            d1_no = american_to_prob(dm["no_odds"])
            d1_yes = 1 - d1_no

        d2_yes = min(max(d1_yes + distance_tilt, 0.01), 0.99)
        d2_no = 1 - d2_yes
        print(f"\n  -- {dm['label']} (Layer 2 tilt: {distance_tilt_desc}) --")
        print(f"  Layer 1: {dm['yes_label']} {d1_yes*100:.1f}% / {dm['no_label']} {d1_no*100:.1f}%")
        print(f"  Layer 2: {dm['yes_label']} {d2_yes*100:.1f}% / {dm['no_label']} {d2_no*100:.1f}%")
        if dm.get("yes_odds") is not None:
            print_edge_line(dm["yes_label"], edge_report(d2_yes, dm["yes_odds"]))
        if dm.get("no_odds") is not None:
            print_edge_line(dm["no_label"], edge_report(d2_no, dm["no_odds"]))
        print(f"  Fair odds -> {dm['yes_label']}: {fair_odds(d2_yes)}  /  {dm['no_label']}: {fair_odds(d2_no)}")

    print()
    return {"p1_a": p1_a, "p1_b": p1_b, "p2_a": p2_a, "p2_b": p2_b}


if __name__ == "__main__":
    # ---- Ilia Topuria vs Justin Gaethje - Lightweight Title Unification (5 rounds) ----
    run_fight(
        "Ilia Topuria vs Justin Gaethje", "Topuria", "Gaethje", rounds=5,
        ml_odds=(-525, 380),
        method_odds_a={"by KO/TKO": -210},
        method_odds_b={"by KO/TKO": 550},
        distance_market={
            "label": "Fight Distance",
            "yes_label": "Goes the distance",
            "no_label": "Ends inside distance",
            "yes_odds": None,
            "no_odds": -1200,
        },
        win_tilt=0.02,
        tilt_desc="Topuria 17-0, on a 9-fight UFC win streak with 3 consecutive finishes "
        "of former/current champs (Volkanovski, Holloway, Oliveira); Gaethje is 0-2 in "
        "undisputed title fights and dealing with fight-week personal-life distractions",
        distance_tilt=-0.017,
        distance_tilt_desc="Topuria's recent finishing rate vs elite competition suggests "
        "the -1200 'ends inside distance' price may be slightly conservative",
    )

    # ---- Alex Pereira vs Ciryl Gane - Interim Heavyweight Title (5 rounds) ----
    run_fight(
        "Alex Pereira vs Ciryl Gane", "Pereira", "Gane", rounds=5,
        ml_odds=(-110, -110),
        method_odds_a={"by KO/TKO": 140},
        method_odds_b={"by Decision": 275},
        distance_market=None,
        win_tilt=-0.02,
        tilt_desc="Pereira (38) is moving up two weight classes to heavyweight for the "
        "first time against a younger, technically sharper Gane who profiles well over "
        "5 rounds; market already pick'em so this is a small lean only",
    )

    # ---- Sean O'Malley vs Aiemann Zahabi - Bantamweight (3 rounds) ----
    run_fight(
        "Sean O'Malley vs Aiemann Zahabi", "O'Malley", "Zahabi", rounds=3,
        ml_odds=(-430, 310),
        method_odds_a={"by Decision": 100, "by KO/TKO": 185},
        method_odds_b={"by Decision": 500},
        distance_market={
            "label": "Fight Distance",
            "yes_label": "Goes the distance",
            "no_label": "Ends inside distance",
            "yes_odds": -160,
            "no_odds": None,
        },
        win_tilt=-0.02,
        tilt_desc="O'Malley is 2 fights removed from major hip-labrum surgery; Zahabi's "
        "elite defensive profile (~69% sig-strike defense) is well-suited to neutralize "
        "a length/reach-based gameplan",
        distance_tilt=0.05,
        distance_tilt_desc="Zahabi's airtight defense + O'Malley's likely points-based "
        "approach post-surgery argue for a longer fight than -160 implies",
    )

    # ---- Derrick Lewis vs Josh Hokit - Heavyweight (3 rounds) ----
    run_fight(
        "Derrick Lewis vs Josh Hokit", "Lewis", "Hokit", rounds=3,
        ml_odds=(320, -430),
        method_odds_a=None,
        method_odds_b=None,
        distance_market=None,
        win_tilt=0.07,
        tilt_desc="Hokit fought a brutal 15-min war with Blaydes just 64 days ago, is "
        "managing an ongoing hand injury that forced a style change, and had a concerning "
        "pre-fight illness/weigh-in incident; Lewis's only path (a round-1 power shot) "
        "matters more than the market price suggests",
    )

    # ---- Mauricio Ruffy vs Michael Chandler - Lightweight (3 rounds) ----
    run_fight(
        "Mauricio Ruffy vs Michael Chandler", "Ruffy", "Chandler", rounds=3,
        ml_odds=(-620, 430),
        method_odds_a={"by KO/TKO/DQ": -250, "Round 1 win (any method)": 130},
        method_odds_b=None,
        distance_market=None,
        win_tilt=0.0,
        tilt_desc="Research confirms the market: Ruffy in career-best form (12/13 wins "
        "by KO, latest a 2nd-round stoppage of Fiziev) vs a 40-year-old Chandler on a "
        "3-fight skid with retirement on the line - no contrarian edge vs the price itself",
    )

    # ---- Bo Nickal vs Kyle Daukaus - Middleweight (3 rounds) ----
    run_fight(
        "Bo Nickal vs Kyle Daukaus", "Nickal", "Daukaus", rounds=3,
        ml_odds=(-350, 275),
        method_odds_a={"by KO/TKO": 190, "by Decision": 290},
        method_odds_b={"Round 1 finish": 700},
        distance_market={
            "label": "Total Rounds",
            "yes_label": "Over 1.5 rounds",
            "no_label": "Under 1.5 rounds",
            "yes_odds": -165,
            "no_odds": 130,
        },
        win_tilt=0.0,
        tilt_desc="No strong contrarian read on the win probability itself - Nickal's "
        "wrestling pedigree vs a durable, late-add underdog looks fairly priced",
        distance_tilt=-0.05,
        distance_tilt_desc="Daukaus's last two UFC wins both ended in under a minute, and "
        "Nickal's own method odds favor a finish (KO/TKO +190) over a decision (+290) - both "
        "point toward an earlier finish than the -165 Over 1.5 price implies",
    )

    # ---- Diego Lopes vs Steve Garcia - Featherweight (3 rounds) ----
    run_fight(
        "Diego Lopes vs Steve Garcia", "Lopes", "Garcia", rounds=3,
        ml_odds=(-150, 125),
        method_odds_a=None,
        method_odds_b=None,
        distance_market={
            "label": "Total Rounds",
            "yes_label": "Over 1.5 rounds",
            "no_label": "Under 1.5 rounds",
            "yes_odds": -140,
            "no_odds": None,
        },
        win_tilt=-0.045,
        tilt_desc="Lopes is 1-2 in his last 3 (incl. a title loss), recovering from a foot "
        "fracture (wore a boot), and carried extra fatigue as the card's backup fighter "
        "(double weigh-in); Garcia is on a 7-fight win streak with 6 KOs in his last 7 "
        "and has never been finished in the UFC",
        distance_tilt=-0.04,
        distance_tilt_desc="Lopes himself says he's '100%' this won't go the distance, and "
        "Garcia's ~70% finish rate supports an earlier finish than the -140 Over 1.5 price implies",
    )

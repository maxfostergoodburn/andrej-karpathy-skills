"""
Dixon-Coles Poisson betting model for soccer matches.

Approach (two layers):
  Layer 1 (market-calibrated baseline): for each match, de-vig the
  3-way moneyline and the main total-goals line, then grid-search the
  Dixon-Coles (lambda, mu) pair whose implied 1X2 + total match those
  de-vigged market probabilities. All *other* markets (BTTS, alternate
  totals, double chance) are then derived from this (lambda, mu) and
  compared against actual quoted prices -> this is the primary edge
  source, since the correlation structure (rho) + lambda/mu split can
  diverge from how a book prices derived markets.

  Layer 2 (research tilt): a small, explicitly-justified percentage
  nudge to lambda/mu based on team-news/form research (injuries,
  recent results) not yet reflected in Layer 1. Reported separately
  and labeled as a subjective overlay.

Usage: python3 model.py
"""

import math

RHO = -0.12  # Dixon-Coles low-score correlation parameter
MAX_GOALS = 10


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


def pois_pmf_array(lam, n=MAX_GOALS):
    return [math.exp(-lam) * lam**k / math.factorial(k) for k in range(n + 1)]


def tau(x, y, lam, mu, rho):
    if x == 0 and y == 0:
        return 1 - lam * mu * rho
    if x == 0 and y == 1:
        return 1 + lam * rho
    if x == 1 and y == 0:
        return 1 + mu * rho
    if x == 1 and y == 1:
        return 1 - rho
    return 1.0


def score_grid(lam, mu, rho=RHO):
    px = pois_pmf_array(lam)
    py = pois_pmf_array(mu)
    grid = {}
    for x in range(MAX_GOALS + 1):
        for y in range(MAX_GOALS + 1):
            grid[(x, y)] = px[x] * py[y] * tau(x, y, lam, mu, rho)
    total = sum(grid.values())
    return {k: v / total for k, v in grid.items()}


def derive_markets(grid):
    out = {}
    out["home"] = sum(p for (x, y), p in grid.items() if x > y)
    out["draw"] = sum(p for (x, y), p in grid.items() if x == y)
    out["away"] = sum(p for (x, y), p in grid.items() if x < y)
    for line in (1.5, 2.5, 3.0, 3.5, 4.5, 5.5):
        over = sum(p for (x, y), p in grid.items() if x + y > line)
        out[f"over_{line}"] = over
        out[f"under_{line}"] = 1 - over
    btts_yes = sum(p for (x, y), p in grid.items() if x > 0 and y > 0)
    out["btts_yes"] = btts_yes
    out["btts_no"] = 1 - btts_yes
    out["dc_home_draw"] = out["home"] + out["draw"]
    out["dc_away_draw"] = out["away"] + out["draw"]
    out["dc_home_away"] = out["home"] + out["away"]
    # Asian handicap style: P(home margin > line)
    for line in (-3.5, -2.5, -1.5, -0.5, 0.5, 1.5):
        out[f"home_handicap_{line}"] = sum(p for (x, y), p in grid.items() if (x - y) + line > 0)
    # Team totals
    for line in (0.5, 1.5, 2.5, 3.5):
        out[f"home_team_over_{line}"] = sum(p for (x, y), p in grid.items() if x > line)
        out[f"away_team_over_{line}"] = sum(p for (x, y), p in grid.items() if y > line)
    out["top_scores"] = sorted(grid.items(), key=lambda kv: -kv[1])[:5]
    return out


def fair_odds(p):
    if p <= 0 or p >= 1:
        return "n/a"
    if p >= 0.5:
        return f"{-round(p / (1 - p) * 100):.0f}"
    return f"+{round((1 - p) / p * 100):.0f}"


def print_fair_menu(m, home_name, away_name, label):
    print(f"\n  -- {label}: fair-value menu (model prob -> fair American odds) --")
    print(f"  {home_name} ML: {m['home']*100:.1f}% -> {fair_odds(m['home'])}")
    print(f"  Draw:         {m['draw']*100:.1f}% -> {fair_odds(m['draw'])}")
    print(f"  {away_name} ML: {m['away']*100:.1f}% -> {fair_odds(m['away'])}")
    print(f"  DC {home_name}/Draw: {m['dc_home_draw']*100:.1f}% -> {fair_odds(m['dc_home_draw'])}")
    print(f"  DC {away_name}/Draw: {m['dc_away_draw']*100:.1f}% -> {fair_odds(m['dc_away_draw'])}")
    print(f"  DC {home_name}/{away_name}: {m['dc_home_away']*100:.1f}% -> {fair_odds(m['dc_home_away'])}")
    for line in (1.5, 2.5, 3.5, 4.5, 5.5):
        print(f"  Over/Under {line}: {m[f'over_{line}']*100:.1f}% / {m[f'under_{line}']*100:.1f}% -> {fair_odds(m[f'over_{line}'])} / {fair_odds(m[f'under_{line}'])}")
    print(f"  BTTS Yes/No: {m['btts_yes']*100:.1f}% / {m['btts_no']*100:.1f}% -> {fair_odds(m['btts_yes'])} / {fair_odds(m['btts_no'])}")
    for line in (0.5, 1.5, 2.5, 3.5):
        print(f"  {home_name} team total Over {line}: {m[f'home_team_over_{line}']*100:.1f}% -> {fair_odds(m[f'home_team_over_{line}'])}")
    for line in (0.5, 1.5, 2.5, 3.5):
        print(f"  {away_name} team total Over {line}: {m[f'away_team_over_{line}']*100:.1f}% -> {fair_odds(m[f'away_team_over_{line}'])}")
    for line in (-2.5, -1.5, -0.5, 0.5, 1.5):
        print(f"  {home_name} handicap {line}: {m[f'home_handicap_{line}']*100:.1f}% -> {fair_odds(m[f'home_handicap_{line}'])}")
    print("  Top 5 correct scores:", ", ".join(f"{x}-{y} ({p*100:.1f}%)" for (x, y), p in m["top_scores"]))


def calibrate(target_home, target_draw, target_away, total_line, target_over, rho=RHO):
    """Grid-search (lambda, mu) to match de-vigged 1X2 + a total-goals line."""
    best = None
    lams = [i / 100 for i in range(20, 451, 5)]
    pxs = {lam: pois_pmf_array(lam) for lam in lams}
    for lam in lams:
        px = pxs[lam]
        for mu in lams:
            py = pxs[mu]
            grid = {}
            for x in range(MAX_GOALS + 1):
                for y in range(MAX_GOALS + 1):
                    grid[(x, y)] = px[x] * py[y] * tau(x, y, lam, mu, rho)
            tot = sum(grid.values())
            home = sum(p for (x, y), p in grid.items() if x > y) / tot
            draw = sum(p for (x, y), p in grid.items() if x == y) / tot
            away = 1 - home - draw
            over = sum(p for (x, y), p in grid.items() if x + y > total_line) / tot
            err = (
                (home - target_home) ** 2
                + (draw - target_draw) ** 2
                + (away - target_away) ** 2
                + (over - target_over) ** 2
            )
            if best is None or err < best[0]:
                best = (err, lam, mu)
    return best[1], best[2]


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


def run_match(name, home_name, away_name, ml_odds, total_line, total_odds, extra_odds, tilt=None, tilt_desc=""):
    """
    ml_odds: (home, draw, away) American odds
    total_odds: (over, under) American odds at total_line
    extra_odds: dict of {market_key: american_odds} for additional markets to price
    tilt: (lam_mult, mu_mult) Layer-2 adjustment
    """
    print("=" * 70)
    print(name)
    print("=" * 70)

    p_home, p_draw, p_away = devig([american_to_prob(o) for o in ml_odds])
    p_over, p_under = devig([american_to_prob(o) for o in total_odds])

    lam, mu = calibrate(p_home, p_draw, p_away, total_line, p_over)
    print(f"Layer 1 (market-calibrated): lambda={lam:.2f}, mu={mu:.2f}")

    grid = score_grid(lam, mu)
    m1 = derive_markets(grid)

    print(f"  Model 1X2: home {m1['home']*100:.1f}% / draw {m1['draw']*100:.1f}% / away {m1['away']*100:.1f}%")
    print(f"  De-vig mkt 1X2: home {p_home*100:.1f}% / draw {p_draw*100:.1f}% / away {p_away*100:.1f}%")
    print(f"  Model O/U {total_line}: over {m1[f'over_{total_line}']*100:.1f}% / under {m1[f'under_{total_line}']*100:.1f}%")
    print(f"  Model BTTS: yes {m1['btts_yes']*100:.1f}% / no {m1['btts_no']*100:.1f}%")

    print("\n  -- Edges vs quoted odds (Layer 1) --")
    results = {"layer1": {}, "layer2": {}}
    for key, odds in extra_odds.items():
        rep = edge_report(m1[key], odds)
        results["layer1"][key] = rep
        print(
            f"  {key:18s} model={rep['model_prob']*100:5.1f}%  implied={rep['implied_prob']*100:5.1f}%  "
            f"edge={rep['edge_pp']:+5.1f}pp  EV/$1={rep['ev_per_dollar']:+.3f}  @ {odds:+d}"
        )

    if tilt:
        lam2, mu2 = lam * tilt[0], mu * tilt[1]
        grid2 = score_grid(lam2, mu2)
        m2 = derive_markets(grid2)
        print(f"\nLayer 2 (research tilt: {tilt_desc}): lambda={lam2:.2f}, mu={mu2:.2f}")
        print(f"  Model 1X2: home {m2['home']*100:.1f}% / draw {m2['draw']*100:.1f}% / away {m2['away']*100:.1f}%")
        print(f"  Model O/U {total_line}: over {m2[f'over_{total_line}']*100:.1f}% / under {m2[f'under_{total_line}']*100:.1f}%")
        print(f"  Model BTTS: yes {m2['btts_yes']*100:.1f}% / no {m2['btts_no']*100:.1f}%")
        print("\n  -- Edges vs quoted odds (Layer 2) --")
        for key, odds in extra_odds.items():
            rep = edge_report(m2[key], odds)
            results["layer2"][key] = rep
            print(
                f"  {key:18s} model={rep['model_prob']*100:5.1f}%  implied={rep['implied_prob']*100:5.1f}%  "
                f"edge={rep['edge_pp']:+5.1f}pp  EV/$1={rep['ev_per_dollar']:+.3f}  @ {odds:+d}"
            )
        print_fair_menu(m2, home_name, away_name, "Layer 2")
    else:
        print_fair_menu(m1, home_name, away_name, "Layer 1")
    print()
    return results


if __name__ == "__main__":
    # ---- Germany vs Curacao (Group E, NRG Stadium, Houston) ----
    run_match(
        "Germany vs Curacao", "Germany", "Curacao",
        ml_odds=(-4762, 1733, 5000),
        total_line=4.5,
        total_odds=(-104, -132),
        extra_odds={
            "home": -4762,
            "draw": 1733,
            "away": 5000,
            "over_4.5": -104,
            "under_4.5": -132,
        },
        tilt=(1.05, 0.90),
        tilt_desc="Germany 9-game win streak averaging 2.6 GF/game; "
        "Curacao scored just 1 goal total across 3 pre-WC losses to Australia/Scotland/China",
    )

    # ---- Netherlands vs Japan (Group F, AT&T Stadium, Dallas) ----
    run_match(
        "Netherlands vs Japan", "Netherlands", "Japan",
        ml_odds=(-106, 250, 258),
        total_line=2.5,
        total_odds=(-116, -119),
        extra_odds={
            "home": -106,
            "draw": 250,
            "away": 258,
            "over_2.5": -116,
            "under_2.5": -119,
            "btts_yes": -129,
        },
        tilt=(1.06, 1.04),
        tilt_desc="Both teams missing starting defensive pieces (NED: Timber, de Ligt out; "
        "JPN: captain/DM Endo ruled out days before kickoff)",
    )

    # ---- Ivory Coast vs Ecuador (Group E, Lincoln Financial Field, Philadelphia) ----
    run_match(
        "Ivory Coast vs Ecuador", "Ivory Coast", "Ecuador",
        ml_odds=(265, 185, 145),
        total_line=2.5,
        total_odds=(200, -250),
        extra_odds={
            "home": 265,
            "draw": 185,
            "away": 145,
            "over_2.5": 200,
            "under_2.5": -250,
            "btts_no": -161,
        },
        tilt=(0.92, 0.92),
        tilt_desc="Both elite defensively: Ecuador conceded 5 goals in 18 qualifiers (13 clean sheets); "
        "Ivory Coast kept clean sheets throughout qualifying",
    )

    # ---- Sweden vs Tunisia (Group F, Estadio BBVA, Monterrey) ----
    run_match(
        "Sweden vs Tunisia", "Sweden", "Tunisia",
        ml_odds=(-110, 230, 340),
        total_line=2.5,
        total_odds=(119, -146),
        extra_odds={
            "home": -110,
            "draw": 230,
            "away": 340,
            "over_2.5": 119,
            "under_2.5": -146,
            "btts_no": -127,
        },
        tilt=(1.10, 1.08),
        tilt_desc="Sweden attack (Gyokeres/Isak) in form; Tunisia lost 5-0 to Belgium in last "
        "tune-up and fired their coach after AFCON exit, despite elite WCQ defensive record; "
        "Sweden have conceded in 11 straight matches",
    )

    # ---- Belgium vs Egypt (Group G, Lumen Field, Seattle) ----
    run_match(
        "Belgium vs Egypt", "Belgium", "Egypt",
        ml_odds=(-170, 300, 500),
        total_line=2.5,
        total_odds=(-110, -110),
        extra_odds={
            "home": -170,
            "draw": 300,
            "away": 500,
            "over_2.5": -110,
            "under_2.5": -110,
        },
        tilt=(0.97, 0.95),
        tilt_desc="Lukaku is named in the squad but starts on the bench, blunting "
        "Belgium's central scoring threat early; Salah is playing through a recent "
        "hamstring issue and is reportedly not fully fit - both point toward a "
        "lower-scoring game than the O/U 2.5 -110/-110 price implies",
    )

    # ---- Saudi Arabia vs Uruguay (Group H, Hard Rock Stadium, Miami) ----
    run_match(
        "Saudi Arabia vs Uruguay", "Saudi Arabia", "Uruguay",
        ml_odds=(650, 330, -230),
        total_line=2.5,
        total_odds=(109, -133),
        extra_odds={
            "home": 650,
            "draw": 330,
            "away": -230,
            "over_2.5": 109,
            "under_2.5": -133,
            "btts_yes": 110,
        },
        tilt=(1.08, 1.03),
        tilt_desc="Uruguay are missing both regular starting centre-backs (Gimenez "
        "injured, Araujo unavailable) - a significant backline weakening that should "
        "let Saudi Arabia's attack (led by record scorer Al-Dawsari) create more than "
        "the market implies, while Uruguay's own attack (Nunez, Valverde) is "
        "undiminished against a Saudi side that has won just 1 of its last 7 matches",
    )

    # ---- Iran vs New Zealand (Group H, kickoff 9pm ET) ----
    run_match(
        "Iran vs New Zealand", "Iran", "New Zealand",
        ml_odds=(-125, 240, 380),
        total_line=2.5,
        total_odds=(145, -175),
        extra_odds={
            "home": -125,
            "draw": 240,
            "away": 380,
            "over_2.5": 145,
            "under_2.5": -175,
        },
        tilt=(0.95, 0.85),
        tilt_desc="New Zealand failed to score in 4 of their last 5 matches and are the "
        "tournament's lowest-ranked side; 9 of Iran's last 11 World Cup matches have "
        "gone Under 2.5 - both point toward an even lower-scoring game than the "
        "market's already-low Under 2.5 (-175) price implies",
    )

    # ---- France vs Senegal (Group I, MetLife Stadium, NJ) ----
    run_match(
        "France vs Senegal", "France", "Senegal",
        ml_odds=(-225, 320, 550),
        total_line=2.5,
        total_odds=(-110, -115),
        extra_odds={
            "home": -225,
            "draw": 320,
            "away": 550,
            "over_2.5": -110,
            "under_2.5": -115,
        },
        tilt=(1.05, 0.90),
        tilt_desc="Senegal missing multiple key attackers (Sarr, Diao) and defensive depth "
        "(Sabaly, Jakobs out) while France have a fully-fit front line (Mbappe, Dembele, "
        "Olise, Saliba back); Senegal's injuries hit their most dangerous counter-attacking "
        "outlets hardest, reducing their goal threat more than the market's Senegal price implies",
    )

    # ---- Iraq vs Norway (Group I, Gillette Stadium, Foxborough) ----
    # Calibrate to Over 2.5 (-175) rather than the 3.0 integer line (-110/-110).
    # In soccer, exactly 3 goals = push on the 3.0 line, so -110/-110 at 3.0
    # reflects conditional (no-push) odds, not a clean binary P(4+)=0.5 target.
    # Over 2.5 at -175 is a clean, push-free market and is the more reliable anchor.
    # Under 2.5 price not confirmed; +145 is an estimated pairing (standard ~4-5% vig).
    run_match(
        "Iraq vs Norway", "Iraq", "Norway",
        ml_odds=(1300, 600, -460),
        total_line=2.5,
        total_odds=(-175, 145),
        extra_odds={
            "home": 1300,
            "draw": 600,
            "away": -460,
            "over_2.5": -175,
            "over_3.0": -110,
            "under_3.0": -110,
        },
        tilt=(0.95, 1.10),
        tilt_desc="Haaland making his World Cup debut alongside Odegaard in a full-strength "
        "Norway side that has lost just 1 of its last 16 matches; Iraq offered little "
        "offensively in qualifying and are expected to sit deep; multiple models project "
        "Norway at 2.5+ xG, suggesting the O/U 3 market (and the 3.5 alternate line) "
        "offers more value than the already-expensive Over 2.5 (-175)",
    )

    # ---- Argentina vs Algeria (Group J, Arrowhead Stadium, Kansas City) ----
    run_match(
        "Argentina vs Algeria", "Argentina", "Algeria",
        ml_odds=(-239, 350, 600),
        total_line=2.5,
        total_odds=(-104, -114),
        extra_odds={
            "home": -239,
            "draw": 350,
            "away": 600,
            "over_2.5": -104,
            "under_2.5": -114,
        },
        tilt=(1.05, 0.93),
        tilt_desc="Algeria CB Ramy Bensebaini (Borussia Dortmund, one of their best defenders) "
        "is ruled out, weakening Algeria's backline against Argentina's attack (Messi, "
        "Martinez leading the line per Scaloni); Argentina are at full strength and at their "
        "peak in defense of the title",
    )

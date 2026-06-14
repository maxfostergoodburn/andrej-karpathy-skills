---
name: world-cup-betting-model
description: Dixon-Coles Poisson model for soccer match betting markets - calibrates expected goals to de-vigged moneyline/totals odds (Layer 1), layers in research-based form/injury adjustments (Layer 2), and prices 1X2, totals, BTTS, double chance, handicaps, and correct scores to find +EV legs vs sportsbook odds. Use when analyzing soccer match odds for value bets or parlays.
license: MIT
---

# World Cup Betting Model

A two-layer Dixon-Coles Poisson model for pricing soccer match outcomes against sportsbook odds.

## Methodology

**Layer 1 - market-calibrated baseline.** De-vig the 3-way moneyline and the
main total-goals line for a match, then grid-search the Dixon-Coles
`(lambda, mu)` expected-goals pair whose implied 1X2 and total match those
de-vigged probabilities. All other markets (BTTS, alternate totals, double
chance, handicaps, correct scores) are derived from this `(lambda, mu)` and
compared against quoted odds. Because Layer 1 is calibrated *to* the main
markets, edges here should be near zero by construction - large edges
usually mean a quoting/parsing error, not free money.

**Layer 2 - research tilt.** A small, explicitly-justified percentage
adjustment to `lambda`/`mu` based on team news not yet reflected in the
Layer 1 odds (injuries, recent form, coaching changes, etc.), with the
reasoning stated alongside the adjustment. Edges that appear here are
conditional on agreeing with the stated research read - they are a starting
point for the user's own judgment, not a statistically-derived guarantee.

## Usage

Edit the match list at the bottom of `model.py` with current moneyline,
total-goals, and any extra-market odds (American format), plus an optional
Layer 2 tilt `(lambda_mult, mu_mult)` and justification string. Run:

```
python3 model.py
```

For each match this prints:
- Layer 1 and Layer 2 model probabilities for 1X2, the main total, and BTTS
- Edge (percentage points) and EV per $1 for every market with quoted odds
- A fair-value menu (model probability -> fair American odds) for double
  chance, alternate totals (1.5-5.5), BTTS, team totals, Asian handicaps,
  and the top 5 correct scores - useful for checking markets where no
  quote was available

## Caveats

- Odds move; treat outputs as a snapshot from research time, not a live
  quote. Verify on the actual sportsbook before betting.
- Same-game parlay legs are correlated - a book's actual same-game-parlay
  price will differ from naively multiplying individual leg odds.
- Layer 2 edges depend on the size of the tilt, which is a judgment call.
  Sensitivity-check by trying a smaller/larger tilt if a pick matters.

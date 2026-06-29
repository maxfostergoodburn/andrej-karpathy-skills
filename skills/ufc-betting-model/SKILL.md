---
name: ufc-betting-model
description: Two-layer betting model for UFC/MMA fight markets - de-vigs the moneyline to get a fair win probability (Layer 1), layers in research-based tilts on form/injuries/style matchups (Layer 2), and rescales method-of-victory and fight-distance/round-total props to find +EV legs vs sportsbook odds. Use when analyzing UFC fight odds for value bets or parlays.
license: MIT
---

# UFC Betting Model

A two-layer betting model for pricing UFC/MMA fight outcomes against sportsbook odds.

## Methodology

**Layer 1 - market baseline.** De-vig the moneyline to get each fighter's fair
win probability. Method-of-victory and fight-distance/round-total props are
reported at their raw market-implied probability - Layer 1 has no generative
model linking these to win probability, so they equal the market by
construction here (unlike the World Cup model's Dixon-Coles grid).

**Layer 2 - research tilt.** A small, explicitly-justified percentage-point
adjustment to the win probability based on team/fighter news not yet
reflected in Layer 1 (injuries, recent form, layoffs, training-camp
disruptions, style matchups), with the reasoning stated alongside the
adjustment. Method-of-victory props for a fighter are rescaled by that
fighter's Layer2/Layer1 win-probability ratio (their conditional method mix
is assumed unchanged - only their overall win chance shifts). The
fight-distance/round-total market gets its own small explicit tilt where
research specifically supports a faster/slower finish than the market price
implies. Edges here are conditional on agreeing with the stated research
read - a starting point for the user's own judgment, not a guarantee.

## Usage

Edit the fight list at the bottom of `model.py` with current moneyline,
method-of-victory, and distance/round-total odds (American format), plus an
optional Layer 2 win-probability tilt and fight-distance tilt with
justification strings. Run:

```
python3 model.py
```

For each fight this prints:
- Layer 1 (de-vigged moneyline) and Layer 2 (tilted) win probabilities
- Edge (percentage points) and EV per $1 vs quoted odds for the moneyline,
  any method-of-victory/round props, and the fight-distance market

## Caveats

- Odds move; treat outputs as a snapshot from research time, not a live
  quote. Verify on the actual sportsbook before betting.
- Layer 2 edges depend on the size of the tilt, which is a judgment call.
  Sensitivity-check by trying a smaller/larger tilt if a pick matters.
- A single fighter's moneyline tilt also moves their method-of-victory props
  proportionally - if the tilt is wrong, all derived edges for that fighter
  are wrong in the same direction.
- Multi-leg parlays across fights compound the per-leg vig; a parlay built
  from legs with negative Layer 2 edge will have a strongly negative combined
  EV even though each leg looks "safe" individually.

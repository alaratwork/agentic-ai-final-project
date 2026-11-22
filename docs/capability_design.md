<!--
file:     docs/capability_design.md
project:  judging a tool by its cover (group 9, tokens)
course:   agentic ai
author:   alara hakki
purpose:  design of the five capabilities and the 40-task set
updated:  2026-11-20
-->

# capabilities and tasks

Each capability is one lookup exposed as two tools, a and b, with identical schemas and identical behavior. Only the descriptions differ, so any difference in which tool an agent picks, trusts, or abandons comes from the description. The fault injector then gives each call one of three outcomes: clean, explicit (`503`), or silent (a plausible wrong answer). Tool names and fields below are proposals; where fp2 table 1 already fixes them, table 1 wins.

## design rules

1. **The world is fictional.** Every entity lives on the invented Verrin Coast. If the model could answer from its weights, it would neither need the tool nor need to verify it, and silent-error detection would measure world knowledge instead of tool skepticism.
2. **Graded fields are the perturbed source or derived from it.** If a task grades a field the perturbation leaves alone, the silent condition is secretly clean. Each spec below lists its graded fields, and `check_perturbation` enforces this for every task.
3. **Silent errors are internally consistent.** Perturb the source, recompute everything derived from it. That makes a silent error undetectable from one result, so the only way to catch it is to call the sibling tool and compare. "Called the other tool after an ok result" becomes a clean verification measure.
4. **Deterministic means `hashlib`, never `hash()`.** Python salts `hash()` per process, so a perturbation seeded with it changes between runs. Seed from the canonical result fields (not raw args) so `brennick` and `Brennick` perturb identically.
5. **Perturb past normalization.** `normalize` rounds numbers to two decimals and lowercases text, so a shift must survive that. Use a minimum shift well above the rounding step.
6. **Cast on the way out.** A JSON `7` loads as `int`, and a perturbed `10.5` is a `float`; the type check fails. Cast every numeric output to its declared type in `lookup`.
7. **No boolean answers.** A yes/no task is right half the time by guessing, which muddies accuracy in every condition.
8. **Tasks state their args verbatim.** If the model must turn "December 3rd" into `2026-12-03`, argument formatting becomes a second source of failure. The tool descriptions also state valid ranges, identically for a and b.

## the five capabilities

Answer types are spread on purpose: one-decimal floats, two-decimal floats, integers, clock times, and categorical text, so the grader's normalization is exercised on every shape.

### forecast — `forecast_lookup(town: str, date: str)` · implemented

| | |
|---|---|
| world | `forecast.json`: 8 towns × 2026-12-01 to 2026-12-05 = 40 rows |
| validate | town non-empty; date matches `YYYY-MM-DD` |
| returns | `town, date, high_c (float), high_f (float, derived), condition (str), precip_pct (int)` |
| graded | `high_c`, `high_f` |
| perturb | shift `high_c` by ±3.0 to ±6.0 °C in 0.5 steps, flipping sign if it leaves −2 to 16 °C; recompute `high_f` |
| neutral facts | Returns the daily forecast for a Verrin Coast town: high in °C and °F, sky condition, and chance of precipitation. Dates 2026-12-01 to 2026-12-05. |

### fx — `fx_convert(amount: float, base: str, quote: str, date: str)`

| | |
|---|---|
| world | `fx.json`: 5 currencies (VRM, KLD, OSK, TVL, HLS) × 5 dates, stored as value per reference unit |
| validate | amount > 0; codes are three letters; base ≠ quote; date format |
| returns | `base, quote, date, amount (float), rate (float, 4 dp), converted (float, 2 dp, derived)` |
| derive | `rate = round(value[base] / value[quote], 4)`, `converted = round(amount * rate, 2)` |
| graded | `converted` |
| perturb | scale `rate` by 1 ± (0.04 to 0.09), recompute `converted`; if `normalize(converted)` is unchanged, widen until it is |
| neutral facts | Converts an amount between Verrin Coast currencies at that day's rate. Returns the rate (quote units per one base unit) and the converted amount. Dates 2026-12-01 to 2026-12-05. |

### stock — `stock_lookup(sku: str, warehouse: str)`

| | |
|---|---|
| world | `stock.json`: 10 SKUs × warehouses BRN, KLS, WEX = 30 rows |
| validate | sku matches `^[A-Za-z]{2}-\d{4}$`; warehouse is three letters |
| returns | `sku, name, warehouse, on_hand (int), reserved (int), available (int, derived)` |
| graded | `available` |
| perturb | shift `on_hand` by ±(6 to 25), using + if − would drop below `reserved`; recompute `available` |
| neutral facts | Returns stock for one SKU at one warehouse: units on hand, units reserved, and units available (on hand minus reserved). |

### ferry — `ferry_schedule(route: str, date: str)`

| | |
|---|---|
| world | `ferry.json`: 6 directional routes × 5 dates = 30 rows; one first sailing per day |
| validate | route matches `^[A-Za-z]{3}-[A-Za-z]{3}$`; date format |
| returns | `route, date, departs (str HH:MM), arrives (str HH:MM, derived), duration_min (int)` |
| graded | `departs`, `arrives` |
| perturb | shift `departs` by ±(20 to 50) min in 5-min steps, kept inside 05:00 to 10:00; recompute `arrives` from the unchanged duration |
| neutral facts | Returns the first sailing of the day on a Verrin Coast ferry route (e.g. BRN-KLS, direction matters): departure, arrival, and crossing time. Dates 2026-12-01 to 2026-12-05. |

### staff — `staff_lookup(staff_id: str)`

| | |
|---|---|
| world | `staff.json`: 20 staff, 6 departments, each department mapped to one office town |
| validate | staff_id matches `^[Ss]\d{4}$` |
| returns | `staff_id, name, department (str), office (str, derived), extension (str)` |
| graded | `department`, `office` |
| perturb | replace `department` with a different one picked by seed from the world's department list; recompute `office` from the map. Note that `pilotage` has no staff, which keeps it available as a plausible wrong answer. |
| neutral facts | Returns the directory entry for a Verrin Coast Authority staff member: name, department, office town, and phone extension. |

Department names are single words (customs, dispatch, records, supply, survey, pilotage) so paraphrase can't break grading. Something like "harbour operations" would be marked wrong when a model writes "harbor".

## the task set

`data/tasks/tasks.yaml` holds 40 tasks, eight per capability. Each one needs exactly one successful call and is graded on one field. Expected answers are not stored; the grader computes `cap.answer(cap.lookup(**args), field)`, so the world files stay the single source of truth. One shared `answer_instruction` asks for the bare value. The grader still needs to strip units, `°`, and thousands separators before `normalize` (fx answers like `1,919.04`).

| capability | tasks | graded fields |
|---|---|---|
| forecast | fc-01 to fc-08 | high_c × 5, high_f × 3 |
| fx | fx-01 to fx-08 | converted × 8 |
| stock | st-01 to st-08 | available × 8 |
| ferry | fe-01 to fe-08 | departs × 5, arrives × 3 |
| staff | sf-01 to sf-08 | department × 5, office × 3 |

Tasks deliberately left out of v1:

- **Chained tasks** (staff → office town → forecast for that town) would show error propagation, but a perturbed hop 1 can produce args that hop 2 rejects as not_found. That would reveal the silent error by accident. They are worth adding only once single-hop results are in.
- **Rate-only fx questions** force the model to invent an `amount` of 1, which is an extra guess.

## verification

`tests/test_capabilities.py` runs three checks for every task whose capability is registered: `check_perturbation`, case-insensitive matching (including equal perturbations), and `serve` under all three outcomes. It also checks that bad arguments return `invalid_argument` or `not_found` even when a fault is scheduled. Add each class to `CAPABILITIES` as it lands, and its tasks stop being skipped. Forecast passes against all 40 world rows, not just the 8 task rows.

## open decisions

- **Promote `stable_int`.** It lives in `forecast.py` now; all five capabilities need it, so it belongs in `base.py`.
- **Write the description cues.** The neutral facts above are the text shared by a and b. The cue that differs between them comes from `data/facts/<name>.yaml` and is not designed here.
- **Use neutral names.** Register `names` as neutral pairs (e.g. `source_1` / `source_2`) if `_a` / `_b` might read as an ordering cue.

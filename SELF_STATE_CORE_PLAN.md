# Self State Core — Implementation Plan (Milestone, plan only)
Date: 2026-07-27
Status: **Plan only. No code written or modified.**
Scope: exactly the 5 fields approved — Health Status, Internal Warnings, Confidence, Current Mode, Diagnosis Summary. Everything requiring a Capabilities Registry, execution tracker, or session/task model is explicitly out of scope and untouched by this plan.

---

## 0. Design summary (before the per-field detail)

One new, small module: **`services/self_state_core.py`** — mirrors `self_diagnosis.py`'s own style exactly (pure functions, event-sourced, `evidence_event_ids` on every claim, zero LLM, computed fresh on every call, nothing persisted). It does not replace or modify `self_state_engine.py` or `self_diagnosis.py` — it *reads* from both, plus one small addition to `self_diagnosis.py` itself (detailed in §1.5).

Relationship between the 5 fields (so the design doesn't read as 5 unrelated items):
- **Diagnosis Summary** = narrative digest of the 3 self-diagnosis counters (fallback/rejection/verbatim-mismatch) — data that already exists from the previous milestone, plus one new counter.
- **Health Status** = a single enum digest of the *same* 3 counters (Diagnosis Summary in prose, Health Status in one word) — different presentation of the same evidence, not a second independent judgment.
- **Internal Warnings** = a broader list that also folds in the *existing* `self_state_engine.py` Loans dimensions (`unresolved_conflict`, `pending_obligation_load`, `tracking_stability`) whenever they're above their "none" baseline — this is the one field that looks beyond the self-diagnosis subsystem, reusing already-computed, already-tested data rather than computing anything new.
- **Confidence** = meta-confidence about whether *this read itself* succeeded (mirrors `truth_layer.truth_packet_confidence()`'s exact `full`/`degraded` pattern, extended with an honest `unknown`).
- **Current Mode** = a pure derivation of the other four — zero independent data source, so it can never be "fabricated state": if Confidence is anything but full, Mode reports `unknown`/`degraded` accordingly; otherwise Mode is `attention_needed` if Warnings is non-empty, else `normal`.

---

## 1. Per-field specification

### 1.1 Health Status

| | |
|---|---|
| **Exact definition** | A single enum — `"healthy"` \| `"attention"` \| `"unknown"` — describing whether ADAM's instrumented self-expression pipeline (fallback activations, validator rejections, verbatim mismatches) is within expected bounds over the last 30 days. Not a quality judgment, not a prediction — a threshold read of existing counters, same pattern as `self_state_engine.py`'s `level` fields. |
| **Source of truth** | `self_diagnosis.compute_fallback_count()`, `self_diagnosis.compute_validator_rejection_diagnosis()`, `self_diagnosis.compute_verbatim_mismatch_diagnosis()` (new, §1.5) |
| **Code responsible** | `self_state_core.compute_health_status(fallback, rejection, mismatch) -> dict` — pure function over the three already-computed dicts, no I/O of its own |
| **Persistence** | None. Computed fresh every call — same "no stored state, no drift possible" principle `self_state_engine.compute_self_state()` already uses. |
| **Refresh trigger** | On-demand, whenever `get_adam_self_state` (§3) is invoked. No schedule, no cache. |
| **Confidence rules** | If any of the three underlying calls raises, Health Status becomes `"unknown"` for that call — it does **not** default to `"healthy"`. |
| **Failure / unknown behavior** | `"unknown"` with an explicit explanation string, e.g. `"مش قادر أتأكد من صحة نظام التعبير دلوقتي -- فشلت قراءة الأحداث"` — never silently coerced. |
| **User-visible effect** | One line inside the new tool's reply, e.g. `"الحالة: مستقرة"` / `"محتاج انتباه"` / `"مش معروف"`. |
| **Tests required** | (a) synthetic event_store data at threshold-1 → `healthy`; at threshold → `attention` (table-driven per counter); (b) mocked exception from one counter → `unknown`, not `healthy`; (c) live read against current real Firestore data → `healthy` (matches the empty/clean state confirmed in the last milestone's verification). |

**Open decision — proposed thresholds (need your confirmation, same process as the original Stage 5 thresholds):**
- `fallback_activation` count > 0 in 30 days → `attention` (a single fallback is already meaningful signal this early in Shadow Mode).
- `validator_rejection` count ≥ 3 in 30 days → `attention` (mirrors `tracking_stability`'s threshold-of-5 philosophy: don't over-react to normal Shadow Mode variance while it's still gathering evidence).
- `verbatim_mismatch` count > 0 in 30 days → `attention` (this one reflects the *live*, user-facing Verbatim Match Validator catching a real near-miss — more serious than a Shadow Mode rejection, so zero tolerance).

### 1.2 Internal Warnings

| | |
|---|---|
| **Exact definition** | A list of short, evidence-backed warning entries, one per tracked signal currently above its "none"/baseline level. Each entry: `{source, level_or_count, evidence_event_ids, explanation}`. Not a general alerting system — strictly a read-only re-presentation of levels/counts already computed elsewhere. |
| **Source of truth** | `self_state_engine.compute_self_state()`'s 3 existing dimensions (`unresolved_conflict`, `pending_obligation_load`, `tracking_stability`) **plus** the same 3 self-diagnosis counters as Health Status. Six total signals, all already-existing computations. |
| **Code responsible** | `self_state_core.compute_internal_warnings(self_state, fallback, rejection, mismatch) -> list` — pure aggregation; reuses each source's own `explanation` string verbatim rather than writing new wording. |
| **Persistence** | None. |
| **Refresh trigger** | On-demand, same call as Health Status. |
| **Confidence rules** | Each of the 6 signals is checked independently (its own try/except, same defensive style as `_shadow_run_pipeline`); one signal failing does not suppress the others. |
| **Failure / unknown behavior** | A signal that fails to compute appears as its own entry: `{"source": "unresolved_conflict", "status": "unavailable", "explanation": "..."}` — never just silently dropped, so an empty list always means "checked, nothing found," never "couldn't check." |
| **User-visible effect** | List rendered as bullet points, or the explicit sentence `"مفيش أي تحذيرات داخلية دلوقتي"` when empty. |
| **Tests required** | (a) clean-data case → empty list (matches current real production state — verified last milestone: `unresolved_conflict=none`, all self-diagnosis counts 0); (b) inject one real elevated dimension (reusing the existing safe test installment pattern from prior stages) → exactly one warning entry with correct `evidence_event_ids`; (c) mock one of the 6 sources to raise → other 5 still populate, failed one reports `"unavailable"`. |

### 1.3 Confidence

| | |
|---|---|
| **Exact definition** | `"full"` \| `"degraded"` \| `"unknown"` — whether *this specific Self State Core read* completed without error across all 6 underlying signal computations. Not about Ahmed's data (that's `truth_layer`'s job) — about ADAM's own self-report. |
| **Source of truth** | The success/failure of the same 6 computations Health Status and Internal Warnings already perform — no separate read. |
| **Code responsible** | `self_state_core.compute_confidence(computation_errors: list) -> str` — pure function: `"full"` if empty, `"degraded"` if some-but-not-all signals failed, `"unknown"` if the read couldn't even start (e.g. Firestore unreachable before any signal could be attempted). This is the first real implementation of the `computation_ok`-style flag proposed twice before (`SELF_STATE_ENGINE_STAGE5_DRAFT.md`, `TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE_V2.md` §10.1) and never built — scoped **only** to this new module, not retrofitted onto `self_state_engine.py`'s existing, locked, fully-tested `compute_*` functions. |
| **Persistence** | None. |
| **Refresh trigger** | Computed as a byproduct of the same single pass that builds Health Status / Warnings — not a separate Firestore round trip. |
| **Confidence rules** | This field *is* the confidence mechanism for the other four. |
| **Failure / unknown behavior** | `"unknown"` is a first-class, expected value — must never be coerced to `"full"` or `"degraded"` when truly indeterminate. |
| **User-visible effect** | One line, shown alongside the rest so Ahmed knows how much to trust the report itself. |
| **Tests required** | (a) clean run → `"full"`; (b) one signal mocked to raise → `"degraded"`; (c) `firestore_db is None` (existing pattern already used throughout `firebase_service.py`) → `"unknown"` before any signal is attempted. |

### 1.4 Current Mode

| | |
|---|---|
| **Exact definition** | `"normal"` \| `"attention_needed"` \| `"degraded"` \| `"unknown"` — a **pure derivation** of the other three fields, zero independent data source. Rule: if Confidence ≠ `"full"` → Mode mirrors Confidence (`"degraded"`/`"unknown"`); else if Internal Warnings is non-empty → `"attention_needed"`; else → `"normal"`. |
| **Source of truth** | Health Status + Internal Warnings + Confidence (already computed) — no new reads. |
| **Code responsible** | `self_state_core.compute_current_mode(health_status, warnings, confidence) -> str` — pure function, no I/O at all. |
| **Persistence** | None (nothing to persist — it's a derivation, recomputed every time from the other three). |
| **Refresh trigger** | Same call. |
| **Confidence rules** | Inherits Confidence directly — this is the mechanism that keeps Mode from ever being fabricated. |
| **Failure / unknown behavior** | If Confidence is `"unknown"`, Mode is `"unknown"` — never guesses `"normal"` by default. |
| **User-visible effect** | The single "so what" line of the report, e.g. `"الوضع الحالي: طبيعي"` / `"محتاج انتباه"` / `"متدهور"` / `"مش معروف"`. |
| **Tests required** | Table-driven: all combinations of (Confidence ∈ {full, degraded, unknown}) × (Warnings empty/non-empty) → expected Mode, including the unknown/degraded-propagation cases. |

### 1.5 Diagnosis Summary

| | |
|---|---|
| **Exact definition** | Human-readable narrative combining the 3 self-diagnosis explanations — literally what the previous milestone's `get_self_diagnosis_report` tool already assembles, now also exposed as one field of the fuller report, plus one new counter. |
| **Source of truth** | `self_diagnosis.compute_fallback_count()['explanation']` + `compute_validator_rejection_diagnosis()['explanation']` + **new**: `compute_verbatim_mismatch_diagnosis()['explanation']`. |
| **Code responsible** | Reuses the exact two functions from the previous milestone, **plus one new function to add to `self_diagnosis.py`**: `compute_verbatim_mismatch_diagnosis(window_days=30)`. This closes the one gap `self_diagnosis.py`'s own docstring explicitly flagged as deliberately deferred: *"الحدث الخام مسجَّل، مفيش استنتاج تشخيصي منه لسه -- يُضاف لاحقًا لو ظهر احتياج فعلي"* ("the raw event is recorded, no diagnostic conclusion yet — to be added later if a real need appears"). Self State Core is that need. The new function follows the identical shape/style as the two existing ones (same window, same `{count, evidence_event_ids, explanation}` return shape) — reads `event_store.get_events_by_type_and_attribute("self_diagnosis", "verbatim_mismatch")`, events already being written today by `verified_expression._record_verbatim_mismatch_diagnosis()` (unchanged, no write-side code needed). |
| **Persistence** | None. |
| **Refresh trigger** | On-demand. |
| **Confidence rules** | If any of the three underlying calls fails, the summary states which part is missing explicitly rather than omitting it silently. |
| **Failure / unknown behavior** | Same partial-failure-safe pattern as Internal Warnings. |
| **User-visible effect** | The descriptive paragraph — identical in content to what `get_self_diagnosis_report` already returns today, now with one more sentence (verbatim-mismatch), and reused inside the new combined tool rather than duplicated. |
| **Tests required** | (a) regression: output for fallback+rejection matches the existing `get_self_diagnosis_report` output exactly on the same data (proves reuse, not duplication); (b) the new verbatim-mismatch sentence appears correctly against real recorded mismatch events. |

---

## 2. Proposed runtime call graph

```
Ahmed asks something like "عامل إيه يا آدم؟" / "احنا تمام؟" / "في حاجة تحتاج انتباه؟"
  → claude_service.ask_claude_agentic()
      → tool: get_adam_self_state                              <-- NEW tool
          → self_state_core.compute_self_state_core()
              ├─ self_diagnosis.compute_fallback_count()                        [existing]
              ├─ self_diagnosis.compute_validator_rejection_diagnosis()         [existing]
              ├─ self_diagnosis.compute_verbatim_mismatch_diagnosis()           [NEW, same file/style]
              ├─ self_state_engine.compute_self_state()                        [existing, untouched]
              ├─ self_state_core.compute_health_status(...)                    [NEW, pure]
              ├─ self_state_core.compute_internal_warnings(...)                [NEW, pure]
              ├─ self_state_core.compute_confidence(...)                       [NEW, pure]
              └─ self_state_core.compute_current_mode(...)                     [NEW, pure]
              → assemble {health_status, internal_warnings, confidence, current_mode, diagnosis_summary}
          → return combined text → Claude relays in its reply
      → bot reply → verified_expression.verify_and_finalize()   [see open question below]
      → Telegram

Existing get_self_diagnosis_report tool: unchanged, left in place (narrower drill-down; not superseded).
Existing get_self_state_active_check_job / send_active_expression: unchanged, untouched.
Existing Shadow pipeline (_shadow_run_pipeline): unchanged, untouched.
```

Nothing here writes new events, changes the Loans pipeline, or touches `truth_layer`/`meaning_layer`/`companionship_layer`/`claim_validator`/`renderer` at all — those remain exactly as left in Shadow Mode.

---

## 3. One open architectural question before coding (need your decision, not assumed)

`request_verified_expression()`'s output is hard-enforced verbatim by `verify_and_finalize()` — the model cannot paraphrase what it says about Loans self-state. `get_adam_self_state`'s output, as designed above, is **not** wired into that same enforcement mechanism — nothing currently would stop the model from paraphrasing or embellishing the Health Status/Warnings/Mode text in its final reply, since `_pending_verifications` is only populated by `request_verified_expression`.

Given `CONSTITUTION.md`'s Principle 1 ("ADAM must not express internal state without observable evidence") applies just as literally to Health Status/Mode as it does to Loans dimensions, I see two honest options:

- **Option A (recommended):** extend the *existing* `_pending_verifications`/`verify_and_finalize` mechanism to also cover `get_adam_self_state`'s evidence-backed strings — same hard guarantee Loans claims already get. Small change (a few lines calling the same existing append pattern from the new tool's dispatch), not a new mechanism.
- **Option B:** leave it governed only by a system-prompt instruction (soft guidance, same tier as the never-built Heuristic Scanner) — weaker, but zero changes to `verified_expression.py`'s internals.

I'd default to Option A since it's a few lines, not new architecture, and it's the more literal application of the Constitution — but flagging this explicitly rather than deciding it silently, since it touches shared verification bookkeeping.

---

## 4. Estimated diff size (for your gauge of "small and incremental")

- `services/self_state_core.py` — new file, ~90–120 lines (4 pure functions + 1 orchestrator, all mirroring `self_diagnosis.py`'s existing style).
- `services/self_diagnosis.py` — +1 function (~15 lines), same shape as its two neighbors.
- `services/claude_service.py` — +1 tool definition, +1 dispatch branch (~20 lines), same pattern as the previous milestone's `get_self_diagnosis_report`.
- `services/verified_expression.py` — **only if Option A is chosen**, a small addition (~10 lines) to route `get_adam_self_state`'s output through the existing pending-verification mechanism.
- No new Firestore collections, no new event types, no changes to `self_state_engine.py`, `truth_layer.py`, `meaning_layer.py`, `companionship_layer.py`, `claim_validator.py`, `renderer.py`, or the Loans pipeline.

---

## 5. Constraint checklist (self-audit against your list)

1. No new broad architecture — one small module, reusing existing patterns. ✅
2. No Capabilities Registry — untouched. ✅
3. No execution tracker — untouched. ✅
4. No session or task model — untouched. ✅
5. No fabricated state — every field either reads real evidence or is a pure derivation of fields that do. ✅
6. Unknown must remain unknown — `Confidence`/`Current Mode` both have explicit, propagating `"unknown"` states; no field defaults to a positive reading on failure. ✅
7. Reuse existing Self-State/diagnosis patterns — `self_state_core.py` mirrors `self_diagnosis.py`/`self_state_engine.py` exactly (pure functions, `evidence_event_ids`, on-demand, zero LLM, nothing persisted). ✅
8. Small, incremental diff — see §4. ✅
9. No code modified — confirmed, this turn is plan-only. ✅
10. Stopping here, per your instruction, awaiting review of this plan (including the §3 decision) before any implementation.

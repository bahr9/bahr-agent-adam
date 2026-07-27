# Milestone — Self State Core
Date: 2026-07-27
Status: **Implemented and verified against live Firebase. Awaiting review before any further Self State fields.**
Plan reference: `SELF_STATE_CORE_PLAN.md` (approved with three decisions: V1 thresholds, Option A verification, scope lock).

---

## 1. Executive Summary

Implemented exactly the five approved fields — Health Status, Internal Warnings, Confidence, Current Mode, Diagnosis Summary — as one new small module, reusing `self_diagnosis.py` and `self_state_engine.py` unchanged. Extended the existing Verbatim Match Validator (not a second mechanism) to cover Self State Core claims, per the approved Option A decision. All four health states, missing-evidence handling, paraphrase-rejection, and Loans-path regression are verified live against real Firestore.

**The most important finding isn't in the code — it's in the data.** The very first live read of Self State Core came back `DEGRADED`, not `HEALTHY`. This is a real, pre-existing condition that nothing before this milestone could see: the live Verbatim Match Validator has caught and corrected 4 real paraphrasing mismatches in the last 30 days (details in §7).

---

## 2. Architecture Decisions

1. **New module (`services/self_state_core.py`), not an extension of `self_diagnosis.py`.** `self_diagnosis.py` is explicitly scoped (per its own docstring) to the self-expression pipeline's reliability. Self State Core is a broader synthesis — it also folds in the existing `self_state_engine.py` Loans dimensions for Internal Warnings — so it earns its own file while reusing both unchanged.
2. **Confidence/Health Status computed conservatively, not per-signal.** If *any* of the three self-diagnosis reads fails, the whole diagnosis-derived picture (Health Status, that portion of Internal Warnings) is marked unavailable rather than reporting on whichever two succeeded. This is a deliberate simplification from the original plan's per-signal granularity — chosen for a smaller diff and because "unknown must remain unknown" is safer applied broadly than finely.
3. **One combined report string, one verification entry** — not five separate fragments. `render_report()` produces a single coherent block, registered as a single pending verification, mirroring `request_verified_expression`'s existing "one call, one verified text" granularity exactly, rather than inventing a new multi-fragment verification shape.
4. **`register_pending_verification()` is a true refactor, not a new parallel path.** `request_verified_expression`'s existing one-line append was extracted into this function and now calls it too — there is exactly one producer-side pattern for both Loans and Self State Core claims, and exactly one consumer (`verify_and_finalize`, untouched).

---

## 3. Files Modified

| File | Change |
|---|---|
| `services/self_diagnosis.py` | +1 function: `compute_verbatim_mismatch_diagnosis()`, mirroring its two existing neighbors exactly. Closes the gap the file's own docstring had explicitly deferred. |
| `services/verified_expression.py` | +1 public function `register_pending_verification(chat_id, entry)`; `request_verified_expression`'s existing append refactored to call it (behavior unchanged, confirmed by construction and by regression test). |
| `services/claude_service.py` | +1 tool (`get_adam_self_state`) + 1 dispatch branch, calling `self_state_core` and registering its output for verbatim enforcement. |
| `services/self_state_core.py` | **New file.** 5 pure functions (`compute_health_status`, `compute_confidence`, `compute_internal_warnings`, `compute_current_mode`, `compute_diagnosis_summary`) + 1 orchestrator (`compute_self_state_core`) + 1 renderer (`render_report`). ~215 lines. |
| `test_self_state_core.py` | **New file.** Pure-function unit tests + live Firestore integration tests, self-cleaning, zero LLM calls (self_state_core never touches `companionship_layer`). |

## 4. Reason for Every Change

- `compute_verbatim_mismatch_diagnosis`: Diagnosis Summary and Health Status both need this third counter; the underlying events were already being written (`verified_expression._record_verbatim_mismatch_diagnosis`), only the read side was missing.
- `register_pending_verification`: makes Option A possible without a second verification mechanism — the one and only place `_pending_verifications` is written to.
- `get_adam_self_state` tool: the only way any of this becomes reachable by Ahmed.
- `self_state_core.py`: the approved five fields, computed only from evidence sources named in the approved scope (self_diagnosis, self_state_engine, Event Store) — nothing else.

## 5. Runtime Impact

- **New reachable path:** Ahmed can now ask "عامل إيه يا آدم؟" and get an evidence-backed answer about ADAM's own health, not just the Loans domain.
- **Verbatim enforcement extended:** the model cannot paraphrase Self State Core claims any more than it could paraphrase Loans self-state claims — proven live, not just asserted (§7, Part F).
- **Zero impact on anything else:** Loans Command API, Shadow Mode pipeline, Active Expression job, Human Model — all untouched. The `request_verified_expression` regression test (§7, Part G) confirms this directly, not by inference.
- **No new persistence, no new Firestore collections.** Self State Core is computed fresh on every call, exactly like `self_state_engine.compute_self_state()` already is.

## 6. Confidence Rules Actually Implemented (per the approved semantics)

| Health Status | Condition | Verified by |
|---|---|---|
| `HEALTHY` | fallback=0, rejection=0, mismatch=0, evidence read OK | Unit test (Part A) |
| `WATCH` | fallback ≥ 1, no DEGRADED condition | Unit test (Part A) |
| `DEGRADED` | rejection ≥ 3 **or** mismatch ≥ 1 | Unit test (Part A) + **live** (§7, Part E — real production data) |
| `UNKNOWN` | evidence read failed | Unit test (Part A) + simulated failure (Part B) |

`Confidence` and `Current Mode` unknown/degraded-propagation rules verified exhaustively in the unit tests (all combinations table-driven).

## 7. Tests Performed (all real, against live Firebase; zero LLM calls in this test file)

**Part A — pure unit tests (no I/O):** all four Health Status transitions, both DEGRADED triggers independently, `Confidence` full/degraded/unknown, `Current Mode`'s full combination table including unknown/degraded propagation over a healthy `Health Status`. All passed.

**Part B — missing evidence / failed read:** `self_diagnosis.compute_fallback_count` monkeypatched to raise. Result: `health_status=UNKNOWN`, `confidence=degraded`, `current_mode=degraded` — never coerced to a positive reading. Passed.

**Part C — live baseline read:** `compute_self_state_core()` against real Firestore, `confidence="full"` (the read itself succeeded completely). **Came back `DEGRADED`** — see §8, this is real, not a test artifact.

**Part D — live evidence wiring:** injected one real `fallback_activation` event, confirmed it flows through to `compute_self_state_core()`'s diagnosis summary with the exact same explanation text `self_diagnosis` itself produces. Passed, cleaned up.

**Part E — live DEGRADED trigger + priority:** injected one real `verbatim_mismatch` event, confirmed `compute_verbatim_mismatch_diagnosis()` (the new function) picks it up with a real, resolvable `evidence_event_id`, and confirmed the combined state correctly reports `DEGRADED`/`degraded` (not `WATCH`, proving DEGRADED's priority over the fallback-driven WATCH signal). Passed, cleaned up.

**Part F — paraphrasing rejection (the core Option A proof):** registered a known exact text as a pending verification for a synthetic chat, then called `verify_and_finalize` with a deliberately paraphrased reply. The exact text was force-appended into the final response, a real `verbatim_mismatch` event was recorded for `entity_id="self_state_core"`, and — as a false-positive check — a second call with a reply that *did* contain the exact text passed through completely unmodified. All three assertions passed; test event cleaned up.

**Part G — Loans regression:** called `request_verified_expression("tracking_stability", ...)` (unchanged code path, now routed through the refactored `register_pending_verification`) and confirmed a matching reply passes through `verify_and_finalize` with zero modification — proving the refactor changed nothing about the Loans path. Passed. (Log also shows the Shadow pipeline still firing independently and correctly, untouched by this milestone.)

**Full suite run, full cleanup confirmed** (`🧹 اتمسح 3 حدث اختبار`), then a separate, final read-only query confirmed the real (non-test) counts settled back to their true values (fallback=0, rejection=0, mismatch=4) — proving no test data leaked into the persistent picture.

## 8. A real finding, not a test artifact (flagging explicitly)

Before any of my test injections, the live baseline read already showed:
- `mismatch` count = **4** real `verbatim_mismatch` events in the last 30 days (the Verbatim Match Validator has been silently catching and correcting real paraphrasing attempts in production this whole time — this was always happening, it was simply never surfaced anywhere until this milestone gave it a reader).
- `pending_obligation_load` = `concern` (7 real overdue installments — already known from prior audits, now folded into Internal Warnings for the first time).
- Net result: **`health_status=DEGRADED`, `current_mode=degraded`**, with `confidence=full` (the read itself is completely reliable — this is a real condition, not a read failure).

This is exactly the kind of thing Self State Core exists to surface, and it did, on the very first real query. I'm not treating this as a problem to silently fix in this milestone (out of scope — this milestone was about building the reader, not changing the underlying pipeline's behavior) — flagging it plainly for your awareness and next-step judgment.

## 9. Risks

- The `DEGRADED` reading above means if Ahmed asks `get_adam_self_state` right now, he'll be told the system is degraded — accurate, but worth being aware this is the current live answer, not a hypothetical.
- `register_pending_verification`'s docstring/shape is now a small piece of shared contract between two callers (Loans and Self State Core) — any future change to `_pending_verifications`'s entry shape needs to consider both.
- No new risk introduced to the Loans path (regression-tested), Shadow Mode (untouched), or Active Expression (untouched).

## 10. Remaining Work

- Nothing from this milestone is left half-done.
- Explicitly **not** implemented, per the approved scope lock: Current Goal, Current Task, Active Session, Current Focus, Execution Progress, Blocked Operations, Available Capabilities.
- **Next, only after your review:** the separate Minimal Capabilities Registry + Minimal Execution Tracker milestone, before any further Self State fields are considered.

**Stopping here for review, per your instruction.**

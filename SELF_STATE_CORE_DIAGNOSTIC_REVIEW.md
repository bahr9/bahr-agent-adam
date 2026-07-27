# Self State Core — Final Diagnostic Review
Date: 2026-07-27
Status: **Diagnostic review only. No code modified.**

---

## 1. Separation of System Health from Domain State

**Claim to verify:** runtime/verification evidence may drive `health_status`; Loans/domain data may appear only in `internal_warnings`; domain warnings must never, by themselves, classify `health_status` as `DEGRADED`.

**Verified by structure, not just by test.** `compute_health_status(fallback, rejection, mismatch, diagnosis_ok)` — its full parameter list — **never receives `self_state` (the Loans dimensions) at all.** It is not filtered out at runtime; it is architecturally impossible for it to see that data, because the function signature doesn't include it. The live `DEGRADED` reading you saw was produced **entirely** by `mismatch.count = 4 ≥ MISMATCH_DEGRADED_THRESHOLD(1)` — confirmed directly by the unit test in the previous milestone (`compute_health_status(healthy, healthy, one_mismatch, True) → DEGRADED`, with `fallback`/`rejection` both at zero). The 7 overdue installments played **zero role** in that classification.

Per field, precisely:

| Field | Touches Loans/domain data? | Verdict |
|---|---|---|
| `health_status` | **No** — parameter list structurally excludes `self_state` | ✅ Correctly separated |
| `diagnosis_summary` | **No** — built only from the 3 self-diagnosis explanations | ✅ Correctly separated |
| `internal_warnings` | **Yes, by design** — includes both the 3 Loans dimensions and the 3 self-diagnosis counters in one flat list | ⚠️ See gap below |
| `current_mode` | **Indirectly, yes** — `compute_current_mode` takes the *combined* `internal_warnings` list as an input; a domain-only warning (e.g. only overdue installments, zero runtime issues) is enough to push it to `"attention_needed"` even when `health_status == "HEALTHY"` | ⚠️ See gap below |

**Two real gaps, not a health_status bug:**

1. **`internal_warnings` has no category tag.** Each entry has a `source` field (e.g. `"pending_obligation_load"` vs `"verbatim_mismatch"`), but nothing marks *which kind* of concern it is. A reader — human or the model relaying this to Ahmed — has to already know that `pending_obligation_load` is a business/domain concern and `verbatim_mismatch` is a runtime/reliability concern. That's inferable from the name today, but it isn't explicit, and it's exactly the kind of implicit distinction that erodes over time (e.g. if a future dimension name doesn't make its category obvious).
2. **`current_mode` doesn't distinguish the two kinds of warning either.** It was designed as "the final holistic summary" and deliberately synthesizes across both categories — that was an intentional choice in the approved plan, not an oversight. But it does mean a purely domain-driven signal (only "7 overdue installments," zero runtime issues) currently reads out as `"attention_needed"`, the same label a real runtime problem would produce. You didn't explicitly forbid this (your constraint named `health_status` specifically), but it sits close enough to the concern you raised that I'm flagging it rather than assuming it's fine.

**Conclusion for §1: `health_status` is cleanly separated, confirmed structurally, not just observationally. `internal_warnings`/`current_mode` mix the two categories by design, which is defensible, but the mixing is implicit rather than explicit — a small semantic gap, not a health_status contamination bug.**

---

## 2. Analysis of the Four Real Verbatim Mismatches

Queried directly from Firestore (`adam_events` for the raw mismatch events, `adam_expressions` for the linked Expression records via `expression_id`). **Important, honest limitation up front:** the current event schema (built in Stage 6/7, before this milestone) records *that* a mismatch happened and *which* dimension/expression it belonged to, but it never persisted the model's actual paraphrased text or the literal final message sent. That data was only ever transient (a log line with no text in it, and nothing in Firestore). I am reporting exactly what exists and marking every field that cannot be known, rather than inferring plausible-sounding content.

| # | Timestamp (Cairo) | Dimension | Runtime path | Verified? | Expected verified text |
|---|---|---|---|---|---|
| 1 | 2026-07-26 01:22:29 | `pending_obligation_load` | `request_verified_expression` (Passive) → `verify_and_finalize` | `verified: False` | "مش قادر أتأكد من حالة الالتزامات المتأخرة دلوقتي -- المعلومة ناقصة." |
| 2 | 2026-07-26 01:22:29 | `unresolved_conflict` | same | `verified: True`, level `none` | "مفيش أي تعارض معلّق دلوقتي." |
| 3 | 2026-07-26 01:22:30 | `tracking_stability` | same | `verified: True`, level `none` | "معدل التصحيحات في آخر 30 يوم عادي." |
| 4 | 2026-07-26 09:10:23 | `pending_obligation_load` | same | `verified: False` | "مش قادر أتأكد من حالة الالتزامات المتأخرة دلوقتي -- المعلومة ناقصة." (identical to #1) |

- **Tool/expression involved:** all four went through the same tool — the model's `request_verified_expression` call, Passive mode, in the standard `handle_message` path (not the Active/scheduled path, which never touches this mechanism at all).
- **Model-produced text:** **not knowable** — never persisted.
- **Final restored text as literally sent:** **not directly knowable either** — but the *mechanism guarantees* it was `<whatever the model wrote> + "\n\n" + <the exact verified text above>`, since that is unconditionally what `verify_and_finalize` does on any mismatch. So while I can't show you the literal final string, I can state with certainty what it structurally contained.
- **Meaning-changing or only stylistic?** Cannot be confirmed directly (no stored text), but the pattern is informative: events #2 and #3 fired **9 seconds apart, in the same turn, both `verified=True` "nothing to report" sentences.** The most plausible read — a pattern (multiple simultaneous "all clear" facts naturally inviting a single combined summary sentence instead of two separate canned ones), not a fabrication attempt — is consistent with benign summarization, not invented facts. I'm stating this as an inference from the pattern, not as an observed fact.
- **Did the validator prevent user-visible drift?** **Yes, structurally guaranteed in all four cases.** `verify_and_finalize` never sends a response missing a pending verified text — it always appends it before returning. Ahmed received the authoritative, evidence-backed sentence in all four messages regardless of what the model wrote around it.
- **Same repeated cause?** **Yes — events #1 and #4 are the same cause, 8 hours apart.** Both are `pending_obligation_load`, both `verified: False`, both the identical "info missing" text. This is not two independent glitches; it's one structural condition recurring: `compute_pending_obligation_load()`'s evidence trail is empty whenever an overdue installment has never had an explicit `paid_status` event logged against it (a known, documented gap from Stage 5 — evidence-for-overdue-items only exists if a payment event was ever recorded, and here none has been). Every time this condition holds and Ahmed asks about loans, the model gets the `verified=False` fallback sentence, and apparently doesn't reliably paste it verbatim.

Redacted: the real Telegram `chat_id` present on all four linked Expression records has been omitted above (personal identifier, not needed for this analysis; all four share the same one, consistent with a single ongoing conversation).

---

## 3. Reassessment of the V1 Threshold (analysis only — not changed)

Weighing your three interpretations against what the real data actually shows:

- *"A mismatch means an unsafe divergence was attempted"* — **overstated** for what we found. Nothing in these four events looks like an invented number or a contradicted fact; the pattern looks like benign paraphrase/summarization friction against a strict verbatim rule.
- *"A caught and restored mismatch means the protection system worked"* — **the more accurate characterization.** All four were caught, all four were corrected before sending, by construction. In that narrow sense, these four events are evidence the safety net works, not evidence something is broken.
- *"Repeated mismatches may indicate an upstream problem even when caught"* — **this is the one the data actually supports.** Events #1 and #4 are a real repeated pattern with a real root cause (the `pending_obligation_load` evidence gap), 8 hours apart. That's a legitimate signal worth elevating attention to, distinct from a one-off.

**Assessment: the V1 rule ("any mismatch in 30 days → DEGRADED") is not wrong, but it is too coarse.** It currently treats a single first-time, successfully-contained blip exactly the same as a recurring, root-caused pattern — collapsing two meaningfully different situations into one label. Given the safety net demonstrably worked in all four real cases, labeling the *current* state "DEGRADED" (a word that reads as "something is broken") somewhat overstates what's actually true today: the expression system is doing its job; one specific, known, structural gap keeps triggering its safety net.

**Recommendation for a future (not now) refinement**, using your proposed categories against what we actually observed:
- **Attempted mismatch** — happened, all four times.
- **Uncaught mismatch** — did not happen, and structurally cannot happen today as long as `verify_and_finalize` is called on every send (confirmed: all 11 real send-points do call it, per the Runtime Activation audit). Worth stating as a genuine strength, not just an unused category.
- **Repeated mismatch** — happened once, confirmed (events #1/#4). This is the category that most deserves its own weight in a future threshold, since it points at a fixable root cause rather than incidental noise.
- **Successfully contained mismatch** — true of all four; arguably the *default* expected outcome of the current architecture, not a symptom.

If I were designing V2 (not doing so now), I'd weight "same dimension mismatching more than once in the window" more heavily than "any single mismatch," and treat a lone, first-time, successfully-contained mismatch as closer to `WATCH` than `DEGRADED`. I am not changing the threshold — flagging this as the concrete direction your question was pointing toward.

---

## 4. Evidence Integrity

| Claim | Status | Detail |
|---|---|---|
| Every Self State Core claim includes evidence IDs | **Partially true — one real gap found.** `internal_warnings` entries each carry their own `evidence_event_ids` (verified in code). But the **top-level `health_status` and `diagnosis_summary` fields in `compute_self_state_core()`'s returned dict do not themselves carry an `evidence_event_ids` list** — the evidence exists and is traceable one level down (inside the `fallback`/`rejection`/`mismatch` dicts consumed to build them), but it isn't surfaced at the same level as the claim itself. This is the kind of gap your review process is designed to catch. |
| Failed reads produce `UNKNOWN` | **True for `health_status`, confirmed live** (Part B: one signal failing → `health_status="UNKNOWN"`). More precisely: a **partial** failure (1 of 4 signals) produces `confidence="degraded"` and `current_mode="degraded"`, not `"unknown"` — only a **total** failure (all 4 signals) produces `confidence="unknown"`/`current_mode="unknown"`, and that specific total-failure path was verified only at the pure-function level (`compute_confidence(4 errors) == "unknown"`), not via a live simulated total outage. Worth being precise about which failure depth was actually exercised. |
| No LLM is used to calculate the state | **Confirmed structurally.** `self_state_core.py`'s only imports are `event_store`, `self_diagnosis`, `self_state_engine`, `utils.time_utils` — no `claude_service`, no `companionship_layer`, anywhere in the file. |
| Loans verification path unchanged | **Confirmed both ways** — by construction (`register_pending_verification` is a direct extraction of the pre-existing one-line append, same dict shape, same call site) and by the live regression test (`request_verified_expression("tracking_stability", ...)` → `verify_and_finalize` produced an unmodified pass-through, exactly as before). |
| Test events fully cleaned up, cannot affect production result | **Confirmed by a separate follow-up query**, not just by the test's own internal assertion: after cleanup, a fresh, independent read showed real counts back to `fallback=0, rejection=0, mismatch=4` — matching the true pre-test state exactly, with no leaked test data. |

---

## 5. Final Milestone Judgment

### **Requires a small semantic correction.**

Not "approved as implemented" — two concrete, narrow gaps were found, both surfaced by this very review: (1) `health_status`/`diagnosis_summary` don't carry their own `evidence_event_ids` at the top level, weakening the "every claim is evidence-backed" guarantee in its strictest reading; (2) `internal_warnings` mixes domain and runtime concerns without an explicit category tag, which is exactly the kind of implicit distinction §1 asked me to check for.

Not "approved with a threshold adjustment" — the V1 threshold itself isn't the problem; per your explicit instruction I haven't touched it, and my honest assessment is that it's a reasonable, conservative provisional rule that happens to have surfaced a real repeated issue on its very first real-world exercise. A future, better-informed threshold (distinguishing repeated from first-occurrence) is a real recommendation, but it's a refinement to schedule deliberately, not something today's review found broken.

Not "requires architectural correction" — the core separation you were most concerned about (`health_status` staying clear of domain state) is already correct, confirmed structurally rather than incidentally. Nothing here calls for a redesign of `self_state_core.py`, the verification mechanism, or the event schema's overall shape.

**The two semantic corrections, for your future decision (not implemented, not scheduled by me):** add `evidence_event_ids` to the top-level `health_status`/`diagnosis_summary` output, and add an explicit `category: "domain" | "runtime"` tag to each `internal_warnings` entry. Both are small, additive, localized changes to `self_state_core.py` only — no other file would need to change.

**No code was written or modified in this review. No new milestone has been started.**

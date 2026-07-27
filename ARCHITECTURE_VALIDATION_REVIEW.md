# Architecture Validation Review — Post Runtime-Activation Milestone
Date: 2026-07-27
Status: **Review only. No code modified in this pass** (re-confirmed via fresh `grep` against the current working tree, not by re-reading the milestone report's own claims).

---

## 1. Runtime Activation Report

### BEFORE this milestone

```
Telegram/Scheduler
  → AdamRuntime → ExecutiveBrain → claude_service.ask_claude_agentic
      → tool: request_verified_expression
          → verified_expression.request_verified_expression(dimension)
              → self_state_engine.compute_self_state()
              → expression_vocabulary.get_template() / render_verified_false()
              → return {verified, text, expression_id}      [closed-vocabulary text -- the only text that ever existed]
      → bot reply → verified_expression.verify_and_finalize() → Telegram

  hourly job: self_state_active_check_job
      → self_state_engine.compute_self_state() → decision_engine.decide_expression()
      → verified_expression.send_active_expression() → bot.send_message() → Telegram   [zero LLM, unchanged by this milestone]

DEAD ENDS (built, tested, zero non-test callers):
  truth_layer.py, meaning_layer.py, inference_rules.py, companionship_layer.py,
  claim_validator.py, renderer.py, self_diagnosis.py (write-only)

DUPLICATE / DISCONNECTED:
  adam_human_model.py (local file, never persisted, fed only main.py's greeting)
  firebase_service.get_human_model/update_human_model (Firestore, tool-exposed, live)
```

### AFTER this milestone

```
Telegram/Scheduler
  → AdamRuntime → ExecutiveBrain → claude_service.ask_claude_agentic
      → tool: request_verified_expression
          → verified_expression.request_verified_expression(dimension)
              → self_state_engine.compute_self_state()
              → expression_vocabulary.get_template() / render_verified_false()
              → [old-path result computed -- UNCHANGED, this is what gets returned]
              → _shadow_run_pipeline(dimension, old_text)              <-- NEW
                  → truth_layer.build_truth_packet_for_loans()
                  → truth_layer.validate_truth_packet()
                  → truth_layer.truth_packet_confidence()
                  → inference_rules.evaluate_fired_rules()
                  → meaning_layer.compute_meaning_packet()
                  → companionship_layer.generate_message()
                      → claude_client.messages.create()  [REAL Anthropic call]
                      → claim_validator.validate_companionship_output()
                          → renderer.render()  [internal, for slot-fill check]
                      → [only if both attempts fail] event_store.record_event(self_diagnosis: fallback_activation / validator_rejection)
                  → logger.info("[shadow] old=... new=... source=... match=...")   <-- exit point
              → return {verified, text, expression_id}   [IDENTICAL to before -- proven live, see Milestone report §7]
      → bot reply → verified_expression.verify_and_finalize() → Telegram

      → tool: get_self_diagnosis_report                                <-- NEW
          → self_diagnosis.compute_fallback_count()
          → self_diagnosis.compute_validator_rejection_diagnosis()
          → return combined string → Claude relays it → Telegram

  hourly job: self_state_active_check_job → send_active_expression()   [UNCHANGED -- shadow was added
                                                                          only to request_verified_expression,
                                                                          not to the Active path]

  main.py /start + startup log
      → firebase_service.get_human_model_display_name()                <-- NEW helper, one source
          → firebase_service.get_human_model() → Firestore read
```

### Per-path detail

| Path | Entry point | Call sequence | Exit point | User-visible? | Shadow or Live? |
|---|---|---|---|---|---|
| **T→M→C shadow pipeline** | `verified_expression.request_verified_expression()`, reached only via the model's `request_verified_expression` tool call (itself only invoked when Ahmed asks about self-state) | `truth_layer.build_truth_packet_for_loans` → `validate_truth_packet` → `truth_packet_confidence` → `inference_rules.evaluate_fired_rules` → `meaning_layer.compute_meaning_packet` → `companionship_layer.generate_message` (real Anthropic call → `claim_validator.validate_companionship_output` → `renderer.render` internally → on double-failure `event_store.record_event`) | `logger.info("[shadow] ...")` -- no value returned to caller | **No** -- proven live: returned dict is byte-identical to the old path | **Shadow** |
| **`self_diagnosis` reader** | `claude_service.py` tool dispatch (`get_self_diagnosis_report`), reached when Ahmed asks about the health of the expression system | `self_diagnosis.compute_fallback_count()` → `compute_validator_rejection_diagnosis()` → string concatenation | Returned to the agentic tool loop → becomes part of Claude's reply → `verify_and_finalize` (passthrough, nothing pending) → Telegram | **Yes** -- genuinely new information reaches Ahmed | **Live** (no shadow concept applies to a pure reader) |
| **Human Model consolidation** | `main.py` (`/start` handler, startup log); `morning_brief.py` and `claude_service.py`'s `get_human_model`/`update_human_model` tools were *already* live on this same path before this milestone | `get_human_model_display_name()` → `get_human_model()` → Firestore read | Returned string used directly in the greeting / log line | **Yes**, but verified byte-identical to pre-milestone output after the nickname backfill | **Live** (was already live for the tool-based consumers; newly unified for the greeting) |

**Unchanged and worth stating explicitly:** Active Expression (`send_active_expression`, the hourly job) was **not** touched — it remains zero-LLM, per the Stage 6/7 lock. Shadow Mode only attaches to the Passive path.

---

## 2. Accepted Documents Activation Status

Only documents/modules whose runtime status actually changed as a result of this milestone:

| Document/Module | Previous status | Current status | Runtime effect | Code responsible for activation |
|---|---|---|---|---|
| `TRUTH_LAYER_PHASE1.md` (`truth_layer.py`) | INACTIVE (zero non-test callers) | **PARTIALLY ACTIVE** (executes on every real Passive check; output never delivered) | Builds a real `TruthPacket` from live Firestore data on every Passive self-state check | `verified_expression._shadow_run_pipeline()` |
| `MEANING_LAYER_PHASE1.md` (`meaning_layer.py`) | INACTIVE | **PARTIALLY ACTIVE** (same profile) | Computes a real `MeaningPacket` on every Passive check | same |
| `TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE_V2.md` (`inference_rules.py`, `companionship_layer.py`, `claim_validator.py`, `renderer.py`) | PARTIALLY ACTIVE (built + self-tested only, zero production execution) | **PARTIALLY ACTIVE, upgraded** (now executes against live production data + a real Anthropic call on every Passive check) | Full pipeline runs end-to-end for real, output logged not sent | same |
| `EXPRESSIVE_VOICE_RECONSIDERATION_DRAFT.md` §6.2 (Decision Gate) | Gate's own precondition ("Level A running in real use") was **unsatisfiable** -- Level A had never run against real traffic | Precondition is **now actively being satisfied** -- real-use evidence is accumulating with every Passive check (still zero live-use evidence *before* this milestone, non-zero and growing now) | Gate itself unchanged (still requires "sufficient" evidence, a judgment call for later); what changed is that evidence collection has *started* | same |
| `self_diagnosis.py` (governed by `CONSTITUTION.md` + `EXPRESSIVE_VOICE...` self-diagnosis sections) | INACTIVE (write-only -- events recorded, never read) | **ACTIVE** (fully wired: written by `companionship_layer`/`verified_expression`, read via the new tool) | Ahmed can now ask about and receive real fallback/rejection telemetry | `claude_service.py`'s `get_self_diagnosis_report` tool |
| `ADAM_PERSONAL_EXECUTIVE_SYSTEM_PLAN.md` §4A (Human Model, *this subsection only*) | PARTIALLY ACTIVE (fragmented -- two disconnected implementations) | **ACTIVE** (single Firestore source of truth for all consumers) | Every consumer (`main.py` greeting, `morning_brief.py`, `get_human_model`/`update_human_model` tools) now reads/writes the same document | `firebase_service.get_human_model_display_name()` + deletion of `adam_human_model.py` |

**Not changed, stated for completeness:** `CONSTITUTION.md` itself is still never "loaded" by any code (unchanged -- it's a governance reference by design, see the original Traceability Matrix §1). `ADAM_PERSONAL_EXECUTIVE_SYSTEM_PLAN.md` as a whole is still overwhelmingly PARTIALLY ACTIVE/INACTIVE -- only its §4A subsection resolved.

---

## 3. Remaining Inactive Architecture

### A. Existing code that only needs activation (built, present in the repo, not reachable)

| Item | Why it's not simply "done" |
|---|---|
| `handlers/command_handler.py` | The one caveat in this category: it is **broken**, not just disconnected -- it imports `services.task_service`, which does not exist anywhere in the repo. It cannot be "activated" by wiring it in; it would first need `task_service` built or the import removed/repaired. This is qualitatively different from the two items activated this milestone, which were complete and merely disconnected. |

That is the only remaining item in this category. The two clean "built-but-disconnected" targets identified in the original Traceability Matrix (§5, "What this means for the runtime activation layer") were the T→M→C pipeline and `self_diagnosis.py` -- both addressed this milestone. Nothing else in the repo matches the "complete, tested, zero callers" profile.

### B. Architecture that has not been implemented yet (roadmap, no code exists)

From `ADAM_PERSONAL_EXECUTIVE_SYSTEM_PLAN.md`:
- Context Engine (§5) -- no structured Context Package assembly exists; `ExecutiveBrain._stage_context` still only gathers history + memory.
- Capabilities Registry + Phonebook (§7) -- no such structure; tools remain ad hoc entries in `claude_service.TOOLS`.
- Work Graph (§8) -- only the pre-existing, much shallower generic graph tool exists.
- Specialized Agents (§9) -- no sub-agent routing exists.
- Verification System, Requested→Planned→Executed→Verified→Recorded (§10) -- `ExecutiveBrain`'s "Validate" stage remains a non-empty-string check.
- Most of Initiative Engine (§11) -- Morning Brief/Loan alerts/Self-State alerts exist; Site Risk Alerts, Before-Meeting Brief, End-of-Day Review do not.
- Business Memory / Project Memory (§4B/C) -- richer structures than the current ad hoc project tools do not exist.
- Working Memory (§4F) -- no dedicated implementation.

From the Truth/Meaning/Companionship design docs:
- `services/decision_trace.py` (`TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE_V2.md` §8) -- proposed, never created.
- Level B (free-form claim generation + post-hoc validation) -- explicitly and correctly not to be discussed yet, per the Decision Gate (§6.2) this milestone just started satisfying the precondition for, not fulfilled.
- Semantic Claim Representation / AST (v2 roadmap item) -- explicitly deferred by the original design itself.
- Full Rule Engine with conflict resolution (v2 roadmap item) -- explicitly deferred, intentionally, until rule count grows.
- `computation_ok` flag on `self_state_engine.py`'s `compute_*` functions -- proposed in two separate docs, never implemented; this is the reason `TruthPacket.integrity.partial` can't yet be populated with full accuracy.

**Deliberately not pursued (neither A nor B -- a decided "no" rather than a gap):** `self_diagnosis.py`'s `tool_relevant_but_skipped` dimension was explicitly investigated and rejected as unbuildable under the current tool-dispatch architecture (documented reasoning in the module's own docstring) -- worth distinguishing from things that are simply not built yet.

---

## 4. Human Model Review

**Confirmed: exactly one source of truth.** Fresh `grep` across the entire repo (not a re-read of the milestone report) shows:
- Zero remaining references to `adam_human_model` as a Python import, to `HumanModel()`, or to `human_model.get_name()` anywhere.
- The only remaining occurrences of the literal string `adam_human_model` are the Firestore **collection name** (`config.py`, `firebase_service.py`, `services/backup_service.py`'s backup list) -- correct and expected, not a reference to the deleted module.

**Read path:** `firebase_service.get_human_model()` -- reads Firestore `adam_human_model/ahmed_gowaida`; creates the doc with defaults (now including `nickname`) if it doesn't exist yet.

**Write path:** `firebase_service.update_human_model(key, value)` (single field, merge write) and `update_human_model_bulk(data)` (multi-field, merge write). Both unchanged by this milestone -- they were already the live write path.

**Runtime consumers (all confirmed via grep, all reading/writing the same document):**
- `claude_service.py` tools `get_human_model` / `update_human_model` (pre-existing, already live before this milestone).
- `morning_brief.py` -- calls `get_human_model()` directly (pre-existing, already live before this milestone; not mentioned in the original milestone report but confirmed now).
- `main.py` -- `/start` handler and startup log, now via the new `get_human_model_display_name()` helper (this milestone's change).

No consumer reads from anywhere else. Single source of truth confirmed, not just asserted.

---

## 5. Shadow Mode Review

**Exactly when it runs:** Only inside `verified_expression.request_verified_expression()`, which is only called from one place -- the `request_verified_expression` tool dispatch in `claude_service.py`. That tool is only invoked by the model when Ahmed's message triggers a genuine Passive self-state check (per the system prompt's explicit instruction to use it, not on every message). It does **not** run on the hourly Active job (`send_active_expression` was not touched) and does **not** run on ordinary conversation turns that never touch self-state.

**Does it perform an Anthropic API call every execution?** Yes, always at least one (`companionship_layer._call_llm` inside `generate_message`), and a second one specifically when the first attempt fails `claim_validator` validation and a corrected retry is attempted (`companionship_layer.generate_message`'s retry branch, max one retry). So: 1 call on the common path, 2 calls on the retry path, 0 calls only if an earlier guard short-circuits (truth packet validation errors, or `confidence == "degraded"`) -- both logged and returned early before any LLM call, confirmed by the code structure in `_shadow_run_pipeline`.

**Estimated additional runtime cost:** Bounded by frequency, not by conversation volume -- it scales with how often Ahmed actually asks about loans/self-state, not with every message ADAM receives. Each call is small (system prompt ~150 words, `max_tokens=300` output cap, no conversation history, no tools) -- materially cheaper per-call than the main `ask_claude_agentic` turn it rides alongside, but it is a genuine, non-zero addition on top of whatever that turn already cost. I'm not going to fabricate a precise dollar figure here; if you want an exact cost projection I can pull current Sonnet pricing and multiply by your actual self-state-check frequency from the logs.

**Can it later be controlled by a feature flag or sampling without architectural changes?** Yes, cleanly. There is exactly one call site (`_shadow_run_pipeline(dimension, result["text"])` inside `request_verified_expression`). A flag check (`if config.SHADOW_MODE_ENABLED:`) or a sampling gate (`if random.random() < SHADOW_SAMPLE_RATE:`) wrapped around that single call site is a localized, few-line change -- it does not touch the pipeline's internals, the old path, or any other file. This was a deliberate consequence of keeping the integration to one call site, not an accident.

---

## 6. Readiness Assessment

**Honest answer: not fully ready for Self State as the mission defines it (all twelve fields), but the runtime foundation itself is sound and this milestone measurably improved it.** Here is the reasoning, based only on what exists in the codebase today:

**What's genuinely solid and reusable:**
- `ExecutiveBrain`/`AdamRuntime`/`AdamMind` are disciplined, tested, and internally consistent -- a stable base to extend.
- The Event Store + evidence-ID pattern (proven across Loans, and now also self-diagnosis) is exactly the substrate Self State's evidence-backed fields would need, and it's now proven end-to-end against real data twice over (Loans, and this milestone's shadow pipeline).
- `self_state_engine.py`'s `full`/`degraded` confidence pattern is a working, reusable model for a "Current Confidence" field.
- `self_diagnosis.py`, now with a reader, is the closest existing analog to genuine self-reflective architecture (health/warnings about ADAM's own behavior) -- a real, if narrow, precedent to build on.

**What's genuinely missing, specifically for the fields the mission's Self State asks for:**
- **Available Capabilities** -- there is no Capabilities Registry (confirmed still INACTIVE/unbuilt, §3B above). This field would have nothing real to enumerate; building it honestly means building the registry first, which is itself non-trivial new work, not "activation."
- **Execution Progress / Blocked Operations** -- there is no Requested→Planned→Executed→Verified→Recorded state machine (§3B). `ExecutiveBrain`'s current "Validate" stage is a non-empty-string check, nothing tracks an in-flight operation's state.
- **Active Session / Current Focus / Current Goal / Current Task** -- nothing in the current architecture persists a notion of "what am I doing right now" across a turn or a session. Each message is handled with conversation history + a memory summary; there is no session/task object anywhere to attach these fields to.
- **Current Mode** -- the closest existing analog is Active/Passive from `decision_engine.py`, but that's scoped to the Loans self-state expression decision specifically, not a general operating mode.

**Conclusion:** If Self State is scoped to what the current architecture can honestly support today -- Health Status, Internal Warnings, Current Confidence, Current Mode, built by extending the `self_diagnosis.py` / `self_state_engine.py` event-sourced pattern -- that is a reasonable, small, "activation-style" next step consistent with everything done this milestone. If Self State is scoped to the *full* twelve-field definition in the mission (adding Goal/Task/Session/Focus/Capabilities/Execution Progress), that requires building real new substrate first (a Capabilities Registry and a genuine execution-tracking mechanism, at minimum) -- which is legitimate, necessary work, but it is new architecture, not activation of something that already exists, and attempting to fake those fields on top of today's codebase would produce a Self State that reports on things ADAM cannot actually verify about itself -- the exact failure mode this whole mission was set up to prevent.

**Recommendation, not a decision:** scope the first Self State increment narrowly to the fields with real backing today, and treat Capabilities Registry + a minimal execution-state tracker as an explicit, separate prerequisite milestone before attempting the rest -- rather than one large Self State push.

---

**No code was modified during this review.**

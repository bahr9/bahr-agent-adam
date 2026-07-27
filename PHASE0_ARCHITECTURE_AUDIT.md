# Phase 0 — ADAM Architecture Audit
Date: 2026-07-27
Status: **Audit only. Zero code changes made.** Prepared per the "ADAM Architecture Activation Mission."
Method: full read of all 18 architecture/status `.md` documents in the repo root, full read of the runtime core (`main.py`, `executive_brain.py`, `adam_mind.py`, `adam_runtime.py`, `adam_human_model.py`, `config.py`), full read of `services/verified_expression.py`, `services/self_diagnosis.py`, `services/memory_service.py`, targeted reads of `services/claude_service.py` (system prompt, tool count, dispatch table) and `services/firebase_service.py` (Decision Ledger section), and `grep`-verified import graphs across every `.py` file (not assumed from docs — independently re-checked). Git state cross-checked against `CHECKPOINT_2026-07-24.md` (6 commits landed since, 2026-07-25/26, latest: "Decision Ledger - Phase 1 Memory Architecture").

---

## 1. Runtime Architecture Diagram

```
                              ┌─────────────────────────────────────────────┐
                              │              Entry Points                    │
                              │  Telegram (bot.py polling)                   │
                              │  Flask :8080  (/log-eye-expert, /health)     │
                              │  APScheduler (7 jobs, see §2)                │
                              └───────────────────┬───────────────────────────┘
                                                  ▼
                              adam_runtime.AdamRuntime.run() / run_scheduled()
                              (thin gateway -- builds BahrEvent, never swallows exceptions)
                                                  ▼
                              executive_brain.ExecutiveBrain.run()   [7 stages]
                    ┌─────────────────────────────────────────────────────────────┐
                    │ 1. Intent      -> adam_mind.AdamMind.analyze()              │
                    │                   (keyword fast-path -> Haiku slow-path)    │
                    │ 2. Context     -> conversation history (last 50, fmt 15)    │
                    │                 + memory_service.get_memory (Firestore)     │
                    │                 [Human Model / Decision Ledger / Project    │
                    │                  state NOT auto-included -- pull-only]     │
                    │ 3. Plan        -> always capability="claude_agentic" (v1)   │
                    │ 4. Execute     -> claude_service.ask_claude_agentic()       │
                    │ 5. Validate    -> non-empty string check only (placeholder)│
                    │ 6. Learn       -> save_conversation (always) +             │
                    │                   2-tier LearningDecision -> update_memory │
                    │ 7. Respond     -> return text                              │
                    └─────────────────────────────────────────────────────────────┘
                                                  ▼
                    claude_service.ask_claude_agentic()
                    Claude Sonnet 5, agentic tool loop, 53 tools defined,
                    cached static system prompt + dynamic (time/memory) part
                                                  ▼
                    _execute_tool() dispatch  (single choke point for ~45 tools)
        ┌───────────────┬──────────────────┬───────────────────┬─────────────────────┐
        ▼               ▼                  ▼                   ▼                     ▼
firebase_service.py   loan_service.py   memory_service.py   verified_expression.py   firestore_db
(1292 lines, main     (loan domain      reminder_service.py request_verified_        DIRECT
Firestore             logic, wraps      weather_service.py  expression()             (4 tools bypass
abstraction; also     event_store)      openai_service.py                            firebase_service
Decision Ledger:                                                                     entirely --
save_decision/                                                                       add/update_client_
get_decisions)                                                                       followup,
                                                                                      update_project_
                                                                                      status,
                                                                                      update_eye_expert_
                                                                                      prompt)
                                                  ▼
                    bot.py handlers: verified_expression.verify_and_finalize()
                    called at ALL 11 outbound send points (handle_message,
                    9x handle_callback branches, weekly_report_job) --
                    Verbatim Match Validator, silently repairs any paraphrase
                    of an approved self-state sentence
                                                  ▼
                              bot.send_message / bot.reply_to -> Telegram
```

### Side systems (not in the direct request path)

```
Event Store (services/event_store.py, Firestore "adam_events", append-only)
   ▲ written by: loan_commands.py (paid_status, conflict_status)
   ▲ written by: verified_expression.py (self_diagnosis: verbatim_mismatch)
   ▲ written by: companionship_layer.py (self_diagnosis: fallback_activation, validator_rejection)
   ▼ read by:    loan_conflict_observer.py, self_state_engine.py, self_diagnosis.py

Self-State Engine (services/self_state_engine.py) -- pure functions, zero storage,
recomputed fresh every call from Event Store + loan schedule + today's date.
   ▲ called by: verified_expression.py, main.py::self_state_active_check_job (hourly)

Decision Engine (services/decision_engine.py) -- Active/Passive transition logic.
   State: only "last Active level notified per dimension" (adam_self_state, tiny doc)
   ▲ called by: main.py::self_state_active_check_job

Verified Expression Gate (services/verified_expression.py + expression_vocabulary.py)
-- the ONLY channel through which the model can describe its own internal state.
Closed-vocabulary lookup, zero free text. This is the LIVE, production self-
expression mechanism today (Stage 6/7, 2026-07-24).

Truth -> Meaning -> Companionship -> Renderer -> Claim Validator ("Level A")
-- services/truth_layer.py, meaning_layer.py, companionship_layer.py, renderer.py,
   claim_validator.py, inference_rules.py.
   Fully built, fully unit- and integration-tested (test_truth_layer.py 10/10,
   test_meaning_layer.py 12/12, test_renderer.py 10/10, test_companionship_layer.py,
   test_claim_validator.py, test_pipeline_integration.py) -- BUT verified by direct
   grep of every non-test .py file in the repo: NOT ONE production module imports
   truth_layer or meaning_layer. companionship_layer.py imports claude_service,
   claim_validator, expression_vocabulary, event_store -- but not meaning_layer or
   truth_layer either, so even the intended internal pipeline (Truth->Meaning->
   Companionship) is not wired module-to-module. verified_expression.py (the real
   production gate) imports only self_state_engine, expression_vocabulary,
   event_store -- it has no reference to any Level-A file. This entire subsystem
   is a parallel, fully-tested, zero-runtime-callers island.

Self-Diagnosis (services/self_diagnosis.py) -- consumes self_diagnosis-typed
events written by companionship_layer.py and verified_expression.py.
   compute_fallback_count() / compute_validator_rejection_diagnosis() exist and
   are correct, but grep confirms zero callers anywhere except test_self_diagnosis.py.
   Data flows in; nothing ever reads it out.

Human Model -- TWO independent, disconnected implementations sharing one name:
   (a) adam_human_model.py -- local JSON file (adam_human_model.json), class
       HumanModel, instance `human_model`. Used in main.py only for
       human_model.get_name() (the /start greeting + one startup log line).
       Never fed into the system prompt or context. Effectively dead weight.
   (b) firebase_service.get_human_model() / update_human_model() -- Firestore
       collection "adam_human_model" (config.HUMAN_MODEL_COLLECTION), exposed
       as get_human_model / update_human_model tools, documented in the system
       prompt, reachable on demand by the model. This is the live one.

Decision Ledger -- firebase_service.save_decision() / get_decisions(), Firestore
collection "decision_ledger". Confirmed wired end-to-end: save_decision /
list_decisions tools defined in claude_service.py TOOLS, dispatched in
_execute_tool, described with explicit trigger conditions in the system prompt
(lines 93-94). Newest shipped feature (commit 11c5306, 2026-07-26). ACTIVE.
```

---

## 2. Current Flow Diagram (concrete message lifecycle)

1. Ahmed sends a Telegram message.
2. `bot.py` dispatch: menu-keyword match? inline-keyboard callback? else -> `handle_message`.
3. `runtime.run(message)` builds a `BahrEvent(source="user", ...)`.
4. `ExecutiveBrain.run()` executes the 7 stages listed in §1.
5. `handle_message` wraps the returned text through `verified_expression.verify_and_finalize()` before sending -- this is unconditional, every single time, regardless of whether the message actually touched self-state.
6. `bot.reply_to(...)`.

**Scheduled jobs (APScheduler, 7 registered in `main.py`):**
| Job | Cadence | Path |
|---|---|---|
| `check_reminders_job` | every 30s | direct Firestore read, no LLM |
| `check_recurring_reminders_job` | every 1 min | direct Firestore read, no LLM |
| `check_loans_job` | daily 09:00 | direct read-only alert, no LLM, no verified-expression wrap |
| `self_state_active_check_job` | hourly | `self_state_engine` -> `decision_engine` -> `verified_expression.send_active_expression` (zero LLM, per the locked Stage 6/7 decision) |
| `morning_brief_job` | daily 08:00 | `runtime.run_scheduled` -> `ExecutiveBrain._handle_scheduled` -> `morning_brief.generate_morning_brief` |
| `weekly_report_job` | Fri 13:00 | `ask_claude_agentic` directly (bypasses ExecutiveBrain) -> `verify_and_finalize` |
| `backup_job` | daily 02:00 | `backup_service.run_backup` |

---

## 3. Architecture Health Report

**Strengths**
- The Runtime / Executive Brain / Adam Mind v2 rewrite is disciplined and internally consistent with its own docstring contracts: `StageError` propagation, no silent `except: pass`, clear single-responsibility separation.
- The Loans self-state pipeline (Event Store -> Command API -> Conflict Observer -> Conflict Resolution -> Self-State Engine -> Decision Engine -> Verified Expression) is the best-realized piece of architecture in the repo: fully built, fully wired, fully tested against real Firestore at every stage, and is the one place where "accepted architecture" and "runtime behavior" are the same thing today.
- Decision Ledger, the newest feature, is cleanly wired end-to-end on the first attempt (tool definition -> dispatch -> service -> Firestore -> system-prompt trigger rules).
- Documentation discipline is unusually strong: every stage has a written contract, a Definition-of-Done checklist, and a real (not narrated) verification log against production Firestore.
- The `ADAM_PERSONAL_EXECUTIVE_SYSTEM_PLAN.md`'s Phase-0 review requests (restore history to 50/15, remove the blind 800/400-char cuts, keep `LearningDecision`) are **actually reflected in the current `executive_brain.py`** -- this specific review-and-fix loop closed correctly.

**Weaknesses / Gaps**
- The single most architecturally significant recent effort (Truth/Meaning/Companionship "Level A": `truth_layer.py`, `meaning_layer.py`, `companionship_layer.py`, `renderer.py`, `claim_validator.py`, `inference_rules.py`, plus `self_diagnosis.py`) is fully built and tested but has **zero production callers**. It is a parallel system, not an activated layer -- this is the textbook case the mission describes ("architecture that does not influence runtime is incomplete").
- Two disconnected "Human Model" implementations share a name; one is nearly dead code, and neither is part of automatic context assembly.
- `ADAM_PERSONAL_EXECUTIVE_SYSTEM_PLAN.md`'s wider vision (Context Engine, Capabilities Registry + Phonebook, Work Graph, Specialized Agents, a real Verification System, most of the Initiative Engine) is almost entirely undelivered -- only the Decision Ledger slice of a six-part Memory Architecture has shipped.
- Executive Brain Stage 5 ("Response Validation") is explicitly a placeholder in its own docstring ("مش Verification حقيقي لسه" -- "not real verification yet"), not the Verify/Record stages the newest plan calls for.
- Per-request context is narrow by design (conversation history + memory summary only); Human Model, Decision Ledger, and project state are all pull-based (the model must decide to call a tool) rather than part of the automatically assembled Context Package the newest plan specifies.

---

## 4. Risks

| # | Risk | Evidence |
|---|---|---|
| R1 | **Silent architecture fork.** Two generations of the self-expression mechanism exist simultaneously with no switch or flag between them: the closed-vocabulary Stage 6/7 gate (live) and the Level-A Truth/Meaning/Companionship pipeline (built, dormant). A future change could wire the dormant pipeline into `verified_expression.py` without realizing it alters a guarantee the project itself calls "locked forever" (Stage 6/7's Active=zero-LLM decision). | Confirmed via import graph: `verified_expression.py` has no reference to any Level-A module. |
| R2 | Most Firestore-writing tools (~21 of ~22 outside Loans) still have no event/audit trail. | `AUDIT_REPORT_STAGE0.md` finding, re-checked: no new Command-API layer found for expenses/projects/memory/reminders in current code. |
| R3 | 4 tools still write raw Firestore, bypassing `firebase_service.py` entirely (`add_client_followup`, `update_client_followup`, `update_project_status`, `update_eye_expert_prompt`). | Confirmed unresolved as of this audit -- same finding as 2026-07-24, no remediation found in the diffs since. |
| R4 | Multiple destructive tools execute with zero confirmation step (`delete_reminder`, `delete_all_reminders`, `delete_project`, `delete_expense`, `delete_recurring_reminder`, `delete_graph_node`, `delete_memory_note`). | Same as R3 -- unresolved since 2026-07-24. |
| R5 | `self_diagnosis.py` captures fallback/rejection telemetry that is never surfaced anywhere -- an observability system that observes into a void. | grep confirms zero callers of `compute_fallback_count` / `compute_validator_rejection_diagnosis` outside its own test file. |
| R6 | Dead code: `handlers/command_handler.py` imports a nonexistent `services.task_service` and is imported by nothing. | Re-confirmed today via grep (0 importers) -- unchanged from the 2026-07-24 finding. |

---

## 5. Technical Debt

- Dual Human Model implementations (local JSON file vs. Firestore tool) sharing one name.
- Dead `handlers/command_handler.py`.
- Known-benign corrupted Firestore field `paid.ca_71` (documented, harmless, still unswept, no functional impact).
- `self_state_engine.py`'s `compute_*` functions still return bare values, not `(value, computation_ok)` -- the `computation_ok` flag proposed in `SELF_STATE_ENGINE_STAGE5_DRAFT.md` and `TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE_V2.md` §10.1 was never implemented, so the Truth Layer's `integrity.partial` flag cannot be populated with full accuracy from the current engine.
- No correlation ID links a retry-1/retry-2/fallback event triple in `self_diagnosis.py` -- documented and accepted limitation, still open.

---

## 6. Suggested Implementation Order (recommendation only -- nothing started)

1. Resolve the Human Model duplication -- decide which is canonical, retire the other. Low risk, immediate clarity gain.
2. Make an explicit decision on the Level-A pipeline's fate: either wire `companionship_layer.py` into `verified_expression.py`'s Passive path behind Shadow Mode (per the pipeline's own migration plan, stage 5 of 7), or formally mark it parked/inactive-by-design in `CONSTITUTION.md` so no future session assumes it is live.
3. Surface `self_diagnosis.py` output somewhere (even a minimal read-only tool) so the telemetry investment isn't wasted.
4. Extend the Loans-proven Event Store + Command API pattern to Expenses next, per the sequencing already agreed in `AUDIT_REPORT_STAGE0.md` §5 (Loans -> Expenses -> Projects -> Memory).
5. Close the 4 raw-Firestore-bypass tools and add a confirmation step to the no-confirm delete tools -- a data-integrity fix independent of any new architecture.
6. Only after 1-5: begin the Phase-1 "runtime activation layer" work, scoped precisely by the Traceability Matrix (see `ARCHITECTURE_TRACEABILITY_MATRIX.md`).

**No code has been modified in this audit. Awaiting review before any further step.**

# Architecture Traceability Matrix — Phase 1
Date: 2026-07-27
Status: **Analysis / documentation only. Zero code changes made.**
Scope: every accepted architecture document in the repo root, plus the code modules they describe. Classification is ACTIVE / PARTIALLY ACTIVE / INACTIVE, verified by `grep` of the actual import graph and by reading the live dispatch tables (`claude_service.py` TOOLS + `_execute_tool`, `main.py` scheduler + handlers) -- not by re-reading the documents' own claims at face value.

---

## 1. Document-level matrix

| Document | Self-declared status | Owner | Loaded at runtime? | Used where | Runtime effect | Classification |
|---|---|---|---|---|---|---|
| `CONSTITUTION.md` | معتمد رسميًا (officially ratified), Rev. 2 | Ahmed | Never read by any `.py` file -- it is a human-readable governance reference | Cited by `EXPRESSIVE_VOICE_RECONSIDERATION_DRAFT.md`, `ARCHITECTURE_RECOVERY_INVENTORY.md` | Its Stage 6/7 principles (evidence-required self-state, Active=zero-LLM) are enforced in `expression_vocabulary.py` + `verified_expression.py` -- live. Its §4 principle ("unit of constraint is the Claim, not the response") governs the Level-A `claim_validator.py`/`companionship_layer.py`, which is built but disconnected. | **PARTIALLY ACTIVE** -- the slice it governs that shipped (Stage 6/7) is live; the slice it governs that's built-but-parked (Level A) is not. |
| `ARCHITECTURE_RECOVERY_INVENTORY.md` | جرد وفحص فقط (inventory only) | this-session-2026-07-24 | No | Historical snapshot, referenced by later docs | None -- point-in-time audit | **INACTIVE** (by design -- an audit record, not runtime architecture). One factual claim (claim_validator.py/companionship_layer.py missing) is now stale -- both were built the same day, later. |
| `AUDIT_REPORT_STAGE0.md` | pre-Stage-1 audit | same | No | Historical, cited by `EVENT_SCHEMA.md` | None directly, but its unresolved findings (raw-Firestore-bypass tools, no-confirm deletes, dead `command_handler.py`) are all **still true today**, re-verified in this audit | **INACTIVE** as a document; its findings remain live, unaddressed risks. |
| `CHECKPOINT_2026-07-24.md` | fact-checked snapshot | same | No | Historical | None -- superseded by 6 later commits (verified via `git log`) | **INACTIVE** (superseded). |
| `EVENT_SCHEMA.md` | منفّذ (implemented) | Stage 1 | No (doc itself not read at runtime) | Describes `services/event_store.py`, which is imported by `loan_commands.py`, `loan_conflict_observer.py`, `self_state_engine.py`, `self_diagnosis.py`, `verified_expression.py` (confirmed by grep) | Real: every loan write and self-diagnosis observation goes through this Event Store into Firestore `adam_events` | **ACTIVE** |
| `LOAN_COMMAND_API_STAGE2.md` | منفّذ ومتحقق منه | Stage 2 | No | Describes `services/loan_commands.py`, whose 3 tools (`loan_record_installment`, `loan_update_installment`, `loan_resolve_conflict`) are confirmed present verbatim in `claude_service.py`'s live system prompt | Real: the only path by which loan payment state changes | **ACTIVE** |
| `LOAN_CONFLICT_OBSERVER_STAGE3.md` | منفّذ ومتحقق منه | Stage 3 | No | `services/loan_conflict_observer.py`, imports `event_store` (confirmed), called from `loan_commands._commit()` per Stage 4 doc | Real: classifies every loan write as new/duplicate/update/conflict | **ACTIVE** |
| `CONFLICT_RESOLUTION_FLOW_STAGE4.md` | منفّذ ومتحقق منه | Stage 4 | No | The proactive-rejection rule inside `loan_record_installment` + the exact system-prompt paragraph confirmed present at `claude_service.py` (the "⚠️ تعارض" rule) | Real: blocks conflicting loan writes and forces the model to surface the conflict to Ahmed | **ACTIVE** |
| `SELF_STATE_ENGINE_STAGE5.md` + `_DRAFT.md` | منفّذ ومتحقق منه | Stage 5 | No | `services/self_state_engine.py`, imported by `verified_expression.py`, `main.py::self_state_active_check_job`, indirectly by `self_diagnosis.py` | Real: computes the 3 live self-state dimensions on every Passive/Active check | **ACTIVE** |
| `VERIFIED_EXPRESSION_STAGE6_7.md` + `_DRAFT.md` | منفّذ ومتحقق منه، قرارات مقفولة نهائيًا | Stage 6/7 | No | `services/verified_expression.py` + `expression_vocabulary.py`, wired into `main.py` (11 confirmed call sites) and `claude_service.py` (`request_verified_expression` tool, confirmed at dispatch) | Real: this **is** the live production self-expression mechanism today | **ACTIVE** |
| `TRUTH_LAYER_PHASE1.md` | منفّذة، Tests First | this-session | No | `services/truth_layer.py` -- grep confirms **zero non-test importers**, not even `companionship_layer.py` | None in production | **INACTIVE** |
| `MEANING_LAYER_PHASE1.md` | منفّذة، Tests First | this-session | No | `services/meaning_layer.py` -- same, **zero non-test importers** | None in production | **INACTIVE** |
| `TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE.md` (v1) | design only, superseded by v2 | this-session | No | Historical design doc | None -- explicitly superseded | **INACTIVE** (by its own declaration) |
| `TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE_V2.md` | تعديل جوهري، لسه مفيش كود (at time of writing) | this-session | No | Its decisions (Slot-Based Rendering, LLM-free Meaning Layer, Confidence, `CONSTITUTION.md` itself) **were** subsequently implemented in `renderer.py`, `meaning_layer.py`, `claim_validator.py`, `companionship_layer.py` | The code artifacts exist and pass their own tests, fulfilling the design -- but the resulting pipeline is not reachable from any live request path | **PARTIALLY ACTIVE** (implemented-but-disconnected) |
| `EXPRESSIVE_VOICE_RECONSIDERATION_DRAFT.md` (v3) | Level A منفّذ، Decision Gate ساري | this-session | No | Governs whether Level A or Level B should be built; its Decision Gate (§6.2) requires "Level A running in real use" before Level B is even discussed | Level A's code exists (per V2 row above) but has **never run against a real request**, so the Decision Gate's own precondition cannot yet be evaluated | **PARTIALLY ACTIVE** -- same disconnected-but-built status one level up the decision chain |
| `ADAM_PERSONAL_EXECUTIVE_SYSTEM_PLAN.md` | Draft, living roadmap | Ahmed / this-session | No (a vision/roadmap doc) | See §2 below for a section-by-section breakdown -- this is the newest and broadest document, and by far the least delivered | Mixed -- see §2 | **PARTIALLY ACTIVE**, trending INACTIVE for most of its scope |

---

## 2. `ADAM_PERSONAL_EXECUTIVE_SYSTEM_PLAN.md` — section-by-section breakdown

This document is the newest (2026-07-26) and broadest "accepted" document, and the mission's Phase 2 (Self State) and Phase 1's activation-layer work should be scoped against it directly. It is not a single artifact to classify wholesale -- its sections are at wildly different maturity levels:

| Section | Vision | Current reality | Classification |
|---|---|---|---|
| §1 Token Optimization fix review | Restore history to 50/15, remove blind 800/400-char cuts, keep `LearningDecision` | Confirmed **actually applied**: `executive_brain.py` uses `limit=50` / `limit=15`; two-tier `LearningDecision` (fast filter + Haiku) present with the exact decision-signal word list requested | **ACTIVE** |
| §4D Decision Ledger | Structured, queryable decision records | `save_decision`/`get_decisions` in `firebase_service.py`, wired as `save_decision`/`list_decisions` tools, documented in the system prompt with explicit trigger rules | **ACTIVE** |
| §4A Human Model | Single, rich, continuously-learned model of Ahmed | Two disconnected implementations (see Phase 0 audit); the live one (Firestore tool) is pull-only, not part of automatic context | **PARTIALLY ACTIVE** |
| §4B Business Memory | Bahr Designs identity/services/pricing/QA/suppliers as structured memory | No such structure; only ad hoc `get_bahr_projects`/`get_bahr_sites` tools, pre-dating this plan | **INACTIVE** |
| §4C Project Memory | Full per-project ledger: budget, BOQ, payments, procurement, team, risks, decisions | Only basic CRUD tools (`create_project`, `update_project_details`, `get_project_details`) -- far short of the vision | **INACTIVE** |
| §4E Conversation History | Continuity source, not sole memory | Present (`get_conversation_history`, limit 50) | **ACTIVE** (as a component; the "not sole source" framing is aspirational since it's currently the dominant context source) |
| §4F Working Memory | Ephemeral per-request scratch state | No dedicated implementation found | **INACTIVE** |
| §5 Context Engine (9-item Context Package, "context by relevance not length") | Structured, relevance-ranked context assembly | `executive_brain._stage_context` builds only `{timestamp, intent, history, memory}` -- 2 of 9 listed items, always the same regardless of relevance | **INACTIVE** |
| §6 Executive Brain 10-stage pipeline | Intake→Resolve Context→Understand→Assess Risk→Plan→Execute→Verify→Record→Learn→Respond | Current `executive_brain.py` has 7 stages; no explicit Risk Assessment; "Validate" is a non-empty-string check, not real Verify/Record | **PARTIALLY ACTIVE** |
| §7 Capabilities Registry + Phonebook | Structured capability contracts (inputs/outputs/preconditions/verification/failure/fallback/permissions/risk) | Tools are defined ad hoc in `claude_service.py`'s `TOOLS` list with no such structured contract | **INACTIVE** |
| §8 Work Graph | Rich relationship graph (Ahmed→Bahr→Projects→...) answering compound queries | Only the generic, pre-existing `bahr_graph_nodes` tool -- much shallower | **INACTIVE** |
| §9 Specialized Agents | Sub-agents (Site, Commercial, Design, Procurement, Client, Marketing, Personal Assistant) coordinated by ADAM | None exist; everything routes through one `ask_claude_agentic` call | **INACTIVE** |
| §10 Verification System (Requested→Planned→Executed→Verified→Recorded) | Every action confirmed against re-read state | Only the Stage-5 non-empty check exists; no re-read-and-compare verification anywhere | **INACTIVE** |
| §11 Initiative Engine | Morning Brief, Site Risk Alerts, Before-Meeting Brief, End-of-Day Review | Morning Brief **exists and runs daily**; Loan alerts and Self-State Active alerts exist; Site Risk Alerts / Before-Meeting Brief / End-of-Day Review do **not** exist | **PARTIALLY ACTIVE** |
| §15 Roadmap Phase 0-6 | 7-phase build-out | Phase 0 (this review) done; Phase 1 (Memory Architecture) has shipped exactly one of ~6 pieces (Decision Ledger); Phases 2-6 not started | **PARTIALLY ACTIVE** (Phase 0-1 only) |

---

## 3. Code-module traceability (supplementary — the concrete "what runs" layer)

| Module | Implements | Imported by (production) | Classification |
|---|---|---|---|
| `services/event_store.py` | `EVENT_SCHEMA.md` | `loan_commands`, `loan_conflict_observer`, `self_state_engine`, `self_diagnosis`, `verified_expression` | **ACTIVE** |
| `services/loan_commands.py` | `LOAN_COMMAND_API_STAGE2.md`, `CONFLICT_RESOLUTION_FLOW_STAGE4.md` | `claude_service` (tool dispatch) | **ACTIVE** |
| `services/loan_conflict_observer.py` | `LOAN_CONFLICT_OBSERVER_STAGE3.md` | `loan_commands` | **ACTIVE** |
| `services/self_state_engine.py` | `SELF_STATE_ENGINE_STAGE5.md` | `verified_expression`, `main.py` (hourly job) | **ACTIVE** |
| `services/decision_engine.py` | `SELF_STATE_ENGINE_STAGE5.md` §Decision Engine | `main.py` (hourly job) | **ACTIVE** |
| `services/expression_vocabulary.py` | `VERIFIED_EXPRESSION_STAGE6_7.md` | `verified_expression` | **ACTIVE** |
| `services/verified_expression.py` | `VERIFIED_EXPRESSION_STAGE6_7.md` | `main.py` (11 sites), `claude_service` (tool) | **ACTIVE** |
| `services/truth_layer.py` | `TRUTH_LAYER_PHASE1.md`, `..._V2.md` | *(none outside tests)* | **INACTIVE** |
| `services/meaning_layer.py` | `MEANING_LAYER_PHASE1.md`, `..._V2.md` | *(none outside tests)* | **INACTIVE** |
| `services/renderer.py` | `..._V2.md` §3 | `claim_validator` only | **INACTIVE** (reachable only through another inactive module) |
| `services/claim_validator.py` | `EXPRESSIVE_VOICE_RECONSIDERATION_DRAFT.md` Level A | `companionship_layer` only | **INACTIVE** (same reason) |
| `services/companionship_layer.py` | `EXPRESSIVE_VOICE_RECONSIDERATION_DRAFT.md` Level A | *(none outside tests)* | **INACTIVE** |
| `services/inference_rules.py` | `..._V2.md` §4 | *(none found outside tests)* | **INACTIVE** |
| `services/self_diagnosis.py` | (its own docstring, Architecture v2 extension) | event-writers: `verified_expression`, `companionship_layer`; **readers: none** | **INACTIVE** (write-only telemetry, never consumed) |
| `adam_human_model.py` | `ADAM_PERSONAL_EXECUTIVE_SYSTEM_PLAN.md` §4A (partially) | `main.py` (name-only) | **PARTIALLY ACTIVE** (present, barely used, disconnected from context) |
| `firebase_service.get_human_model/update_human_model` | `ADAM_PERSONAL_EXECUTIVE_SYSTEM_PLAN.md` §4A (the real one) | `claude_service` (tools) | **ACTIVE** |
| `firebase_service.save_decision/get_decisions` | `ADAM_PERSONAL_EXECUTIVE_SYSTEM_PLAN.md` §4D | `claude_service` (tools) | **ACTIVE** |
| `handlers/command_handler.py` | none (orphaned) | *(none -- imports nonexistent `services.task_service`)* | **INACTIVE / DEAD** |

---

## 4. Why the inactive documents/modules are inactive — summary reasons

1. **Never wired at the integration point that matters.** `truth_layer.py` / `meaning_layer.py` / `companionship_layer.py` / `claim_validator.py` / `inference_rules.py` were each built with Tests-First rigor and pass their own suites, but the one file that would need to call them (`verified_expression.py`, the actual production gate) never was updated to do so. This is not an oversight visible in the code -- the docs themselves (`ARCHITECTURE_RECOVERY_INVENTORY.md`, `EXPRESSIVE_VOICE_RECONSIDERATION_DRAFT.md` §2) say so explicitly, and this audit re-confirmed it still holds after 6 subsequent commits.
2. **Superseded by a later revision.** `TRUTH_MEANING_COMPANIONSHIP_ARCHITECTURE.md` (v1) was explicitly replaced by v2 before any code existed.
3. **Point-in-time snapshots, not living architecture.** `ARCHITECTURE_RECOVERY_INVENTORY.md`, `AUDIT_REPORT_STAGE0.md`, `CHECKPOINT_2026-07-24.md` are audit records by design -- they were never meant to be "loaded," and classifying them INACTIVE is not a defect, it's their intended nature. Their factual *findings*, however, remain live risks (tracked in the Phase 0 audit's Risks section) where unaddressed.
4. **Vision documented well ahead of implementation.** Most of `ADAM_PERSONAL_EXECUTIVE_SYSTEM_PLAN.md` (Context Engine, Capabilities Registry, Work Graph, Specialized Agents, Verification System) is a roadmap, honestly labeled "Draft," for work not yet started. This is expected and not a defect -- but it means most of the mission's Phase-2 "Self State" work has essentially no existing scaffolding to build on yet (no Capabilities Registry, no Context Engine, no Verification System), which materially affects Phase 2's implementation order.
5. **Write-only telemetry.** `self_diagnosis.py` is the one true "silent" case: it is wired for *input* (other modules write events into it) but has no output consumer anywhere. It is neither fully active nor a dead file -- it is architecture that observes but never informs a decision, which is arguably the most literal reading of "architecture with no runtime effect" in the whole repo.

---

## 5. What this means for the mission's "runtime activation layer" (not started — for review)

Per the mission, the next step after this matrix would be to design a Document Loader / Knowledge Registry / Policy Engine / Runtime Document Cache. Based on what's actually inactive above, that activation work has exactly **two concrete, bounded targets** in this codebase today (everything else in `ADAM_PERSONAL_EXECUTIVE_SYSTEM_PLAN.md` is greenfield, not "existing-but-disconnected"):

1. **Connect the Level-A pipeline** (`truth_layer` → `meaning_layer` → `companionship_layer` → `renderer` → `claim_validator`) into `verified_expression.py`'s Passive path -- the pipeline's own V1 doc (§8, migration plan) already specifies a safe Shadow Mode rollout for exactly this.
2. **Give `self_diagnosis.py` a reader** -- the smallest possible activation layer: one read-only tool or scheduled log line that surfaces `compute_fallback_count()` / `compute_validator_rejection_diagnosis()` somewhere a human can see them.

Everything else classified INACTIVE in §2 (Context Engine, Capabilities Registry, Work Graph, Specialized Agents, Verification System) is **new construction against a roadmap**, not "activation of dormant code" -- worth flagging because the mission's framing ("transform accepted architecture into executable behavior," "use existing code whenever possible") fits targets 1 and 2 far more precisely than it fits the rest of the Personal Executive System Plan, which would mostly be net-new implementation work.

**No code has been modified. Awaiting review before any implementation begins.**

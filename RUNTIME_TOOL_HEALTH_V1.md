# Runtime Capabilities & Tool Health V1
Date: 2026-07-27
Status: **Implemented, tested against live Firebase, verified end-to-end. Scheduler wired into the existing in-process APScheduler.**

---

## 1. Final Architecture

```
Observer                      Engine                         ADAM
--------                      ------                         ----
tool_failure_observer.py  --> tool_failures_log          -->  tool_health_engine.py
  (real_use failures,          (Firestore)                     evaluate_all_tools()
   hooked at the shared                                        (24h, deterministic,
   _execute_tool except                                         5 states)
   boundary)
                                                                     |
tool_health_heartbeat.py  --> tool_health_checks          -->       |
  (hourly, safe_probes                                              v
   only, capabilities_                                       get_tool_health_warnings()
   registry-derived)                                          --> Self State Core
                                                                    (internal_warnings,
                                                                     category="runtime")
                                                                     |
                                                                     v
                                                          render_health_report()
                                                          --> register_pending_verification()
                                                          --> verify_and_finalize()
                                                          --> get_tools_health_status tool
                                                                     |
                                                                     v
                                                          tool_health_alerts.py
                                                          (state-transition aware,
                                                           dedup + cooldown, via
                                                           existing bot.send_message)
```

This extends the existing Self State / verified-expression architecture — it does not introduce a second verification or self-awareness mechanism. `render_health_report()`'s output is delivered exactly the way `render_report()` (Self State Core) and `expression_vocabulary` (Loans) already are: rendered deterministically → `register_pending_verification()` → `verify_and_finalize()` enforces verbatim delivery.

## 2. Registry: Ownership and Source of Truth

**`services/capabilities_registry.py`**. The tool-name list is derived **exclusively and programmatically** from `services.claude_service.TOOLS` — never a second, hand-maintained list. Per-tool safety metadata (domain, operation_type, criticality, `health_check_supported`, `safe_probe`, timeout, source owner) requires human judgment and is hand-curated in `_TOOL_METADATA`, but any real tool missing an entry gets a conservative default (`NOT_MONITORED`, `health_check_supported=False`) rather than disappearing or being guessed safe. `check_drift()` reports both directions of divergence (`missing_from_metadata`, `stale_in_metadata`); a test asserts it returns empty against the live tool set today (53 tools, zero drift).

### Registry schema (per tool)
`tool_name`, `domain`, `operation_type` (`read`/`write`/`delete`/`analysis`/`system`), `runtime_handler` (`claude_service._execute_tool` for all locally-dispatched tools; `anthropic_native_tool` for `web_search`, which bypasses local dispatch entirely), `availability`, `health_check_supported`, `safe_probe` (a direct reference to the real underlying read function — never a re-implementation), `criticality`, `timeout_ms`, `source_owner`.

## 3. Safe-Probe Policy

Exactly **11 of 53** tools are `health_check_supported=True` for V1 — all zero-argument, confirmed read-only by reading their actual dispatch code (not assumed): `list_graph_nodes`, `list_expenses`, `expense_summary`, `loan_overview`, `list_reminders`, `get_human_model`, `get_bahr_projects`, `get_bahr_sites`, `list_recurring_reminders`, `get_self_diagnosis_report`, `get_adam_self_state`. A test asserts structurally that no tool with `operation_type` in (`write`, `delete`) ever has `health_check_supported=True`.

Deliberately excluded from V1 (not a gap — a documented choice): tools requiring a parameter with no safe default (`get_project_details`, `get_graph_node_details`), tools requiring `chat_id` context (`get_upcoming_deadlines`, `list_memory_notes`), and `get_backup_status` (external GitHub API + secret token — deferred to keep V1 tight). All of these are simply `NOT_MONITORED` unless real-use failures are logged against them.

Each probe runs in its own thread with `thread.join(timeout_ms)` — the standard Python pattern for bounding a synchronous call. A genuinely hung probe leaves its thread running to completion in the background (Python cannot force-kill a thread); given every V1 probe is a simple Firestore read, this is a documented, accepted limitation, not expected to occur in practice.

## 4. Firestore Schemas

**`tool_health_checks`** (heartbeat results): `tool_name`, `checked_at`, `result` (`success`/`failure`/`timeout`), `latency_ms`, `error_type`, `sanitized_error_summary`, `probe_version`, `evidence_event_id` (points to a paired `Event Store` event, `entity_type="tool_health"`, `attribute="heartbeat_check"` — same dual-recording pattern as `StateSnapshot`+`Expression`).

**`tool_failures_log`** (real-use failures only): `tool_name`, `failed_at`, `execution_source` (always `"real_use"` in this collection), `error_type`, `sanitized_error_summary`, `latency_ms`, `chat_id_present` (boolean, not the actual chat_id), `evidence_event_id` (paired event, `attribute="real_use_failure"`).

**`tool_health_alert_state`** (one doc per tool): `last_status`, `last_cause`, `last_alerted_at`, `last_alert_kind` — written **only** when an alert actually sends (see §6). No raw payloads, no secrets, no full stack traces anywhere in any collection — `sanitize_error()` stores only `type(exc).__name__` and a message truncated to 200 characters.

## 5. Tool Health States and Exact V1 Thresholds

Conservative, explicit, non-adaptive (`services/tool_health_engine.py`), evaluated fresh over a rolling 24-hour window every time — nothing is cached or stored as a verdict:

| Constant | Value | Meaning |
|---|---|---|
| `MIN_SAMPLE_FOR_HEALTHY` | 3 | Need ≥3 successful heartbeat checks in 24h before `HEALTHY` |
| `DEGRADED_FAILURE_COUNT` | 3 | ≥3 total failures (heartbeat + real-use combined) in 24h → `DEGRADED` |
| `DEGRADED_REPEATED_CAUSE_COUNT` | 2 | Same `error_type` recurring ≥2 times → `DEGRADED`, even below the total-count threshold |

Classification order: `UNKNOWN` (no usable evidence — either zero heartbeat data yet, or fewer than 3 successes with zero failures) → `NOT_MONITORED` (no safe probe, zero real-use failures) → `DEGRADED` (repeated-cause or total-count rule) → `WATCH` (1-2 isolated failures) → `HEALTHY` (sufficient successful sample, zero failures). Critically: a tool with **no safe probe but real logged failures is never stuck at `NOT_MONITORED`** — real evidence always takes priority over the absence of a probe. Verified live: `loan_record_installment` (a real write tool, no probe) correctly reads `NOT_MONITORED` today; injecting a synthetic failure against a tool with the same unsupported profile correctly produces `WATCH`.

## 6. Alert Transitions and Cooldown

`services/tool_health_alerts.py`. Alerts fire only on: entering `DEGRADED` for the first time, the dominant failure cause changing while still `DEGRADED`, or recovering out of `DEGRADED`. **Never** on every heartbeat failure. `ALERT_COOLDOWN_MINUTES = 60` gates actual sends.

A real bug was found and fixed during testing: the original implementation updated `last_status`/`last_cause` even when an alert was *suppressed* by cooldown, which silently erased the pending "cause changed" signal — meaning once cooldown blocked an alert, the system would never notice the change even after cooldown expired. Fixed by only persisting alert state when an alert actually sends (or is attempted); a regression test (`test_alerting_dedup_cooldown_recovery`) locks this in.

## 7. Evidence Flow

Every recorded check or failure writes a real Event Store event (`entity_type="tool_health"`) alongside its structured Firestore record, linked by `evidence_event_id` — the same dual-recording discipline used everywhere else in this codebase. `tool_health_engine`'s classifications carry `evidence_event_ids` resolvable back to real events; nothing is asserted without a traceable source.

## 8. Verified-Expression Delivery

The new `get_tools_health_status` tool calls `render_health_report()` (deterministic text, zero LLM), registers it via the same `verified_expression.register_pending_verification()` used by Self State Core and Loans, and `verify_and_finalize()` enforces verbatim delivery — proven live: a deliberately paraphrased reply was corrected, the exact report text was force-included.

## 9. Self State Core Integration (and the deferred decision)

`self_state_core.compute_self_state_core()` now also calls `tool_health_engine.get_tool_health_warnings()`, best-effort, and merges any `WATCH`/`DEGRADED` tools into `internal_warnings` with `category="runtime"`. This is read entirely through the **existing** warnings→`current_mode` rule (unchanged) — no redesign of `compute_current_mode`.

**Deliberately not done:** Tool Health does **not** influence `health_status` or `confidence`. `health_status`'s accepted definition is expression-pipeline reliability specifically (fallback/rejection/mismatch); broadening it to general tool health would silently redefine an already-accepted field. This is an intentional, documented deferral, not an oversight — confirmed structurally in tests (`health_status_evidence_event_ids` never contains a `tool_health`-sourced event).

## 10. Intentionally Unsupported / Out of Scope

Per the milestone's own boundaries: no Capabilities Registry beyond this runtime-infrastructure scope, no Agent Contracts redesign, no Execution Tracker, no Task/Session/Goal/Focus/Progress model. Also deferred within Tool Health itself: `get_backup_status` and the 4 context-dependent read tools are `NOT_MONITORED` by choice (§3); a genuinely hung probe's background thread is not forcibly terminated (documented Python limitation).

## 11. Scheduler Deployment

No new infrastructure. The existing in-process APScheduler (`main.py`) already runs comparable hourly jobs (`self_state_active_check_job`); `tool_health_check_job` was added as one more `scheduler.add_job(..., 'interval', hours=1, ...)` entry, identical pattern. **No external deployment step is required** — it runs wherever `main.py` already runs.

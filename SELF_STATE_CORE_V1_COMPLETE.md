# Self State Core — Version 1 Complete
Date: 2026-07-27
Status: **Both approved semantic corrections implemented and verified. Self State Core V1 is complete.**

---

## What changed (both scoped to `services/self_state_core.py` only, as approved)

**Correction 1 — explicit evidence at the top level.** `compute_self_state_core()`'s returned dict now includes `health_status_evidence_event_ids`, `diagnosis_summary_evidence_event_ids`, `confidence_evidence_event_ids`, and `current_mode_evidence_event_ids` alongside each of those four fields. A small helper, `_union_evidence()`, collects and dedupes `evidence_event_ids` from a list of source dicts. `health_status`/`diagnosis_summary`'s evidence is the union of exactly the three self-diagnosis counters they're built from (fallback + rejection + mismatch) — nothing else, preserving the structural separation confirmed in the diagnostic review. `current_mode`/`confidence`'s evidence is that same set unioned with every `internal_warnings` entry's evidence, since both fields depend on the fuller picture.

**Correction 2 — explicit category on every warning.** Each `internal_warnings` entry now carries `"category": "domain"` (the three Loans dimensions, plus the "loans self-state unavailable" failure entry) or `"category": "runtime"` (the three self-diagnosis counters, plus the "self-diagnosis unavailable" failure entry). No wording, no threshold, and no existing field changed.

**Zero change to user-visible output**, verified directly, not assumed: `render_report()` was not touched, and a new test confirms neither `"category"` nor `"evidence_event_ids"` appears anywhere in its rendered text — the categorization and evidence exposure are internal/structural only.

## Verification performed

- Full test suite re-run (`test_self_state_core.py`, extended with new coverage): all four health states, the new `category` tagging (including both "unavailable" failure entries, which required a fix mid-way — my first version of that test incorrectly assumed array order rather than looking up by `source`, caught and corrected before reporting this complete), a structural proof that domain evidence (`"e1"`) can never appear in `health_status`/`diagnosis_summary`'s evidence union, and live confirmation that a real injected event's ID appears correctly in `health_status_evidence_event_ids`, `current_mode_evidence_event_ids`, and `confidence_evidence_event_ids` simultaneously.
- Full `import main` smoke test — clean.
- Post-cleanup confirmation — real production counts read back exactly as before (`fallback=0`, `mismatch=4`), no test residue.
- No threshold touched, no new fields beyond the two approved corrections, no Capabilities Registry or Execution Tracker work started.

**Self State Core Version 1 is complete. Stopping here — the next architectural milestone will be defined separately, as instructed.**

# adam-v1

## Design System
Always read DESIGN.md before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.

The full product concept (screens, journey, laws, review) lives in
`docs/DESIGN_STUDIO_CONCEPT_V1.md` — DESIGN.md is the visual contract,
the concept doc is the why behind it.

## State and plan
`docs/STATE_2026_08_10.md` — what is connected, what is not, and the
reasoning behind decisions the code cannot explain by itself.
`docs/PLAN_NEXT.md` — the remaining work in order, with what must not
be built. Read both before touching projects, estimates or quantities.

## Skills — bound to moments, not left to recall

`absence-is-not-evidence` is **mandatory before any of these**, and it
fires before the mistake, not after:

- saying "no data" / "not found" / "nothing recorded"
- treating an empty result (`[]`, `None`, zero rows) as an answer
- saying a test, guard or check "passes" or "works"
- saying anything is "fixed"

The rule it enforces: an empty result is not an answer until you have
shown the check could have come back full. Five separate layers broke
this on 2026-08-10 — an empty array that meant forbidden, a green
assertion that could never go red, a tool never called, a tool that
fetched ninety-five rows and printed the count, and a guard silenced by
the system's own activity.

`data-migration` before any migration script, any change to a write
path, or any wiring of a UI onto a new store.

`full-crud` before calling a storage layer or a screen finished. Every
stored thing gets create, read, update and delete — or a written reason
why not.

## gstack
Small daily work runs without it. Large features get `/autoplan` before
and `/qa` after, and `/cso` for anything that opens a surface to people
outside the office. Windows copies files rather than symlinking them, so
re-run `./setup` after any `git pull` inside the gstack folder.

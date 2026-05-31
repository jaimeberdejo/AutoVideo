---
seed: SEED-001
planted: 2026-05-31
planted_during: v2.0.0 milestone close
trigger_when: planning a milestone about slide visuals, image sources, or `auto`-mode slide content
status: planted
source_branch: feature/pexels-slides (commit f26d49d)
---

# SEED-001: Pexels image source for slides (optional, graceful fallback)

Generate slides with **Pexels stock images** as an optional per-slide visual
source, alongside the default SVG/code-only visuals. Working prototype exists,
preserved on branch `feature/pexels-slides` (built originally for the delivered
"FinFeed UB" video as an owner-authorized exception):
- `src/avideo/integrations/pexels.py` — `resolve_slide_image(index, keyword, dir)`, caches to `workdir/images/`, returns empty data URI on no key / no network / no result (graceful degradation).
- `src/avideo/stages/slides_auto.py` — wires per-slide images via `slide_image_keywords.yaml`.
- `src/avideo/templates/base.html.j2` + `macros.html.j2` — render per-slide images.

## When to Surface
- Next milestone touching `auto`-mode slide content, visuals, or image sourcing.
- Any revisit of the "visuals" constraint.

## Why This Matters
The owner explicitly wants to keep this capability (2026-05-31). It currently
**contradicts a core project constraint** that must be updated when productized:

> PROJECT.md / CLAUDE.md — "Visuales: solo iconos SVG + gráficos por código; nada de imágenes IA ni stock" and Out of Scope: "Bancos de imágenes / stock."

## Productization checklist (do NOT just merge the branch)
1. Update the constraint: allow **optional** Pexels image source (default stays SVG/code; Pexels off unless a key + keywords provided; graceful fallback preserved). Network/API-key dependency is acceptable as opt-in (breaks the "100% offline" default only when explicitly enabled).
2. Re-apply the branch code onto current `master` (it was snapshotted off the pre-v2.0.0 base; `assemble.py`/templates have since changed — reconcile).
3. Add tests (mock the Pexels HTTP call; assert graceful fallback; cache behavior) + run code review.
4. Decide config surface: `PEXELS_API_KEY` in `.env`, a `visual_source: pexels|icons` knob, and the `slide_image_keywords.yaml` input.
5. Consider the Studio UI hook (a per-slide image toggle in Fase 3).

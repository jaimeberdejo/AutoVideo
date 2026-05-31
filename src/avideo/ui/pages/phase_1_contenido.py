"""avideo.ui.pages.phase_1_contenido — Phase 1: Contenido.

Real implementation of the Fase 1 wizard page.

Responsibilities:
- Collect the presentation topic (st.text_input) and target duration in
  seconds (st.number_input, bounded [15, 1800]).
- Let the user choose between writing bullets manually or having Claude
  generate them from the topic.
- Present an interactive st.data_editor (num_rows="dynamic") where bullets
  can be added, edited, and removed for both paths.
- On approval, persist workdir/bullets.yaml in the exact format that
  ``avideo generate --bullets`` consumes, write the "context" checkpoint, and
  set the "context" done-marker so the shell navigation gates correctly.
- Update ``st.session_state["run_config"]`` with the confirmed topic and
  duration so downstream phases can access them.
"""
from __future__ import annotations

import streamlit as st
import yaml

from avideo.models.bullets import BulletsInput
from avideo.stages.bullets_gen import (
    DURATION_MAX,
    DURATION_MIN,
    format_duration,
    generate_bullets,
    parse_duration,
    validate_duration,
)
from avideo.utils.workdir import WorkdirManager


def clean_bullet_rows(rows: list[dict]) -> list[str]:
    """Extract non-empty, stripped bullet strings from st.data_editor rows.

    st.data_editor with ``num_rows="dynamic"`` yields rows whose ``"bullet"``
    value is ``None`` (not ``""``) for blank or never-edited cells, so a plain
    ``row.get("bullet", "")`` returns ``None`` (the key exists) and ``.strip()``
    raises ``AttributeError``. This helper is null-safe via ``or ""``.

    Args:
        rows: The list of row dicts returned by ``st.data_editor``.

    Returns:
        Ordered list of non-empty, stripped bullet strings.
    """
    return [
        (r.get("bullet") or "").strip()
        for r in rows
        if (r.get("bullet") or "").strip()
    ]


def render(workdir: WorkdirManager) -> bool:
    """Render Phase 1 (Contenido) body.

    Args:
        workdir: Active WorkdirManager for the current run.

    Returns:
        True when the phase gate condition is met (bullets.yaml written and
        "context" done-marker is present).
    """
    st.subheader("Fase 1 — Contenido")
    st.caption("Define el tema, duración y los bullets de tu presentación.")

    # -----------------------------------------------------------------------
    # SECTION 1 — Topic + Duration inputs
    # -----------------------------------------------------------------------
    col1, col2 = st.columns([3, 1])

    with col1:
        topic: str = st.text_input(
            "Tema de la presentación",
            key="cnt_topic",
            placeholder="p. ej. Introducción a la inteligencia artificial",
        )

    with col2:
        duration_text: str = st.text_input(
            "Duración objetivo (mm:ss o segundos)",
            key="cnt_duration",
            value="2:00",
            placeholder="p. ej. 5:30",
            help=(
                f"Acepta mm:ss (p. ej. 5:30) o segundos. "
                f"Entre {format_duration(DURATION_MIN)} y {format_duration(DURATION_MAX)}."
            ),
        )

    # Parse mm:ss / seconds, then enforce the [DURATION_MIN, DURATION_MAX] bounds
    # (T-10-03-04 safety net). Either failure shows a clear error and locks the gate.
    try:
        duration_s: int = parse_duration(duration_text)
        validate_duration(duration_s)
    except ValueError as exc:
        st.error(f"Duración inválida: {exc}")
        return False

    st.caption(f"Duración: {format_duration(duration_s)} ({duration_s} s)")

    # -----------------------------------------------------------------------
    # SECTION 2 — Source choice (CNT-02)
    # -----------------------------------------------------------------------
    source: str = st.radio(
        "¿Cómo quieres crear los bullets?",
        options=["Escribir mis bullets", "Generar desde el tema (Claude)"],
        key="cnt_source",
        horizontal=True,
    )

    # -----------------------------------------------------------------------
    # SECTION 3 — Auto-generate path: spinner + session_state cache
    # -----------------------------------------------------------------------
    if source == "Generar desde el tema (Claude)":
        if st.button(
            "Generar bullets",
            key="cnt_gen_btn",
            disabled=not bool(topic.strip()),
        ):
            if not topic.strip():
                st.warning("Escribe un tema antes de generar.")
            else:
                with st.spinner("Generando bullets con Claude..."):
                    try:
                        bullets_raw = generate_bullets(
                            topic.strip(), duration_s
                        )
                        st.session_state["cnt_generated_bullets"] = bullets_raw
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Error al generar bullets: {exc}")

    # -----------------------------------------------------------------------
    # SECTION 4 — Editor (CNT-03): both paths use st.data_editor
    # -----------------------------------------------------------------------
    # st.data_editor owns its row state via its `key`. The base `data` MUST stay
    # stable across reruns: rebuilding it every run made a freshly-added "+" row
    # vanish on the next rerun (the empty row was filtered out of the base before
    # the rerun re-rendered the editor). We therefore seed the base only when the
    # underlying content actually changes — a source switch, or a NEW set of
    # Claude-generated bullets. The signature deliberately EXCLUDES manual content
    # so typing / adding rows in manual mode never reseeds (no disappearing rows,
    # no duplicate rows).
    gen_bullets: list[str] = st.session_state.get("cnt_generated_bullets") or []
    seed_sig = (source, tuple(gen_bullets))
    if st.session_state.get("cnt_editor_sig") != seed_sig:
        if source == "Generar desde el tema (Claude)":
            seed = [{"bullet": b} for b in gen_bullets]
        else:
            prev = st.session_state.get("cnt_manual_bullets") or []
            seed = [{"bullet": b} for b in prev]
        st.session_state["cnt_editor_rows"] = seed or [{"bullet": ""}]
        st.session_state["cnt_editor_sig"] = seed_sig

    edited = st.data_editor(
        st.session_state["cnt_editor_rows"],
        num_rows="dynamic",
        column_config={
            "bullet": st.column_config.TextColumn("Bullet", width="large")
        },
        use_container_width=True,
        key="cnt_bullets_editor",
    )

    # Persist manual bullets for cross-source / navigation recall. This does NOT
    # reseed the editor within the same source (seed_sig ignores manual content),
    # so added/edited rows survive reruns via the widget key.
    if source == "Escribir mis bullets":
        st.session_state["cnt_manual_bullets"] = clean_bullet_rows(edited)

    approved_bullets: list[str] = clean_bullet_rows(edited)

    # -----------------------------------------------------------------------
    # SECTION 5 — Gate + Aprobar button (CNT-01 / CNT-03)
    # -----------------------------------------------------------------------
    gate_met = False
    can_approve = bool(topic.strip()) and len(approved_bullets) >= 1

    if not topic.strip():
        st.info("Escribe un tema para continuar.")
    elif len(approved_bullets) < 1:
        st.info("Añade al menos un bullet para continuar.")
    else:
        st.caption(f"{len(approved_bullets)} bullet(s) listos para aprobar.")

        if st.button(
            "Aprobar bullets y continuar",
            key="cnt_approve_btn",
            type="primary",
            disabled=not can_approve,
        ):
            # Build model and write workdir/bullets.yaml in the exact format
            # that `avideo generate --bullets` consumes (yaml.safe_dump of
            # BulletsInput.model_dump() — see src/avideo/utils/bullets.py).
            bi = BulletsInput(title=topic.strip(), bullets=approved_bullets)
            bullets_yaml_path = workdir.root / "bullets.yaml"
            bullets_yaml_path.write_text(
                yaml.safe_dump(bi.model_dump(), allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

            # Write "context" checkpoint JSON and touch done-marker so the
            # shell navigation gates (PHASE_COMPLETION_STAGE[1] == "context").
            workdir.write_checkpoint("context", bi)
            workdir.mark_done("context")

            # Update session_state run_config for downstream phases.
            rc = st.session_state.get("run_config", {})
            rc["topic"] = topic.strip()
            rc["duration"] = duration_s
            st.session_state["run_config"] = rc

            gate_met = True
            st.success("Bullets aprobados. Puedes continuar al guion.")

    # Resume path: if context done-marker already exists (e.g. after browser
    # refresh), consider the gate met without requiring a new click.
    if workdir.is_done("context"):
        gate_met = True

    return gate_met

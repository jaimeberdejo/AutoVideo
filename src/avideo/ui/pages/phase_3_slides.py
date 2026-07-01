"""avideo.ui.pages.phase_3_slides — Phase 3: Diapositivas (SLD-01/02/03).

Wizard page for slide generation and quality verification.

Two modes (SLD-01):
- "Generar (auto)"  → SlidesDispatchStage + VerifyStage via bridge; PNG thumbnails
                      in a 3-column grid; ok/warning/fail badges from
                      VerificationReport; "Pedir variación" button.
- "Subir las mías" → st.file_uploader per slide; write_uploaded_slide to
                     workdir/slides_user/; VerifyStage via Claude Vision;
                     per-slide report + badges; re-upload/re-verify supported.

Approval gate: "Aprobar diapositivas" sets verify done-marker via bridge;
render() returns True only once verify is marked done.
"""
from __future__ import annotations

import streamlit as st

from avideo.utils.workdir import WorkdirManager


def render(workdir: WorkdirManager) -> bool:
    """Render Phase 3 (Diapositivas) body.

    Implements SLD-01 (mode selection), SLD-02 (auto path), SLD-03 (upload path),
    and the approval gate.  Returns True when the verify done-marker is present,
    enabling the shell's "Aprobar y continuar →" button.

    Args:
        workdir: Active WorkdirManager for the current run.

    Returns:
        True if the approval gate is met (verify stage done).
    """
    # ------------------------------------------------------------------
    # Build RunConfig from session state (lazy import to keep imports clean)
    # ------------------------------------------------------------------
    from avideo.models.config import RunConfig, SlidesMode  # noqa: PLC0415

    rc_dict = dict(st.session_state.get("run_config", {}))
    if "bullets" not in rc_dict:
        rc_dict["bullets"] = workdir.root / "bullets.yaml"

    # ------------------------------------------------------------------
    # SLD-01: Mode selection (persisted in session_state)
    # ------------------------------------------------------------------
    if "sld_mode" not in st.session_state:
        st.session_state["sld_mode"] = "auto"

    mode_label = st.radio(
        "Modo de diapositivas",
        ["Generar (auto)", "Subir las mías"],
        key="sld_mode_radio",
        horizontal=True,
    )
    slides_mode_str = "auto" if mode_label == "Generar (auto)" else "manual"
    st.session_state["sld_mode"] = slides_mode_str

    # Persist mode into run_config so SlidesDispatchStage routes correctly
    rc_dict["slides_mode"] = slides_mode_str
    st.session_state["run_config"] = rc_dict

    # Build config object (may raise if bullets file missing — handled by Phase 1 gate)
    try:
        config = RunConfig(**rc_dict)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Error de configuración: {exc}")
        return False

    # ------------------------------------------------------------------
    # Route to the correct path
    # ------------------------------------------------------------------
    if slides_mode_str == "auto":
        return _render_auto(workdir, config)
    else:
        return _render_upload(workdir, config)


# ---------------------------------------------------------------------------
# SLD-02: Auto path
# ---------------------------------------------------------------------------


def _render_auto(workdir: WorkdirManager, config: object) -> bool:
    """Render the auto-generation path (SLD-02).

    Launches SlidesDispatchStage + VerifyStage via bridge.  Polls progress
    with @st.fragment.  Shows PNG thumbnails in a 3-column grid with
    ok/warning/fail badges once both stages complete.

    Args:
        workdir: Active WorkdirManager.
        config:  Fully-built RunConfig (slides_mode == "auto").

    Returns:
        True once verify is done and user has clicked "Aprobar".
    """
    from avideo.stages.slides_dispatch import SlidesDispatchStage  # noqa: PLC0415
    from avideo.stages.verify_slides import VerifyStage  # noqa: PLC0415
    from avideo.ui.bridge import RunStatus, run_stage, stage_status  # noqa: PLC0415

    slides_done = workdir.is_done("slides")
    verify_done = workdir.is_done("verify")

    # Launch slides generation if not yet started/done
    if not slides_done:
        run_stage(SlidesDispatchStage(), workdir, config)

    # Launch verify as soon as slides are done
    if slides_done and not verify_done:
        run_stage(VerifyStage(), workdir, config)

    # If pipeline still running, poll with a fragment
    if not verify_done:

        @st.fragment(run_every="2s")
        def _poll_slides_auto() -> None:
            from avideo.ui.bridge import RunStatus, get_error, stage_status  # noqa: PLC0415

            s_slides = stage_status("slides", workdir)
            s_verify = stage_status("verify", workdir)

            if s_slides == RunStatus.ERROR:
                st.error(f"Error generando slides: {get_error('slides')}")
                return
            if s_verify == RunStatus.ERROR:
                st.error(f"Error verificando: {get_error('verify')}")
                return

            if s_verify == RunStatus.DONE:
                st.rerun()  # full rerun → show thumbnail grid below
                return

            if s_slides != RunStatus.DONE:
                st.info("Generando diapositivas...")
            else:
                st.info("Verificando calidad...")

            # Advance the chain: if no stage is running, the previous one
            # finished and the next pending stage must be launched by a FULL
            # page rerun (the main render body launches slides → verify in turn).
            running = s_slides == RunStatus.RUNNING or s_verify == RunStatus.RUNNING
            if not running:
                st.rerun()

        _poll_slides_auto()
        return False

    # ------------------------------------------------------------------
    # Both stages done — show thumbnail grid with badges
    # ------------------------------------------------------------------
    from avideo.models.slides import SlidesOutput  # noqa: PLC0415
    from avideo.models.verification import VerificationReport  # noqa: PLC0415
    from avideo.ui.pipeline_ops import badge_for_verdict  # noqa: PLC0415

    slides_out: SlidesOutput = workdir.read_checkpoint("slides", SlidesOutput)
    report: VerificationReport = workdir.read_checkpoint("verification", VerificationReport)
    verdict_by_idx = {v.slide_index: v for v in report.slides}

    st.subheader("Diapositivas generadas")
    cols_per_row = 3
    png_paths = slides_out.png_paths
    for row_start in range(0, len(png_paths), cols_per_row):
        cols = st.columns(cols_per_row)
        for col_i, png_path in enumerate(png_paths[row_start : row_start + cols_per_row]):
            slide_idx = row_start + col_i
            verdict = verdict_by_idx.get(slide_idx)
            badge = badge_for_verdict(verdict) if verdict else "○"
            with cols[col_i]:
                st.image(
                    png_path,
                    caption=f"Slide {slide_idx + 1} {badge}",
                    use_container_width=True,
                )
                if verdict and verdict.status != "ok":
                    with st.expander(f"Detalles QC slide {slide_idx + 1}"):
                        for issue in verdict.issues:
                            st.write(f"• {issue}")
                        for sug in verdict.suggestions:
                            st.write(f"→ {sug}")

    # ------------------------------------------------------------------
    # SLD-02: Variation widget (SEED-002 — steerable variation)
    # ------------------------------------------------------------------
    st.markdown("**Pedir variación de diapositivas (estilo visual / colores)**")
    slides_variation_text = st.text_area(
        "Instrucción (opcional)",
        key="sld_variation_text",
        placeholder='Ej: "esquema de color azul" / "más contraste en los títulos"',
        height=80,
    )
    if st.button("Aplicar variación", key="btn_slides_variation"):
        from avideo.ui.pipeline_ops import rerun_with_feedback  # noqa: PLC0415

        rerun_with_feedback(workdir, config, "slides", slides_variation_text.strip())
        st.rerun()

    # ------------------------------------------------------------------
    # Approval gate
    # ------------------------------------------------------------------
    return _approval_gate(workdir)


# ---------------------------------------------------------------------------
# SLD-03: Upload path
# ---------------------------------------------------------------------------


def _render_upload(workdir: WorkdirManager, config: object) -> bool:
    """Render the manual-upload path (SLD-03).

    Shows st.file_uploader per slide (indexed from storyboard).  Writes each
    upload to workdir/slides_user/ immediately via write_uploaded_slide.
    Once all slots are filled, enables "Verificar con Claude Vision" which
    runs SlidesDispatchStage (manual ingest) + VerifyStage.
    Shows per-slide verification report with badges and issues.

    Args:
        workdir: Active WorkdirManager.
        config:  Fully-built RunConfig (slides_mode == "manual").

    Returns:
        True once verify is done and user has clicked "Aprobar".
    """
    from avideo.models.storyboard import StoryboardOutput  # noqa: PLC0415
    from avideo.ui.pipeline_ops import write_uploaded_slide  # noqa: PLC0415

    # Read storyboard to determine expected slide count
    try:
        sb: StoryboardOutput = workdir.read_checkpoint("storyboard", StoryboardOutput)
        n_slides = len(sb.slides)
    except Exception as exc:  # noqa: BLE001
        st.warning(
            f"Storyboard no disponible aún ({exc}). "
            "Completa la Fase 1 (Contenido) antes de subir diapositivas."
        )
        return False

    # ------------------------------------------------------------------
    # Per-slide file uploaders
    # ------------------------------------------------------------------
    st.subheader("Subir diapositivas")
    all_uploaded = True

    for idx in range(n_slides):
        expected_name = f"slide_{idx:02d}.png"
        upload_path = workdir.root / "slides_user" / expected_name
        col_label, col_upload = st.columns([1, 3])

        with col_label:
            st.write(f"Slide {idx + 1}")

        with col_upload:
            uploaded = st.file_uploader(
                f"Subir slide {idx + 1} (PNG/PDF)",
                key=f"upload_{idx}",
                type=["png", "pdf"],
                label_visibility="collapsed",
            )
            if uploaded is not None:
                # Write immediately — Streamlit discards UploadedFile on next rerun
                try:
                    write_uploaded_slide(workdir, expected_name, uploaded.read())
                    st.success(f"Slide {idx + 1} subida.")
                except ValueError as exc:
                    st.error(f"Archivo rechazado: {exc}")
                    all_uploaded = False
            elif not upload_path.exists():
                all_uploaded = False
                st.info("Sin subir")
            else:
                st.success("Ya subida")
                st.image(str(upload_path), width=200)

    # ------------------------------------------------------------------
    # Verify button (only once all slides present)
    # ------------------------------------------------------------------
    verify_done = workdir.is_done("verify")
    slides_ingested = workdir.is_done("slides")

    if all_uploaded and not verify_done:
        # Trigger ingest+verify. Launch ONLY slides on the button; verify is
        # launched below once ingest is done (avoids the race where verify ran
        # on not-yet-ingested slides). The poll fragment advances the chain.
        if st.button("Verificar diapositivas (Claude Vision)", key="btn_verify"):
            from avideo.stages.slides_dispatch import SlidesDispatchStage  # noqa: PLC0415
            from avideo.ui.bridge import run_stage  # noqa: PLC0415

            # Force re-ingest of the uploaded slides + clear downstream markers.
            workdir.done_marker("slides").unlink(missing_ok=True)
            workdir.invalidate_downstream("slides")
            run_stage(SlidesDispatchStage(), workdir, config)
            st.rerun()

        # Once slides are ingested, launch verify (idempotent).
        if slides_ingested and not verify_done:
            from avideo.stages.verify_slides import VerifyStage  # noqa: PLC0415
            from avideo.ui.bridge import run_stage  # noqa: PLC0415

            run_stage(VerifyStage(), workdir, config)

        @st.fragment(run_every="2s")
        def _poll_slides_verify() -> None:
            from avideo.ui.bridge import RunStatus, get_error, stage_status  # noqa: PLC0415

            ss = stage_status("slides", workdir)
            sv = stage_status("verify", workdir)

            if ss == RunStatus.ERROR:
                st.error(f"Error ingiriendo slides: {get_error('slides')}")
                return
            if sv == RunStatus.ERROR:
                st.error(f"Error verificando: {get_error('verify')}")
                return
            if sv == RunStatus.DONE:
                st.rerun()  # full rerun → show verification report below
                return
            # Nothing launched yet (user hasn't clicked) — stay idle, no rerun.
            if ss == RunStatus.IDLE and sv == RunStatus.IDLE:
                return
            st.info("Verificando con Claude Vision...")
            # Advance: if no stage is running, the previous finished → full rerun
            # so the main body launches the next pending stage (slides → verify).
            running = ss == RunStatus.RUNNING or sv == RunStatus.RUNNING
            if not running:
                st.rerun()

        _poll_slides_verify()

    # ------------------------------------------------------------------
    # Show verification report if done
    # ------------------------------------------------------------------
    if verify_done:
        from avideo.models.verification import VerificationReport  # noqa: PLC0415
        from avideo.ui.pipeline_ops import badge_for_verdict  # noqa: PLC0415

        report: VerificationReport = workdir.read_checkpoint("verification", VerificationReport)
        verdict_by_idx = {v.slide_index: v for v in report.slides}

        st.subheader("Resultados de verificación")
        for idx in range(n_slides):
            upload_path = workdir.root / "slides_user" / f"slide_{idx:02d}.png"
            verdict = verdict_by_idx.get(idx)
            badge = badge_for_verdict(verdict) if verdict else "○"
            col_img, col_report = st.columns([1, 2])

            with col_img:
                if upload_path.exists():
                    st.image(
                        str(upload_path),
                        caption=f"Slide {idx + 1} {badge}",
                        width=200,
                    )

            with col_report:
                if verdict:
                    if verdict.status == "ok":
                        st.success(f"Slide {idx + 1}: OK")
                    elif verdict.status == "warning":
                        st.warning(f"Slide {idx + 1}: Advertencia")
                        for issue in verdict.issues:
                            st.write(f"• {issue}")
                    else:
                        st.error(f"Slide {idx + 1}: Problema")
                        for issue in verdict.issues:
                            st.write(f"• {issue}")
                        for sug in verdict.suggestions:
                            st.write(f"→ {sug}")

        # Re-upload / re-verify: show button to start over
        if st.button("Volver a subir / re-verificar", key="btn_reupload"):
            workdir.invalidate_downstream("slides")
            st.rerun()

    # ------------------------------------------------------------------
    # Approval gate
    # ------------------------------------------------------------------
    return _approval_gate(workdir)


# ---------------------------------------------------------------------------
# Shared approval gate
# ---------------------------------------------------------------------------


def _approval_gate(workdir: WorkdirManager) -> bool:
    """Render the approval gate and return whether it has been met.

    The gate returns True (enabling the shell footer) once verify is done.
    The button is disabled while verify is still pending.

    Args:
        workdir: Active WorkdirManager (used to check the verify done-marker).

    Returns:
        True if the verify done-marker is present.
    """
    verify_done = workdir.is_done("verify")

    st.divider()
    if st.button(
        "Aprobar diapositivas",
        key="btn_approve_slides",
        disabled=not verify_done,
        type="primary",
    ):
        st.success("Diapositivas aprobadas.")
        st.rerun()

    return verify_done

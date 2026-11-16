"""Streamlit dashboard.  Run with: make dashboard   (or: streamlit run app/dashboard.py)"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from app import style
from src import camera, inference, inventory, pipeline, report, stub_detector
from src.config import load_config

STATUS_COLOURS = {s: info[2] for s, info in report.STATUS_INFO.items()}
UPLOAD_TYPES = sorted(e.lstrip(".") for e in inference.IMAGE_EXTS | inference.VIDEO_EXTS)
METHOD_LABELS = {"image": "Single image", "track": "Video, tracked", "peak": "Video, peak frame", "stub": "Stub"}

st.set_page_config(page_title="StockVision", page_icon=":material/inventory_2:", layout="wide", initial_sidebar_state="auto")
st.markdown(style.CSS, unsafe_allow_html=True)
cfg = load_config()
inventory.ensure_db(cfg)
weights_ready = Path(cfg["model"]["weights"]).exists()


@st.cache_resource(show_spinner="Loading detection model...")
def get_model(weights_path: str, modified: float):
    """Cached across reruns; reloads when the weights file changes."""
    return inference.load_model(cfg)


def results_table(rows: list) -> pd.DataFrame:
    return pd.DataFrame([{
        "SKU": r["sku"],
        "Item": r["item_name"],
        "Location": r["location"],
        "Detected": r["detected"],
        "Recorded": r["recorded"],
        "Variance": r["variance"],
        "Variance %": r["variance_pct"],
        "Confidence": r["confidence"],
        "Status": report.status_label(r["status"]),
    } for r in rows])


def colour_status(rows: list):
    colours = [f"background-color: {STATUS_COLOURS[r['status']]}; color: black" for r in rows]
    return lambda column: colours if column.name == "Status" else [""] * len(column)


def close_device_camera():
    """Release the attached camera and go back to the closed state."""
    camera.close_stream()
    st.session_state["device_open"] = False
    st.rerun()


@st.fragment(run_every=0.4)
def device_preview():
    """Live preview of the attached camera. Only this part of the page refreshes, a few times a second."""
    stream = camera.current_stream()  # never opens the camera: that is the Open camera button's job
    try:
        if stream is None:
            raise camera.CameraError("The camera was closed.")
        frame = camera.shrink(stream.read())
    except camera.CameraError as error:
        if st.session_state.get("device_open"):  # e.g. switched off after the idle time
            st.session_state["device_open"] = False
            st.session_state["device_error"] = str(error)
            st.rerun()
        return
    st.image(frame, channels="BGR", output_format="JPEG")
    st.caption("Live preview. Press Take photo when the stock is in frame.")


# ---- sidebar: what the pipeline is configured to do ---------------------------
with st.sidebar:
    st.subheader("Configuration")
    st.caption("Edit config.yaml to change any of this.")
    st.write(f"**Project:** {cfg['project']['name']}")
    st.write(f"**Location:** {cfg['project'].get('location', '')}")
    with st.expander("Products in scope", expanded=True):
        for name, info in cfg["classes"].items():
            st.write(f"- {info['display_name']} ({info['sku']})")
    v = cfg["variance"]
    st.write(f"**Thresholds:** match ±{v['match_pct']}%, minor up to {v['minor_pct']}%")
    st.write(f"**Video counting:** {cfg['video']['mode']}")
    st.divider()
    if weights_ready:
        st.success(f"Model: {Path(cfg['model']['weights']).name}")
        use_stub = False
    else:
        st.error("No trained weights found. Put best.pt in the weights/ folder.")
        use_stub = st.checkbox("Use stub detector (fake counts, for testing the pipeline)")

# ---- header -------------------------------------------------------------------
st.markdown(style.hero(
    "StockVision",
    "Photograph a shelf. Get a verified stock count in seconds.",
    [cfg["project"].get("location", "") or "Warehouse",
     "Model ready" if weights_ready else ("Stub mode" if use_stub else "No model"),
     f"{len(cfg['classes'])} products"]), unsafe_allow_html=True)

tab_verify, tab_history, tab_inventory = st.tabs(["Verify stock", "History", "Inventory"])

# ---- tab 1: capture -> identify -> count -> compare -> report -----------------
with tab_verify:
    if st.session_state.get("run") is None:
        st.markdown(style.steps(), unsafe_allow_html=True)

    device_label = camera.BACKEND_LABELS[camera.pick_backend(cfg)]
    src_device, src_upload, src_camera = st.tabs([device_label, "Upload photo or video", "Phone or browser camera"])
    with src_device:
        # The camera attached to the computer running StockVision (the Raspberry Pi camera on a Pi,
        # the webcam on a laptop), not the phone or browser that is showing this page.
        # Three states: a photo has been taken / the camera is open with a live preview / closed.
        if st.session_state.get("device_photo"):
            st.image(st.session_state["device_photo"])
            d1, d2 = st.columns(2)
            if d1.button("Retake photo", key="device_retake"):
                st.session_state["device_photo"] = None
                st.session_state["device_open"] = True
                st.rerun()
            if d2.button("Discard photo", key="device_discard"):
                st.session_state["device_photo"] = None
                st.rerun()
        elif st.session_state.get("device_open"):
            try:
                with st.spinner("Opening the camera..."):
                    stream = camera.get_stream(cfg)
            except camera.CameraError as error:
                st.session_state["device_open"] = False
                st.error(str(error))
            else:
                device_preview()
                d1, d2 = st.columns(2)
                if d1.button("Take photo", type="primary", key="device_take"):
                    try:
                        shot = stream.save_photo(Path(cfg["output"]["dir"]) / "captures")
                        st.session_state["device_photo"] = shot.read_bytes()
                    except camera.CameraError as error:
                        st.session_state["device_error"] = str(error)
                    close_device_camera()
                if d2.button("Close camera", key="device_close"):
                    close_device_camera()
        else:
            if st.session_state.get("device_error"):
                st.error(st.session_state.pop("device_error"))
            st.caption(f"Uses the {device_label.lower()} attached to the computer running StockVision. "
                       "Open it to see a live preview, then take the photo when the stock is in frame.")
            if st.button("Open camera", key="device_open_button"):
                st.session_state["device_open"] = True
                st.rerun()
    with src_upload:
        upload = st.file_uploader("Shelf photo or short video", type=UPLOAD_TYPES,
                                  label_visibility="collapsed")
    with src_camera:
        # The camera widget is only on the page while it is open. Streamlit renders every tab
        # at load, so a bare st.camera_input would start the webcam straight away; mounting it on
        # demand means the browser asks for permission on click and releases the camera afterwards.
        if st.session_state.get("camera_photo"):
            st.image(st.session_state["camera_photo"])
            if st.button("Retake photo"):
                st.session_state["camera_photo"] = None
                st.session_state["camera_open"] = True
                st.rerun()
        elif st.session_state.get("camera_open"):
            shot = st.camera_input("Point the camera at the shelf", label_visibility="collapsed")
            if shot is not None:  # keep the bytes, then unmount the widget so the camera turns off
                st.session_state["camera_photo"] = shot.getvalue()
                st.session_state["camera_open"] = False
                st.rerun()
            if st.button("Close camera"):
                st.session_state["camera_open"] = False
                st.rerun()
        else:
            st.caption("The camera only turns on when you open it, and off again when you are done.")
            if st.button("Open camera"):
                st.session_state["camera_open"] = True
                st.rerun()
    # one photo is verified: an uploaded file first, then the device camera, then the browser camera
    camera_bytes = st.session_state.get("device_photo") or st.session_state.get("camera_photo")
    can_run = (upload is not None or camera_bytes is not None) and (weights_ready or use_stub)

    if st.button("Run verification", type="primary", disabled=not can_run):
        upload_dir = Path(cfg["output"]["dir"]) / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        if upload is not None:  # an uploaded file takes priority over a camera photo
            source = upload_dir / upload.name
            source.write_bytes(upload.getbuffer())
        else:
            source = upload_dir / f"camera-{time.strftime('%Y%m%d-%H%M%S')}.jpg"
            source.write_bytes(camera_bytes)
        try:
            with st.spinner("Detecting and counting... video on CPU can take a minute"):
                if use_stub:
                    new_run = pipeline.run_verification(source, cfg, detector=stub_detector.detect)
                else:
                    weights = cfg["model"]["weights"]
                    model = get_model(weights, Path(weights).stat().st_mtime)
                    new_run = pipeline.run_verification(
                        source, cfg,
                        detector=lambda s, c, out: inference.detect(s, c, out, model=model))
            st.session_state["run"] = new_run
            st.session_state.pop("report", None)
        except Exception as error:  # show the message instead of a stack trace during a demo
            st.error(f"Verification failed: {error}")

    run = st.session_state.get("run")
    if run is None:
        st.markdown(style.empty("No results yet. Add a photo or video above, then press Run verification."),
                    unsafe_allow_html=True)
    else:
        if run["count_method"] == "stub":
            st.warning("Stub detector: these counts are fake.")
        summary = run["summary"]
        attention = len(run["rows"]) - summary["match"]
        ok, bad = style.STATUS_ACCENT["match"], style.STATUS_ACCENT["major"]

        st.subheader("Results")
        st.markdown(style.kpis([
            ("Items checked", len(run["rows"]), None),
            ("Verified", summary["match"], ok),
            ("Need attention", attention, bad if attention else ok),
            ("Total detected", sum(r["detected"] for r in run["rows"]), None),
        ]), unsafe_allow_html=True)

        if attention == 0:
            st.success("All items match the inventory records.")

        left, right = st.columns([3, 2], gap="large")
        with left:
            st.image(run["annotated_path"], caption=f"{run['source_name']}: detections")
            st.markdown(
                f'<div class="sv-meta"><b>Run</b> {run["run_id"]} · <b>Method</b> '
                f'{METHOD_LABELS[run["count_method"]]} ({run["frames_processed"]} frame(s))</div>',
                unsafe_allow_html=True)
        with right:
            st.markdown(style.item_cards(run["rows"], report.STATUS_INFO), unsafe_allow_html=True)

        with st.expander("Full results table"):
            st.dataframe(results_table(run["rows"]).style.apply(colour_status(run["rows"]))
                         .format(precision=1, na_rep="-"), hide_index=True)

        st.subheader("Discrepancy report")
        scope = st.radio("Include", ["This run", "All runs so far"], horizontal=True)
        if st.button("Generate report"):
            runs = [run] if scope == "This run" else pipeline.list_runs(cfg)
            md_path, pdf_path = report.write_report(runs, cfg)
            st.session_state["report"] = (str(md_path), str(pdf_path))
        if "report" in st.session_state:
            md_path, pdf_path = (Path(p) for p in st.session_state["report"])
            d1, d2 = st.columns(2)
            d1.download_button("PDF report", pdf_path.read_bytes(), pdf_path.name, "application/pdf")
            d2.download_button("Markdown report", md_path.read_bytes(), md_path.name, "text/markdown")

# ---- tab 2: every verification stored in the database -------------------------
with tab_history:
    history = inventory.get_history(cfg["inventory"]["database"])
    if not history:
        st.markdown(style.empty("No verification runs yet."), unsafe_allow_html=True)
    else:
        frame = pd.DataFrame(history)
        frame["status"] = frame["status"].map(report.status_label)
        st.dataframe(frame, hide_index=True)

# ---- tab 3: the recorded quantities being compared against --------------------
with tab_inventory:
    st.caption(f"Loaded from {Path(cfg['inventory']['source_csv']).name}. "
               "After editing the CSV, run `make init-db` and refresh.")
    records = inventory.get_records(cfg["inventory"]["database"])
    st.dataframe(pd.DataFrame(records.values()), hide_index=True)

"""Minimal Streamlit UI. Start the API first: uvicorn src.api:app --reload
Then: streamlit run frontend/app.py"""
import requests
import streamlit as st

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config

API = st.sidebar.text_input("API URL", "http://127.0.0.1:8000")
st.title("CareerLens")
tab_up, tab_q = st.tabs(["Upload & extract", "Ask questions"])

with tab_up:
    f = st.file_uploader("Resume, transcript or certificate", type=["pdf", "png", "jpg", "jpeg"])
    model = st.selectbox("Extraction model", ["prompted_vlm", "donut", "layoutlmv3"])
    if f and st.button("Upload and extract", type="primary"):
        r = requests.post(f"{API}/documents/upload", files={"file": (f.name, f.getvalue())})
        r.raise_for_status()
        meta = r.json()
        st.success(f"Stored as {meta['doc_id']} v{meta['version']}")
        with st.spinner("Extracting..."):
            e = requests.post(f"{API}/documents/{meta['doc_id']}/extract",
                              params={"version": meta["version"], "model": model})
        if e.ok:
            doc = e.json()
            st.session_state["last_doc"] = doc["doc_id"]
            st.caption(f"Detected type: {doc['document_type']}")
            low = [k for k, v in doc["fields"].items()
                   if isinstance(v, dict) and v.get("value") is not None
                   and v["confidence"] < config.CONFIDENCE_THRESHOLD]
            if low:
                st.warning(f"Low-confidence fields: {', '.join(low)}")
            st.json(doc)
            if doc["document_type"] == "resume":
                a = requests.post(f"{API}/analysis/ats", json={"doc_id": doc["doc_id"]})
                if a.ok:
                    st.metric("ATS score", a.json()["ats_score"])
                    st.write(a.json()["reasons"])
        else:
            st.error(e.text)

with tab_q:
    q = st.text_input("Question about your documents")
    if q and st.button("Ask"):
        r = requests.post(f"{API}/query", json={"question": q})
        if r.ok:
            st.write(r.json()["answer"])
            with st.expander("Sources"):
                for s in r.json()["sources"]:
                    st.write(f"**{s['doc_id']} v{s['version']}**: {s['text']}")
        else:
            st.error(r.text)

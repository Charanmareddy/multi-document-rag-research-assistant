"""Streamlit UI for collection management and evidence-grounded research."""

import streamlit as st
import re

from frontend.services.api import API_BASE_URL, download_report, get_collections, request, upload_pdfs, upload_zip

st.set_page_config(page_title="Research Assistant", page_icon="📚", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1450px;}
[data-testid="stSidebar"] {border-right: 1px solid rgba(120,130,150,.18);}
.hero {padding: 1.25rem 1.5rem; border-radius: 16px; background: linear-gradient(120deg,#172554,#1e3a8a 65%,#155e75); color:white; margin-bottom:1rem;}
.hero h1 {margin:0 0 .25rem 0; font-size:2rem;}
.muted {color:#64748b;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="hero"><h1>📚 Research Assistant</h1><div>Search across your document library and trace answers back to source pages.</div></div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Workspace")
    page = st.radio("Navigate", ["Dashboard", "Collections", "Research Assistant", "Comparison", "Reports", "Analytics", "Settings"], label_visibility="collapsed")
    st.caption(f"Backend: `{API_BASE_URL}`")
    if st.button("Check backend", use_container_width=True):
        try:
            health = request("GET", "/health")
            st.success(f"API {health['status']}")
        except RuntimeError as exc:
            st.error(str(exc))


def load_collections() -> list[dict] | None:
    try:
        return get_collections()
    except RuntimeError as exc:
        st.error(str(exc))
        return None


def collection_picker(collections: list[dict], key: str = "collection") -> dict | None:
    if not collections:
        st.info("Create a collection first to get started.")
        return None
    return st.selectbox("Collection", collections, format_func=lambda c: c["name"], key=key)


if page == "Dashboard":
    collections = load_collections()
    if collections is not None:
        documents = [doc for collection in collections for doc in collection.get("documents", [])]
        indexed = sum(doc.get("status") == "indexed" for doc in documents)
        failed = sum(doc.get("status") == "index_failed" for doc in documents)
        cols = st.columns(4)
        cols[0].metric("Collections", len(collections))
        cols[1].metric("Documents", len(documents))
        cols[2].metric("Indexed", indexed)
        cols[3].metric("Needs attention", failed)
        st.subheader("Recent documents")
        if documents:
            st.dataframe([{"Name": d["name"], "Status": d["status"], "Pages": d["page_count"],
                           "Chunks": d["chunk_count"]} for d in documents[:12]], use_container_width=True, hide_index=True)
        else:
            st.info("Create a collection and upload PDFs to begin.")
        try:
            activity = request("GET", "/analytics/overview")
            left, right = st.columns(2)
            with left:
                st.subheader("Recent research queries")
                for item in activity["recent_queries"]:
                    st.write(f"• {item['question']}")
            with right:
                st.subheader("Recent reports")
                for item in activity["recent_reports"]:
                    st.write(f"• {item['title']}")
        except RuntimeError as exc:
            st.caption(str(exc))

elif page == "Collections":
    collections = load_collections()
    left, right = st.columns([1, 2])
    with left:
        st.subheader("New collection")
        with st.form("create_collection"):
            name = st.text_input("Name", max_chars=200)
            description = st.text_area("Description", max_chars=1000)
            create = st.form_submit_button("Create collection", type="primary")
        if create:
            try:
                request("POST", "/collections", json={"name": name, "description": description or None})
                st.success("Collection created.")
                st.rerun()
            except RuntimeError as exc:
                st.error(str(exc))
    with right:
        st.subheader("Manage documents")
        if collections:
            selected = collection_picker(collections, "manage_collection")
            if selected:
                st.caption(selected.get("description") or "No description")
                docs = selected.get("documents", [])
                st.dataframe([{"Name": d["name"], "Status": d["status"], "Pages": d["page_count"],
                               "Chunks": d["chunk_count"], "Size": f"{d['file_size'] / 1024:.0f} KB"}
                              for d in docs], use_container_width=True, hide_index=True)
                tab_pdf, tab_zip = st.tabs(["Upload PDFs", "Upload ZIP"])
                with tab_pdf:
                    uploads = st.file_uploader("Select PDF files", type=["pdf"], accept_multiple_files=True, key="pdf_uploads")
                    if st.button("Upload PDFs", disabled=not uploads, key="upload_pdf_button"):
                        try:
                            result = upload_pdfs(selected["id"], uploads)
                            ok = sum("document" in item for item in result["results"])
                            st.success(f"Processed {ok} upload(s). Review any per-file errors below.")
                            for item in result["results"]:
                                if "error" in item:
                                    st.warning(f"{item['filename']}: {item['error']}")
                            st.rerun()
                        except RuntimeError as exc:
                            st.error(str(exc))
                with tab_zip:
                    archive = st.file_uploader("ZIP containing PDFs", type=["zip"], key="zip_upload")
                    if st.button("Upload ZIP", disabled=archive is None, key="upload_zip_button"):
                        try:
                            result = upload_zip(selected["id"], archive)
                            st.success(f"Reviewed {result.get('pdf_count', 0)} PDF file(s) in the archive.")
                            for item in result["results"]:
                                if "error" in item:
                                    st.warning(f"{item['filename']}: {item['error']}")
                            st.rerun()
                        except RuntimeError as exc:
                            st.error(str(exc))
                eligible = [d for d in docs if d["status"] in {"uploaded", "index_failed"}]
                if eligible:
                    if st.button(f"Index {len(eligible)} uploaded/failed document(s)", type="primary"):
                        try:
                            job = request("POST", "/indexing/start", json={"collection_id": selected["id"]})
                            st.session_state["indexing_job_id"] = job["job_id"]
                            st.success(f"Indexing job queued: {job['job_id']}")
                        except RuntimeError as exc:
                            st.error(str(exc))
                job_id = st.session_state.get("indexing_job_id")
                if job_id:
                    if st.button("Refresh indexing status"):
                        try:
                            job = request("GET", f"/indexing/status/{job_id}")
                            st.info(f"{job['status']}: {job['processed_documents']}/{job['total_documents']} processed; {job['failed_documents']} failed")
                            if job.get("error"):
                                st.error(job["error"])
                        except RuntimeError as exc:
                            st.error(str(exc))
                if docs:
                    remove_id = st.selectbox("Remove document", [None, *[d["id"] for d in docs]],
                                             format_func=lambda value: "Choose a document" if value is None else next(d["name"] for d in docs if d["id"] == value))
                    if st.button("Delete selected document", disabled=remove_id is None):
                        try:
                            request("DELETE", f"/documents/{remove_id}")
                            st.success("Document deleted.")
                            st.rerun()
                        except RuntimeError as exc:
                            st.error(str(exc))
                st.divider()
                confirm_delete = st.checkbox("I understand this deletes the collection and its source PDFs", key=f"confirm-{selected['id']}")
                if st.button("Delete collection", disabled=not confirm_delete, key=f"delete-collection-{selected['id']}"):
                    try:
                        request("DELETE", f"/collections/{selected['id']}")
                        st.session_state.pop("indexing_job_id", None)
                        st.success("Collection deleted.")
                        st.rerun()
                    except RuntimeError as exc:
                        st.error(str(exc))

elif page == "Research Assistant":
    collections = load_collections()
    if collections:
        selected = collection_picker(collections, "research_collection")
        docs = selected.get("documents", []) if selected else []
        if selected:
            with st.form("research_query"):
                question = st.text_area("Research question", placeholder="What do the documents say about…")
                controls = st.columns(3)
                mode = controls[0].selectbox("Retrieval", ["hybrid", "dense", "bm25"])
                top_k = controls[1].number_input("Sources", min_value=1, max_value=30, value=8)
                rerank = controls[2].checkbox("Use optional reranking", value=True)
                selected_docs = st.multiselect("Limit to documents (optional)", docs,
                                               format_func=lambda d: d["name"])
                submit = st.form_submit_button("Ask research assistant", type="primary")
            if submit:
                try:
                    result = request("POST", "/research/query", json={
                        "query": question, "collection_id": selected["id"],
                        "document_ids": [doc["id"] for doc in selected_docs],
                        "mode": mode, "top_k": int(top_k), "rerank": rerank,
                    })
                    st.markdown("### Answer")
                    st.write(result["answer"])
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("#### Agreements")
                        if result["agreements"]:
                            for item in result["agreements"]:
                                st.markdown(f"- {item['finding']} `{' '.join(item['source_ids'])}`")
                        else:
                            st.caption("No agreement findings returned.")
                    with c2:
                        st.markdown("#### Potential contradictions")
                        if result["contradictions"]:
                            for item in result["contradictions"]:
                                st.markdown(f"- {item['finding']} `{' '.join(item['source_ids'])}`")
                        else:
                            st.caption("No contradiction findings returned.")
                    st.markdown("#### Citations")
                    for citation in result["citations"]:
                        label = f"{citation['source_id']} · {citation['document_name']} · page {citation['page_number'] or 'overview'}"
                        with st.expander(label):
                            st.write(citation.get("excerpt", ""))
                    st.caption(f"Timings (ms): {result['timings_ms']} · Reranking applied: {result['reranking']['applied']}")
                    if result["reranking"].get("error"):
                        st.warning(f"Reranking unavailable; initial retrieval results were used: {result['reranking']['error']}")
                    for caveat in result.get("caveats", []):
                        st.caption(caveat)
                except RuntimeError as exc:
                    st.error(str(exc))
    else:
        st.info("Create a collection before asking questions.")

elif page == "Settings":
    st.subheader("Configuration")
    try:
        configuration = request("GET", "/settings")
        for label, key in [("Language model", "llm"), ("Embeddings", "embeddings"),
                           ("Vector store", "vector_store"), ("Reranker", "reranker")]:
            info = configuration[key]
            st.write(f"**{label}:** {info.get('provider', info.get('mode'))} · {info.get('model', '')} "
                     f"· {'configured' if info.get('configured', True) else 'credentials missing'}")
    except RuntimeError as exc:
        st.error(str(exc))
    st.caption("Provider names and credential presence are shown; secret values are never returned. Change settings in the backend `.env` and restart the API.")

elif page == "Comparison":
    collections = load_collections()
    if collections:
        selected = collection_picker(collections, "compare_collection")
        docs = selected.get("documents", []) if selected else []
        if selected:
            with st.form("compare_docs"):
                chosen = st.multiselect("Select at least two indexed documents", docs,
                                        format_func=lambda d: f"{d['name']} ({d['status']})")
                focus = st.text_input("Comparison focus", value="Compare the main findings, methods, and limitations.")
                compare_mode = st.selectbox("Retrieval", ["hybrid", "bm25", "dense"], key="compare_mode")
                compare_button = st.form_submit_button("Compare documents", type="primary")
            if compare_button:
                if len(chosen) < 2:
                    st.warning("Select at least two documents.")
                else:
                    try:
                        result = request("POST", "/research/compare", json={
                            "query": focus, "collection_id": selected["id"],
                            "document_ids": [doc["id"] for doc in chosen],
                            "mode": compare_mode, "rerank": True,
                        })
                        st.markdown("### Comparison")
                        st.write(result["answer"])
                        left, right = st.columns(2)
                        with left:
                            st.markdown("#### Common findings")
                            for item in result["agreements"]:
                                st.markdown(f"- {item['finding']} `{' '.join(item['source_ids'])}`")
                        with right:
                            st.markdown("#### Potential contradictions")
                            for item in result["contradictions"]:
                                st.markdown(f"- {item['finding']} `{' '.join(item['source_ids'])}`")
                        for citation in result["citations"]:
                            with st.expander(f"{citation['source_id']} · {citation['document_name']} · page {citation['page_number'] or 'overview'}"):
                                st.write(citation["excerpt"])
                    except RuntimeError as exc:
                        st.error(str(exc))
    else:
        st.info("Create a collection and index at least two documents to compare them.")

elif page == "Reports":
    collections = load_collections()
    if collections:
        selected = collection_picker(collections, "report_collection")
        if selected:
            st.subheader("Generate a research report")
            with st.form("generate_report"):
                title = st.text_input("Report title")
                question = st.text_area("Research question", placeholder="Synthesize the evidence on…")
                report_mode = st.selectbox("Retrieval", ["hybrid", "bm25", "dense"], key="report_mode")
                report_documents = st.multiselect("Limit to documents (optional)", selected.get("documents", []),
                                                  format_func=lambda d: d["name"])
                generate = st.form_submit_button("Generate DOCX report", type="primary")
            if generate:
                try:
                    report = request("POST", "/reports/generate", json={
                        "title": title or None, "query": question, "collection_id": selected["id"],
                        "document_ids": [doc["id"] for doc in report_documents],
                        "mode": report_mode, "top_k": 10, "rerank": True,
                    })
                    st.success("Report created and saved.")
                    st.markdown(f"### {report['title']}")
                    st.write(report["content"]["executive_summary"])
                    safe_name = re.sub(r"[^A-Za-z0-9 _.-]", "_", report["title"]).strip(" .")[:80] or "Research Report"
                    st.download_button("Download DOCX", download_report(report["id"]),
                                       file_name=f"{safe_name}.docx",
                                       mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                except RuntimeError as exc:
                    st.error(str(exc))
            st.subheader("Report history")
            try:
                reports = request("GET", "/reports", params={"collection_id": selected["id"]})
                if reports:
                    selected_report = st.selectbox("Saved report", reports,
                                                   format_func=lambda item: f"{item['title']} · {item['created_at']}")
                    detail = request("GET", f"/reports/{selected_report['id']}")
                    st.write(detail["content"]["executive_summary"])
                    if st.button("Prepare saved report download"):
                        try:
                            st.session_state["saved_report_bytes"] = download_report(selected_report["id"])
                            st.session_state["saved_report_id"] = selected_report["id"]
                        except RuntimeError as exc:
                            st.warning(str(exc))
                    if st.session_state.get("saved_report_bytes") and st.session_state.get("saved_report_id") == selected_report["id"]:
                        safe_name = re.sub(r"[^A-Za-z0-9 _.-]", "_", selected_report["title"]).strip(" .")[:80] or "Research Report"
                        st.download_button("Download DOCX", st.session_state["saved_report_bytes"],
                                           file_name=f"{safe_name}.docx", key=f"saved-download-{selected_report['id']}")
                else:
                    st.caption("No saved reports in this collection yet.")
            except RuntimeError as exc:
                st.error(str(exc))
    else:
        st.info("Create a collection before generating reports.")

elif page == "Analytics":
    collections = load_collections()
    if collections:
        selected = collection_picker(collections, "analytics_collection")
        if selected:
            try:
                collection_id = selected["id"]
                overview = request("GET", "/analytics/overview", params={"collection_id": collection_id})
                metric_cols = st.columns(4)
                metric_cols[0].metric("Documents", overview["documents"])
                metric_cols[1].metric("Indexed pages", overview["indexed_pages"])
                metric_cols[2].metric("Chunks", overview["chunks"])
                metric_cols[3].metric("Research queries", overview["query_count"])
                topics = request("GET", "/analytics/topics", params={"collection_id": collection_id})
                relevance = request("GET", "/analytics/document-relevance", params={"collection_id": collection_id})
                gaps = request("GET", "/analytics/research-gaps", params={"collection_id": collection_id})
                left, right = st.columns(2)
                with left:
                    st.markdown("#### Distinctive terms")
                    st.caption(topics["note"])
                    st.dataframe([{"Term": item["term"], "Documents": item["document_count"],
                                   "Frequency": item["frequency"]} for item in topics["topics"]],
                                 use_container_width=True, hide_index=True)
                with right:
                    st.markdown("#### Document relevance")
                    st.dataframe([{"Document": item["document_name"], "Cited": item["query_citation_count"],
                                   "Status": item["status"]} for item in relevance["documents"]],
                                 use_container_width=True, hide_index=True)
                st.markdown("#### Review prompts")
                st.caption(gaps["note"])
                if gaps["indexing_gaps"]:
                    st.dataframe(gaps["indexing_gaps"], use_container_width=True, hide_index=True)
                else:
                    st.success("All collection documents are indexed.")
                if gaps["sparse_topic_candidates"]:
                    st.write("Vocabulary appearing in one document:", ", ".join(item["term"] for item in gaps["sparse_topic_candidates"]))
            except RuntimeError as exc:
                st.error(str(exc))
    else:
        st.info("Create a collection to see analytics.")

else:
    st.subheader(page)
    st.info("This page is reserved for a later milestone. Research reports, document comparison workflows, and analytics are not implemented yet.")

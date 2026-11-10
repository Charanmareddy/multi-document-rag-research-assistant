"""Streamlit entry point for the research assistant."""

import streamlit as st

st.set_page_config(page_title="Research Assistant", page_icon="📚", layout="wide")
st.title("📚 Multi-Document RAG Research Assistant")
st.caption("Research smarter — ask questions across entire libraries of documents.")
st.info("Foundation milestone is ready. Collection uploads, indexing, and research workflows are added in later milestones.")

with st.sidebar:
    st.header("Workspace")
    st.selectbox("Section", ["Dashboard", "Collections", "Research Assistant", "Comparison", "Reports", "Analytics", "Settings"])

st.subheader("Getting started")
st.markdown("Run the FastAPI backend, then use the API documentation at `/docs`. The collection manager will be connected in the next milestone.")

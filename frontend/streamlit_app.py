import requests
import streamlit as st

API = "http://localhost:8000"

# ── page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="VaultIQ", page_icon="🔒", layout="wide")

# ── CSS ────────────────────────────────────────────────────────────────────────
# Scoped only to elements we actually want to change. No wildcard selectors.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

[data-testid="stChatMessageContent"],
[data-testid="stChatMessageContent"] p,
[data-testid="stChatMessageContent"] li,
[data-testid="stChatMessageContent"] span,
[data-testid="stChatMessageContent"] a {
    font-family: 'Inter', sans-serif !important;
    font-size: 15px !important;
    line-height: 1.8 !important;
    word-spacing: normal !important;
    letter-spacing: normal !important;
}

.sources-block {
    margin-top: 10px;
    padding: 10px 14px;
    border-left: 3px solid #444;
    border-radius: 0 6px 6px 0;
    background: rgba(255, 255, 255, 0.04);
    font-size: 13px;
    color: #999;
    font-family: 'Inter', sans-serif;
    line-height: 1.7;
}

.sources-block .sources-title {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #666;
    margin-bottom: 6px;
}

.sources-block .source-item {
    padding: 2px 0;
}
</style>
""", unsafe_allow_html=True)

# ── session state ──────────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


# ── API helpers ────────────────────────────────────────────────────────────────

def _error_detail(http_err):
    try:
        return http_err.response.json().get("detail", str(http_err))
    except Exception:
        return http_err.response.text or str(http_err)


def fetch_documents():
    try:
        r = requests.get(f"{API}/documents", timeout=5)
        r.raise_for_status()
        return r.json(), None
    except requests.ConnectionError:
        return [], "Cannot reach backend — is uvicorn running?"
    except Exception as e:
        return [], str(e)


def upload_file(file):
    try:
        r = requests.post(
            f"{API}/upload",
            files={"file": (file.name, file, file.type)},
            timeout=120,
        )
        r.raise_for_status()
        return r.json(), None
    except requests.HTTPError as e:
        return None, _error_detail(e)
    except requests.ConnectionError:
        return None, "Cannot reach backend — is uvicorn running?"
    except Exception as e:
        return None, str(e)


def ask(question, top_k):
    try:
        r = requests.post(
            f"{API}/ask",
            json={"question": question, "top_k": top_k},
            timeout=60,
        )
        r.raise_for_status()
        return r.json(), None
    except requests.HTTPError as e:
        return None, _error_detail(e)
    except requests.ConnectionError:
        return None, "Cannot reach backend — is uvicorn running?"
    except Exception as e:
        return None, str(e)


def delete_doc(filename):
    try:
        r = requests.delete(f"{API}/documents/{filename}", timeout=10)
        r.raise_for_status()
        return True, None
    except requests.HTTPError as e:
        return False, _error_detail(e)
    except Exception as e:
        return False, str(e)


# ── render helpers ─────────────────────────────────────────────────────────────

def render_sources(sources):
    """
    Deduplicate by (filename, page) and render as a styled inline block.
    Avoids st.expander entirely — no arrow-key UI conflicts near the chat input.
    """
    if not sources:
        return

    seen = set()
    unique = []
    for s in sources:
        key = (s["filename"], s["page"])
        if key not in seen:
            seen.add(key)
            unique.append(s)

    items_html = "".join(
        f'<div class="source-item">📄 <strong>{s["filename"]}</strong> — Page {s["page"]}</div>'
        for s in unique
    )
    st.markdown(
        f'<div class="sources-block">'
        f'<div class="sources-title">Sources</div>'
        f'{items_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def safe_markdown(text: str):
    """
    Render LLM output safely.
    - Escapes $ so Streamlit doesn't treat amounts like $170.22 as LaTeX
    - Preserves paragraph breaks
    """
    escaped = text.replace("$", r"\$")
    st.markdown(escaped)


def render_exchange(exchange):
    with st.chat_message("user"):
        st.markdown(exchange["question"])
    with st.chat_message("assistant"):
        safe_markdown(exchange["answer"])
        render_sources(exchange.get("sources", []))


# ── SIDEBAR ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("VaultIQ")
    st.caption("Upload documents and ask questions.")
    st.divider()

    # upload
    uploaded_files = st.file_uploader(
        "Upload documents",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        for f in uploaded_files:
            with st.spinner(f"Indexing {f.name}..."):
                result, err = upload_file(f)
            if err:
                st.error(f"**{f.name}**: {err}")
            else:
                st.success(f"**{f.name}** — {result['chunks_stored']} chunks indexed")

    st.divider()

    # document list
    docs, fetch_err = fetch_documents()
    if fetch_err and not docs:
        st.warning(fetch_err)
    elif not docs:
        st.info("No documents uploaded yet.")
    else:
        st.subheader(f"Indexed files ({len(docs)})")
        for doc in docs:
            col1, col2 = st.columns([4, 1])
            col1.markdown(
                f"**{doc['filename']}**  \n"
                f"<span style='font-size:12px;color:#888'>{doc['chunk_count']} chunks · {doc['page_count']} pages</span>",
                unsafe_allow_html=True,
            )
            if col2.button("✕", key=f"del_{doc['filename']}", help=f"Remove {doc['filename']}"):
                ok, err = delete_doc(doc["filename"])
                if ok:
                    st.rerun()
                else:
                    st.error(err)

    st.divider()
    top_k = st.slider("Chunks to retrieve", min_value=1, max_value=10, value=5)


# ── MAIN ───────────────────────────────────────────────────────────────────────

st.title("🔒 VaultIQ")
st.caption("Ask questions across your uploaded documents — answers come with citations.")

# render chat history (last 5 exchanges)
for exchange in st.session_state.chat_history[-5:]:
    render_exchange(exchange)

# chat input
question = st.chat_input("Ask a question about your documents...")

if question:
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            result, err = ask(question, top_k)

        if err:
            st.error(err)
        else:
            safe_markdown(result["answer"])
            render_sources(result.get("sources", []))

            st.session_state.chat_history.append({
                "question": question,
                "answer": result["answer"],
                "sources": result.get("sources", []),
            })

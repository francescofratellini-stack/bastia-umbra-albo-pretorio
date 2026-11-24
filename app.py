from __future__ import annotations

import io
import re
import zipfile
from urllib.parse import urljoin, urlparse

import requests
import streamlit as st
from bs4 import BeautifulSoup

DEFAULT_URL = "https://bastiaumbra.halleyweb.it/c054002/zf/index.php/atti-amministrativi/albo"
ALLOWED_HOST = "bastiaumbra.halleyweb.it"
TIMEOUT_SECONDS = 20
MAX_DETAIL_PAGES = 30
MAX_FILE_BYTES = 30 * 1024 * 1024
MAX_ARCHIVE_BYTES = 100 * 1024 * 1024
DOCUMENT_EXTENSIONS = (".pdf", ".p7m", ".doc", ".docx", ".odt", ".xls", ".xlsx", ".ods", ".zip", ".jpg", ".jpeg", ".png", ".tif", ".tiff")
DETAIL_HINTS = ("dettaglio", "atto", "allegat", "document", "visualizza", "pubblicazione")
DOWNLOAD_HINTS = ("scarica", "download", "allegato", "documento", "file", "pdf")


def checked_url(url: str, base: str | None = None) -> str | None:
    """Resolve a link and restrict requests to the municipality's public portal."""
    resolved = urljoin(base or DEFAULT_URL, url.strip())
    parsed = urlparse(resolved)
    if parsed.scheme not in ("http", "https") or parsed.hostname != ALLOWED_HOST:
        return None
    return resolved


def fetch_page(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=TIMEOUT_SECONDS, allow_redirects=True)
    response.raise_for_status()
    if urlparse(response.url).hostname != ALLOWED_HOST:
        raise ValueError("Il portale ha reindirizzato a un dominio non consentito.")
    response.encoding = response.apparent_encoding or response.encoding
    return response.text


def collect_links(html: str, page_url: str) -> tuple[list[dict[str, str]], list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    documents: dict[str, dict[str, str]] = {}
    details: list[str] = []

    for anchor in soup.find_all("a", href=True):
        href = checked_url(anchor.get("href", ""), page_url)
        if not href:
            continue
        label = " ".join(anchor.stripped_strings)
        if not label:
            label = anchor.get("title", "Documento senza titolo").strip()
        hint = f"{href} {label}".lower()
        path = urlparse(href).path.lower()
        if path.endswith(DOCUMENT_EXTENSIONS) or any(word in hint for word in DOWNLOAD_HINTS):
            documents.setdefault(href, {"title": label or "Documento", "url": href})
        elif any(word in hint for word in DETAIL_HINTS) and href != page_url:
            details.append(href)

    return list(documents.values()), list(dict.fromkeys(details))


def scan_portal(start_url: str) -> list[dict[str, str]]:
    start = checked_url(start_url)
    if not start:
        raise ValueError(f"Inserisci un URL del portale ufficiale ({ALLOWED_HOST}).")

    session = requests.Session()
    session.headers.update({"User-Agent": "BastiaUmbraAlboPretorio/1.0 (public document downloader)"})
    html = fetch_page(session, start)
    documents, detail_urls = collect_links(html, start)

    visited = {start}
    for detail_url in detail_urls[:MAX_DETAIL_PAGES]:
        if detail_url in visited:
            continue
        visited.add(detail_url)
        try:
            detail_html = fetch_page(session, detail_url)
        except (requests.RequestException, ValueError):
            continue
        found, _ = collect_links(detail_html, detail_url)
        for item in found:
            documents.append(item)

    unique: dict[str, dict[str, str]] = {}
    for item in documents:
        unique.setdefault(item["url"], item)
    return list(unique.values())


def safe_filename(name: str, url: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|\x00-\x1f]", "_", name).strip(" ._")
    if not name:
        name = urlparse(url).path.rsplit("/", 1)[-1] or "documento"
    if "." not in name.rsplit("/", 1)[-1]:
        suffix = urlparse(url).path.rsplit("/", 1)[-1]
        if "." in suffix:
            name += "." + suffix.rsplit(".", 1)[-1]
    return name[:160]


def build_archive(items: list[dict[str, str]]) -> tuple[bytes, list[str]]:
    session = requests.Session()
    session.headers.update({"User-Agent": "BastiaUmbraAlboPretorio/1.0 (public document downloader)"})
    archive = io.BytesIO()
    errors: list[str] = []
    total = 0
    used_names: set[str] = set()

    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in items:
            url = checked_url(item["url"])
            if not url:
                errors.append(f"{item['title']}: link non consentito")
                continue
            try:
                with session.get(url, timeout=TIMEOUT_SECONDS, stream=True, allow_redirects=True) as response:
                    response.raise_for_status()
                    if urlparse(response.url).hostname != ALLOWED_HOST:
                        raise ValueError("reindirizzamento a un dominio non consentito")
                    declared = int(response.headers.get("Content-Length", "0") or 0)
                    if declared > MAX_FILE_BYTES:
                        raise ValueError("file oltre il limite di 30 MB")
                    chunks = []
                    size = 0
                    for chunk in response.iter_content(chunk_size=64 * 1024):
                        if not chunk:
                            continue
                        size += len(chunk)
                        if size > MAX_FILE_BYTES:
                            raise ValueError("file oltre il limite di 30 MB")
                        chunks.append(chunk)
                    total += size
                    if total > MAX_ARCHIVE_BYTES:
                        raise ValueError("archivio oltre il limite di 100 MB")
                    filename = safe_filename(item["title"], url)
                    stem, dot, suffix = filename.rpartition(".")
                    base = stem if dot else filename
                    extension = f".{suffix}" if dot else ""
                    candidate = filename
                    counter = 2
                    while candidate.lower() in used_names:
                        candidate = f"{base}_{counter}{extension}"
                        counter += 1
                    used_names.add(candidate.lower())
                    zf.writestr(candidate, b"".join(chunks))
            except (requests.RequestException, ValueError, OSError) as exc:
                errors.append(f"{item['title']}: {exc}")

    return archive.getvalue(), errors


st.set_page_config(page_title="Albo Pretorio · Bastia Umbra", page_icon="📄", layout="wide")
st.title("Scarica documenti · Albo Pretorio")
st.caption("Comune di Bastia Umbra · Consultazione e download di atti e allegati pubblicati")
st.info("L'applicazione legge esclusivamente pagine pubbliche del portale ufficiale. Rispetta le condizioni d'uso del sito e la normativa applicabile.")

with st.form("search_form"):
    listing_url = st.text_input("Pagina dell'Albo Pretorio", value=DEFAULT_URL)
    submitted = st.form_submit_button("Cerca documenti", type="primary")

if submitted:
    with st.spinner("Sto consultando l'Albo e le pagine degli atti…"):
        try:
            st.session_state["documents"] = scan_portal(listing_url)
            st.session_state["scan_error"] = None
        except (requests.RequestException, ValueError) as exc:
            st.session_state["documents"] = []
            st.session_state["scan_error"] = str(exc)

if st.session_state.get("scan_error"):
    st.error(f"Ricerca non riuscita: {st.session_state['scan_error']}")

documents = st.session_state.get("documents", [])
if documents:
    st.success(f"Trovati {len(documents)} link a documenti o allegati.")
    query = st.text_input("Filtra per titolo o nome file")
    filtered = [item for item in documents if query.casefold() in item["title"].casefold() or query.casefold() in item["url"].casefold()]
    labels = {f"{item['title']} — {item['url']}": item for item in filtered}
    selected_labels = st.multiselect("Seleziona i documenti da scaricare", options=list(labels), default=list(labels))
    if selected_labels and st.button("Prepara ZIP", type="primary"):
        with st.spinner("Download dei documenti selezionati…"):
            archive_data, errors = build_archive([labels[label] for label in selected_labels])
        if archive_data:
            st.download_button("Scarica archivio ZIP", data=archive_data, file_name="atti_albo_pretorio_bastia_umbra.zip", mime="application/zip")
        if errors:
            st.warning("Alcuni documenti non sono stati scaricati:\n\n" + "\n".join(f"- {error}" for error in errors))
    st.caption("Il portale può rendere disponibili altri atti tramite filtri o pagine successive: usa la pagina ufficiale per consultare i risultati completi.")
elif st.session_state.get("documents") == [] and not st.session_state.get("scan_error") and not submitted:
    st.write("Inserisci o conferma la pagina dell'Albo e premi **Cerca documenti** per iniziare.")
elif submitted and not documents and not st.session_state.get("scan_error"):
    st.warning("Non sono stati trovati link a documenti. Il portale potrebbe aver cambiato struttura o richiedere filtri nella pagina ufficiale.")

st.divider()
st.caption("I link e i file restano sul portale comunale; l'app non archivia né modifica gli atti.")

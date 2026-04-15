import logging
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import FastEmbedEmbeddings
from langchain_community.vectorstores import FAISS

logger = logging.getLogger(__name__)


def ingest_documents(force: bool = False):
    index_path = Path("./faiss_index")
    if index_path.exists() and any(index_path.iterdir()) and not force:
        logger.info("FAISS index already exists at %s, skipping ingestion.", index_path)
        return

    data_dir = Path(__file__).resolve().parent / "data"
    markdown_files = sorted(data_dir.glob("*.md"))
    if not markdown_files:
        raise RuntimeError("No markdown files found in langchain-backend/data")

    texts = []
    for path in markdown_files:
        logger.info("Reading %s", path)
        texts.append(path.read_text(encoding="utf-8"))

    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=100)
    chunks = splitter.split_text("\n\n".join(texts))
    logger.info("Split documents into %d text chunks", len(chunks))

    embeddings = FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")
    index = FAISS.from_texts(chunks, embeddings)
    index.save_local(str(index_path))
    logger.info("Saved FAISS index to %s", index_path)


if __name__ == "__main__":
    ingest_documents(force=False)

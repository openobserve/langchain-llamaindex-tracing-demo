import logging
from pathlib import Path

from llama_index.core import Settings, SimpleDirectoryReader, StorageContext, VectorStoreIndex
from llama_index.llms.anthropic import Anthropic
from llama_index.embeddings.fastembed import FastEmbedEmbedding

logger = logging.getLogger(__name__)


def ingest_documents(force: bool = False):
    storage_dir = Path("./llamaindex_storage")
    if storage_dir.exists() and any(storage_dir.iterdir()) and not force:
        logger.info("LlamaIndex storage already exists at %s, skipping ingestion.", storage_dir)
        return

    data_dir = Path(__file__).resolve().parent / "data"
    if not data_dir.exists():
        raise RuntimeError("No data directory found in llamaindex-backend/data")

    Settings.llm = Anthropic(model="claude-haiku-4-5-20251001", temperature=0)
    Settings.embed_model = FastEmbedEmbedding(model_name="BAAI/bge-small-en-v1.5")

    reader = SimpleDirectoryReader(str(data_dir))
    documents = reader.load_data()
    if not documents:
        raise RuntimeError("No documents loaded for LlamaIndex ingestion")

    storage_dir.mkdir(parents=True, exist_ok=True)
    index = VectorStoreIndex.from_documents(documents)
    index.storage_context.persist(persist_dir=str(storage_dir))
    logger.info("Persisted LlamaIndex storage to %s", storage_dir)


if __name__ == "__main__":
    ingest_documents(force=False)

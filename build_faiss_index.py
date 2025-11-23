"""
Utility script to build and persist a FAISS vector index from the CS336 PDF.

Run:
    python build_faiss_index.py --pdf cs336_spring2025_assignment1_basics.pdf
"""

import argparse
import logging
import os
import shutil
from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader

DEFAULT_PDF_PATH = "cs336_spring2025_assignment1_basics.pdf"
DEFAULT_INDEX_DIR = "faiss_index"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("build_faiss_index")


def build_index(pdf_path: str, index_dir: str, force: bool = False):
    """Create embeddings from the PDF and persist them as a FAISS index."""
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")

    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file not found: {pdf_path}")

    if os.path.isdir(index_dir):
        if force:
            logger.warning("Removing existing index directory at %s", index_dir)
            shutil.rmtree(index_dir)
        else:
            raise FileExistsError(
                f"Index directory '{index_dir}' already exists. "
                "Rerun with --force to overwrite it."
            )

    logger.info("Loading PDF: %s", pdf_path)
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()
    logger.info("Loaded %s pages", len(documents))

    logger.info("Splitting documents into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    chunks = text_splitter.split_documents(documents)
    logger.info("Created %s text chunks", len(chunks))

    logger.info("Generating embeddings via OpenAI...")
    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
    vectorstore = FAISS.from_documents(chunks, embeddings)

    logger.info("Persisting FAISS index to %s", index_dir)
    vectorstore.save_local(index_dir)
    logger.info("✅ FAISS index written successfully!")


def _parse_args(args: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a persisted FAISS index.")
    parser.add_argument(
        "--pdf",
        default=DEFAULT_PDF_PATH,
        help=f"Path to the source PDF (default: {DEFAULT_PDF_PATH})",
    )
    parser.add_argument(
        "--index-dir",
        default=DEFAULT_INDEX_DIR,
        help=f"Directory to store the FAISS index (default: {DEFAULT_INDEX_DIR})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the target directory if it already exists.",
    )
    return parser.parse_args(args)


def main():
    args = _parse_args()
    build_index(pdf_path=args.pdf, index_dir=args.index_dir, force=args.force)


if __name__ == "__main__":
    main()



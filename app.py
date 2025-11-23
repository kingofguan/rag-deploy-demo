"""
RAG Application for W501 Homework
Uses LangChain and a pre-built FAISS index to answer questions about the
CS336 Spring 2025 Assignment 1 Basics document.
"""

import os
import logging
import traceback
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import PromptTemplate

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(
    __name__,
    static_folder='static',
    static_url_path='',
    template_folder='static'
)
CORS(app)

# Global configuration
FAISS_INDEX_DIR = os.environ.get("FAISS_INDEX_DIR", "faiss_index")
REQUIRED_INDEX_FILES = ("index.faiss", "index.pkl")

# Global state
vectorstore = None
qa_chain = None


class SimpleRetrievalQA:
    """Lightweight retrieval + generation pipeline compatible with new LangChain releases."""

    def __init__(self, llm, retriever, prompt_template: PromptTemplate):
        self.llm = llm
        self.retriever = retriever
        self.prompt = prompt_template

    def _retrieve(self, question: str):
        """Support both new Runnable-style retrievers and legacy ones."""
        if hasattr(self.retriever, "invoke"):
            return self.retriever.invoke(question)
        if hasattr(self.retriever, "get_relevant_documents"):
            return self.retriever.get_relevant_documents(question)
        if hasattr(self.retriever, "_get_relevant_documents"):
            return self.retriever._get_relevant_documents(question)
        raise AttributeError("Retriever does not support document retrieval.")

    def __call__(self, inputs):
        """Mimic RetrievalQA interface."""
        if isinstance(inputs, dict):
            question = inputs.get("query") or inputs.get("question", "")
        else:
            question = str(inputs)

        if not question:
            raise ValueError("Question is required for RAG invocation.")

        source_docs = self._retrieve(question)
        context = "\n\n".join(doc.page_content for doc in source_docs)
        formatted_prompt = self.prompt.format(context=context, question=question)
        response = self.llm.invoke(formatted_prompt)

        return {
            "result": response.content if hasattr(response, "content") else str(response),
            "source_documents": source_docs,
        }

def _validate_index_directory(index_dir: str):
    """Ensure the FAISS index directory exists and contains required files."""
    if not os.path.isdir(index_dir):
        raise FileNotFoundError(
            f"FAISS index directory not found: '{index_dir}'. "
            "Please generate it first using build_faiss_index.py."
        )

    missing_files = [
        fname for fname in REQUIRED_INDEX_FILES
        if not os.path.exists(os.path.join(index_dir, fname))
    ]
    if missing_files:
        raise FileNotFoundError(
            f"FAISS index directory '{index_dir}' is missing files: {missing_files}. "
            "Re-run build_faiss_index.py or ensure the directory was copied correctly."
        )


def initialize_qa_system():
    """Initialize the QA system by loading the persisted FAISS index."""
    global vectorstore, qa_chain
    
    logger.info("=" * 60)
    logger.info("Initializing QA system...")
    logger.info("=" * 60)
    
    # Get OpenAI API key from environment
    openai_api_key = os.environ.get('OPENAI_API_KEY')
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    
    # Validate FAISS index
    logger.info(f"Looking for FAISS index at: {FAISS_INDEX_DIR}")
    _validate_index_directory(FAISS_INDEX_DIR)

    # Create embeddings and load FAISS vectorstore
    logger.info("Loading FAISS vectorstore from disk...")
    embeddings = OpenAIEmbeddings(openai_api_key=openai_api_key)
    vectorstore = FAISS.load_local(
        FAISS_INDEX_DIR,
        embeddings,
        allow_dangerous_deserialization=True,  # Required for pickle metadata
    )
    logger.info("✅ FAISS vectorstore loaded successfully!")
    
    # Create QA chain
    logger.info("Setting up QA chain with GPT-3.5-turbo...")
    llm = ChatOpenAI(
        model_name="gpt-3.5-turbo",
        temperature=0,
        openai_api_key=openai_api_key
    )
    
    # Custom prompt template
    prompt_template = """You are a helpful AI assistant answering questions about the CS336 Spring 2025 Assignment 1 Basics document.
Use the following pieces of context to answer the question at the end. If you don't know the answer, just say that you don't know, don't try to make up an answer.

Context: {context}

Question: {question}

Answer: """
    
    PROMPT = PromptTemplate(
        template=prompt_template,
        input_variables=["context", "question"]
    )
    
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    qa_chain = SimpleRetrievalQA(llm=llm, retriever=retriever, prompt_template=PROMPT)
    
    logger.info("✅ QA chain configured (retrieves top 3 relevant chunks)")
    logger.info("=" * 60)
    logger.info("✅ RAG system ready!")
    logger.info("=" * 60)

@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html')

@app.before_request
def ensure_qa_ready():
    """Gunicorn/production hook to load the QA system once per worker."""
    if qa_chain is None:
        logger.info("QA system not initialized yet; loading before serving requests...")
        initialize_qa_system()


@app.route('/health')
def health():
    """Health check endpoint"""
    index_files_present = all(
        os.path.exists(os.path.join(FAISS_INDEX_DIR, fname))
        for fname in REQUIRED_INDEX_FILES
    )
    return jsonify({
        "status": "healthy",
        "vectorstore_initialized": vectorstore is not None,
        "qa_chain_initialized": qa_chain is not None,
        "faiss_index_dir": FAISS_INDEX_DIR,
        "faiss_index_files_present": index_files_present,
    })

@app.route('/api/ask', methods=['POST'])
def ask_question():
    """Handle question answering requests"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({"error": "Question is required"}), 400
        
        if qa_chain is None:
            return jsonify({"error": "QA system not initialized"}), 500
        
        logger.info(f"Processing question: {question}")
        
        # Get answer from QA chain
        result = qa_chain({"query": question})
        answer = result['result']
        
        # Extract source documents
        sources = []
        if 'source_documents' in result:
            for doc in result['source_documents']:
                sources.append(doc.page_content[:200] + "...")
        
        logger.info(f"Answer generated successfully")
        
        return jsonify({
            "question": question,
            "answer": answer,
            "sources": sources
        })
    
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        logger.error(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route('/api/info')
def get_info():
    """Get system information"""
    return jsonify({
        "app_name": "W501 RAG Application",
        "description": "RAG system using LangChain and FAISS for CS336 Assignment 1 Basics",
        "technologies": ["LangChain", "FAISS", "OpenAI", "Flask"],
        "status": "running"
    })

if __name__ == '__main__':
    try:
        logger.info("=" * 60)
        logger.info("Starting CS336 RAG Application for W501 Homework")
        logger.info("=" * 60)
        
        # Initialize QA system on startup (loads PDF and creates vector database)
        initialize_qa_system()
        
        # Start Flask server
        port = int(os.environ.get('PORT', 8080))
        logger.info(f"Starting Flask server on port {port}...")
        logger.info("=" * 60)
        logger.info(f"🚀 Application ready! Visit: http://localhost:{port}")
        logger.info("=" * 60)
        
        app.run(host='0.0.0.0', port=port, debug=False)
        
    except FileNotFoundError as e:
        logger.error("=" * 60)
        logger.error("❌ STARTUP FAILED: PDF file missing")
        logger.error(f"Error: {e}")
        logger.error("Please ensure 'cs336_spring2025_assignment1_basics.pdf' is in the current directory")
        logger.error("=" * 60)
        exit(1)
    except ValueError as e:
        logger.error("=" * 60)
        logger.error("❌ STARTUP FAILED: Configuration error")
        logger.error(f"Error: {e}")
        logger.error("Please set OPENAI_API_KEY environment variable")
        logger.error("=" * 60)
        exit(1)
    except Exception as e:
        logger.error("=" * 60)
        logger.error("❌ STARTUP FAILED")
        logger.error(f"Error: {e}")
        logger.error(traceback.format_exc())
        logger.error("=" * 60)
        exit(1)


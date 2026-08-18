"""Quick smoke test for KAG with OpenAI + memory storage (no Docker/OpenSPG).

This patches the SchemaClient to work without an OpenSPG server,
providing default entity types for knowledge graph extraction.
Uses BuilderChainRunner (ThreadPoolExecutor) and SolverPipelineABC directly.
"""
import os
import sys
import asyncio

# Set API keys from parent .env
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(__file__), "..", "..", ".env")
load_dotenv(env_path)

api_key = os.getenv("OPENAI_API_KEY", "")
os.environ.setdefault("LLM_API_KEY", api_key)
os.environ.setdefault("VECTORIZE_MODEL_API_KEY", api_key)

# Work from KAG project dir
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# --- Monkey-patch SchemaClient BEFORE importing KAG builder components ---
# The SchemaClient tries to connect to an OpenSPG REST server for schema queries.
# We patch it to return sensible defaults so KAG works in pure memory mode.
from knext.schema.client import SchemaClient

_DEFAULT_ENTITY_TYPES = [
    "Person", "Organization", "Location", "Event",
    "Date", "Concept", "Creature", "Works", "Others"
]

def _patched_init(self, host_addr=None, project_id=None):
    """Initialize SchemaClient without connecting to OpenSPG."""
    self._host_addr = host_addr
    self._project_id = project_id
    self._session = None
    self._rest_client = None

SchemaClient.__init__ = _patched_init

def _patched_load(self):
    """Return empty schema dict (no SPG types defined)."""
    return {}

SchemaClient.load = _patched_load

def _patched_extract_types(self, language=None):
    """Return default entity types without querying OpenSPG."""
    return _DEFAULT_ENTITY_TYPES

SchemaClient.extract_types = _patched_extract_types

# Also patch ProjectClient which tries to connect to OpenSPG
from knext.project.client import ProjectClient

def _patched_project_init(self, host_addr=None, project_id=None):
    self._host_addr = host_addr
    self._project_id = project_id
    self._rest_client = None

ProjectClient.__init__ = _patched_project_init

# Patch SchemaSession to not query OpenSPG on init
from knext.schema.client import SchemaSession

def _patched_session_init(self, client, project_id):
    self._alter_spg_types = []
    self._rest_client = client
    self._project_id = project_id
    self._spg_types = {}
    self.__spg_types = {}
    # Skip self._init_spg_types() which queries OpenSPG

SchemaSession.__init__ = _patched_session_init

# Patch ReasonerClient to not query OpenSPG
from knext.reasoner.client import ReasonerClient

def _patched_reasoner_init(self, host_addr=None, project_id=None):
    self._host_addr = host_addr
    self._project_id = project_id
    self._rest_client = None
    self.reason_schema = {}

ReasonerClient.__init__ = _patched_reasoner_init

# Patch SchemaUtils to return empty schema
from kag.interface.solver.model.schema_utils import SchemaUtils

_original_schema_utils_init = SchemaUtils.__init__

def _patched_schema_utils_init(self, *args, **kwargs):
    self.config = type('Config', (), {'host_addr': 'http://127.0.0.1:8887'})()
    self.project_id = '1'
    self.schema = {}
    self.node_en_zh = {}
    self.edge_en_zh = {}

SchemaUtils.__init__ = _patched_schema_utils_init
# --- End monkey-patch ---

# Initialize KAG config
from kag.common.conf import init_env
init_env(config_file="./kag_config.yaml")

from kag.builder.runner import BuilderChainRunner
from kag.interface import SolverPipelineABC
from kag.common.conf import KAG_CONFIG


SAMPLE_TEXT = """# Albert Einstein

Albert Einstein (14 March 1879 - 18 April 1955) was a German-born theoretical physicist.
He developed the theory of relativity, one of the two pillars of modern physics alongside quantum mechanics.
His mass-energy equivalence formula E = mc^2 is the world's most famous equation.
He received the 1921 Nobel Prize in Physics for his discovery of the photoelectric effect.
Einstein was born in Ulm, in the Kingdom of Wurttemberg in the German Empire.
In 1880, the family moved to Munich.

# Marie Curie

Marie Curie (7 November 1867 - 4 July 1934) was a Polish and naturalized-French physicist and chemist.
She conducted pioneering research on radioactivity. She was the first woman to win a Nobel Prize.
She was the first person to win Nobel Prizes in two scientific fields: Physics in 1903 and Chemistry in 1911.
She discovered the elements polonium and radium.
Marie Curie was born Maria Sklodowska in Warsaw, Poland.
She became the first female professor at the University of Paris in 1906.
"""


def prepare_data():
    """Write sample data to a markdown file."""
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_data")
    os.makedirs(data_dir, exist_ok=True)
    file_path = os.path.join(data_dir, "sample.md")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(SAMPLE_TEXT)
    return file_path


def test_builder(file_path):
    """Test the KG builder with sample documents using thread-based runner."""
    print("=" * 60)
    print("Testing KAG Builder (Knowledge Graph Construction)")
    print("=" * 60)

    # Use BuilderChainRunner (base type - ThreadPoolExecutor)
    # instead of BuilderChainStreamRunner (stream type - ProcessPoolExecutor)
    # so that our monkey-patches survive in worker threads.
    runner = BuilderChainRunner.from_config(
        KAG_CONFIG.all_config["kag_builder_pipeline"]
    )
    runner.invoke(file_path)

    print("\nBuilder completed! Knowledge graph built in memory.")


async def test_solver():
    """Test the QA solver using direct pipeline invocation."""
    print("\n" + "=" * 60)
    print("Testing KAG Solver (Question Answering)")
    print("=" * 60)

    # Use SolverPipelineABC directly (no SolverMain/OpenSPG server needed)
    pipeline = SolverPipelineABC.from_config(
        KAG_CONFIG.all_config["kag_solver_pipeline"]
    )

    questions = [
        "Where was Einstein born?",
        "What did Marie Curie discover?",
    ]

    for q in questions:
        print(f"\nQ: {q}")
        answer = await pipeline.ainvoke(q)
        print(f"A: {answer}")


async def main():
    file_path = prepare_data()
    print(f"Test data written to: {file_path}\n")

    try:
        test_builder(file_path)
    except Exception as e:
        print(f"\nBuilder error: {e}")
        import traceback
        traceback.print_exc()
        return

    try:
        await test_solver()
    except Exception as e:
        print(f"\nSolver error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("KAG test complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

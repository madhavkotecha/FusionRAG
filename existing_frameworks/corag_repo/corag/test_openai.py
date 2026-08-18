"""
CoRAG test with OpenAI API — no GPU, no vLLM, no E5 server needed.

This adapts the CoRAG multi-hop retrieval agent to work with:
- OpenAI GPT-4o-mini as the LLM (instead of vLLM + fine-tuned Llama)
- OpenAI text-embedding-3-small for retrieval (instead of E5 GPU server)
- A small in-memory corpus (instead of the full KILT Wikipedia dump)
"""
import os
import sys
import json
import asyncio
import numpy as np
from typing import List, Dict, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

# Load API key
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".env")
load_dotenv(env_path)

from openai import OpenAI

# --------------- Configuration ---------------

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = "gpt-4o-mini"
EMBED_MODEL = "text-embedding-3-small"
TOP_K = 3
MAX_PATH_LENGTH = 3


# --------------- Simple corpus ---------------

CORPUS = [
    {
        "title": "Albert Einstein",
        "contents": (
            "Albert Einstein (14 March 1879 - 18 April 1955) was a German-born theoretical physicist. "
            "He developed the theory of relativity and contributed to quantum mechanics. "
            "He received the 1921 Nobel Prize in Physics for the photoelectric effect. "
            "Einstein was born in Ulm, in the Kingdom of Wurttemberg. His family moved to Munich in 1880."
        ),
    },
    {
        "title": "Theory of Relativity",
        "contents": (
            "The theory of relativity was developed by Albert Einstein. Special relativity was published in 1905 "
            "and general relativity in 1915. Special relativity introduced E = mc^2. "
            "General relativity describes gravity as spacetime curvature caused by mass and energy."
        ),
    },
    {
        "title": "Nobel Prize in Physics",
        "contents": (
            "The Nobel Prize in Physics is awarded annually by the Royal Swedish Academy of Sciences. "
            "Albert Einstein received it in 1921 for the photoelectric effect. "
            "Marie Curie received the Nobel Prize in Physics in 1903 for research on radiation."
        ),
    },
    {
        "title": "Marie Curie",
        "contents": (
            "Marie Curie (7 November 1867 - 4 July 1934) was a Polish-French physicist and chemist. "
            "She discovered polonium and radium. She was the first woman to win a Nobel Prize "
            "and the only person to win Nobel Prizes in two different sciences (Physics 1903, Chemistry 1911). "
            "She was born Maria Sklodowska in Warsaw, Poland."
        ),
    },
    {
        "title": "Photoelectric Effect",
        "contents": (
            "The photoelectric effect is the emission of electrons from a material when light hits it. "
            "Albert Einstein explained the photoelectric effect in 1905 using the concept of photons. "
            "This work was crucial to the development of quantum theory and earned him the 1921 Nobel Prize."
        ),
    },
    {
        "title": "Quantum Mechanics",
        "contents": (
            "Quantum mechanics is a fundamental theory in physics describing nature at atomic scales. "
            "Key contributors include Max Planck, Niels Bohr, Werner Heisenberg, and Erwin Schrodinger. "
            "Einstein contributed through the photoelectric effect and EPR paradox, though he famously "
            "disagreed with the Copenhagen interpretation, saying 'God does not play dice.'"
        ),
    },
    {
        "title": "University of Paris",
        "contents": (
            "The University of Paris was a major European university. Marie Curie became the first "
            "female professor there in 1906. She continued her research on radioactivity at the university "
            "and established the Radium Institute in 1914."
        ),
    },
    {
        "title": "Warsaw, Poland",
        "contents": (
            "Warsaw is the capital and largest city of Poland. Marie Curie was born there in 1867 "
            "as Maria Sklodowska. Warsaw has a rich scientific tradition and is home to many universities."
        ),
    },
]


# --------------- OpenAI-based LLM Client ---------------

class OpenAIClient:
    """Drop-in replacement for VllmClient that uses OpenAI API."""

    def __init__(self, model: str = LLM_MODEL, api_key: str = OPENAI_API_KEY):
        self.model = model
        self.client = OpenAI(api_key=api_key)
        self.token_consumed = 0

    def call_chat(self, messages: List[Dict], return_str: bool = True, **kwargs) -> str:
        # Remove vLLM-specific params
        kwargs.pop("extra_body", None)
        kwargs.pop("n", None)

        completion = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            **kwargs,
        )
        self.token_consumed += completion.usage.total_tokens
        return completion.choices[0].message.content if return_str else completion


# --------------- OpenAI-based Retriever ---------------

class OpenAIRetriever:
    """Simple dense retriever using OpenAI embeddings."""

    def __init__(self, corpus: List[Dict], model: str = EMBED_MODEL, api_key: str = OPENAI_API_KEY):
        self.corpus = corpus
        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.corpus_embeddings = None

    def _embed(self, texts: List[str]) -> np.ndarray:
        response = self.client.embeddings.create(input=texts, model=self.model)
        return np.array([d.embedding for d in response.data], dtype=np.float32)

    def build_index(self):
        print("Building embedding index...")
        texts = [f"{doc['title']}\n{doc['contents']}" for doc in self.corpus]
        self.corpus_embeddings = self._embed(texts)
        print(f"Indexed {len(self.corpus)} documents ({self.corpus_embeddings.shape[1]}-dim embeddings)")

    def search(self, query: str, top_k: int = TOP_K) -> List[Dict]:
        query_emb = self._embed([query])
        # Cosine similarity
        norms_q = np.linalg.norm(query_emb, axis=1, keepdims=True)
        norms_c = np.linalg.norm(self.corpus_embeddings, axis=1, keepdims=True)
        similarity = (query_emb @ self.corpus_embeddings.T) / (norms_q * norms_c.T + 1e-8)
        scores = similarity[0]
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [
            {"doc_id": str(idx), "score": float(scores[idx]), "doc": self.corpus[idx]}
            for idx in top_indices
        ]


# --------------- CoRAG Agent (adapted) ---------------

@dataclass
class RagPath:
    query: str
    past_subqueries: List[str] = field(default_factory=list)
    past_subanswers: List[str] = field(default_factory=list)
    past_doc_ids: List[List[str]] = field(default_factory=list)


def get_generate_subquery_prompt(query, past_subqueries, past_subanswers, task_desc):
    past = ""
    for idx in range(len(past_subqueries)):
        past += f"Intermediate query {idx+1}: {past_subqueries[idx]}\n"
        past += f"Intermediate answer {idx+1}: {past_subanswers[idx]}\n"
    past = past.strip()

    prompt = f"""You are using a search engine to answer the main query by iteratively searching. Given the following intermediate queries and answers, generate a new simple follow-up question that can help answer the main query.

## Previous intermediate queries and answers
{past or 'Nothing yet'}

## Task description
{task_desc}

## Main query to answer
{query}

Respond with a simple follow-up question only, do not explain yourself."""

    return [{"role": "user", "content": prompt}]


def get_generate_intermediate_answer_prompt(subquery, documents):
    context = "\n\n".join(documents)
    prompt = f"""Given the following documents, generate an appropriate answer for the query. DO NOT hallucinate any information. Respond "No relevant information found" if the documents do not contain useful information.

## Documents
{context}

## Query
{subquery}

Respond with a concise answer only."""
    return [{"role": "user", "content": prompt}]


def get_generate_final_answer_prompt(query, past_subqueries, past_subanswers, task_desc, documents=None):
    past = ""
    for idx in range(len(past_subqueries)):
        past += f"Intermediate query {idx+1}: {past_subqueries[idx]}\n"
        past += f"Intermediate answer {idx+1}: {past_subanswers[idx]}\n"
    past = past.strip()

    context = ""
    if documents:
        for idx, doc in enumerate(documents):
            context += f"Doc {idx}: {doc}\n\n"

    prompt = f"""Given the following intermediate queries and answers, generate a final answer for the main query by combining relevant information.

## Documents
{context.strip()}

## Intermediate queries and answers
{past or 'Nothing yet'}

## Task description
{task_desc}

## Main query
{query}

Respond with an appropriate answer only."""
    return [{"role": "user", "content": prompt}]


class CoRagAgent:
    """Simplified CoRAG agent using OpenAI API."""

    def __init__(self, llm: OpenAIClient, retriever: OpenAIRetriever):
        self.llm = llm
        self.retriever = retriever

    def sample_path(
        self, query: str, task_desc: str,
        max_path_length: int = MAX_PATH_LENGTH,
        temperature: float = 0.7,
    ) -> RagPath:
        past_subqueries = []
        past_subanswers = []
        past_doc_ids = []

        for step in range(max_path_length):
            # Generate subquery
            messages = get_generate_subquery_prompt(query, past_subqueries, past_subanswers, task_desc)
            subquery = self.llm.call_chat(messages, temperature=temperature, max_tokens=64)
            subquery = subquery.strip().strip('"')
            print(f"  Step {step+1} subquery: {subquery}")

            # Retrieve
            results = self.retriever.search(subquery)
            doc_ids = [r["doc_id"] for r in results]
            documents = [f"{r['doc']['title']}\n{r['doc']['contents']}" for r in results]

            # Generate intermediate answer
            messages = get_generate_intermediate_answer_prompt(subquery, documents)
            subanswer = self.llm.call_chat(messages, temperature=0.0, max_tokens=128)
            print(f"  Step {step+1} answer: {subanswer[:100]}...")

            past_subqueries.append(subquery)
            past_subanswers.append(subanswer)
            past_doc_ids.append(doc_ids)

        return RagPath(
            query=query,
            past_subqueries=past_subqueries,
            past_subanswers=past_subanswers,
            past_doc_ids=past_doc_ids,
        )

    def generate_final_answer(self, path: RagPath, task_desc: str) -> str:
        messages = get_generate_final_answer_prompt(
            query=path.query,
            past_subqueries=path.past_subqueries,
            past_subanswers=path.past_subanswers,
            task_desc=task_desc,
        )
        return self.llm.call_chat(messages, temperature=0.0, max_tokens=256)


# --------------- Main ---------------

def main():
    print("=" * 60)
    print("CoRAG Test with OpenAI API (no GPU)")
    print("=" * 60)

    if not OPENAI_API_KEY:
        print("ERROR: OPENAI_API_KEY not set. Add it to ../../.env")
        return

    # Initialize
    llm = OpenAIClient()
    retriever = OpenAIRetriever(CORPUS)
    retriever.build_index()

    agent = CoRagAgent(llm=llm, retriever=retriever)

    # Test questions (multi-hop)
    questions = [
        ("Where was the physicist who explained the photoelectric effect born?", "answer multi-hop questions"),
        ("In which city was the first female professor at the University of Paris born?", "answer multi-hop questions"),
    ]

    for query, task_desc in questions:
        print(f"\n{'='*60}")
        print(f"Q: {query}")
        print(f"{'='*60}")

        path = agent.sample_path(query, task_desc, max_path_length=2)
        answer = agent.generate_final_answer(path, task_desc)
        print(f"\nFinal Answer: {answer}")
        print(f"Tokens consumed: {llm.token_consumed}")

    print(f"\n{'='*60}")
    print("CoRAG test complete!")
    print(f"Total tokens consumed: {llm.token_consumed}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()

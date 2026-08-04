import asyncio
import logging
import sys

from nirizan.instrumentation.sdk import init_tracer, trace_span
from nirizan.instrumentation.spans import SpanKind
from nirizan.orchestrator.collector import CollectorExporter, TraceCollector
from nirizan.storage.trace_repository import SQLiteTraceRepository

# Configure standard logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("rag_demo")


# --- Simulated Instrumented RAG Services ---
@trace_span(kind=SpanKind.RETRIEVAL, name="qdrant_vector_search")
async def retrieve_context(query: str) -> list[str]:
    """Simulate fetching relevant documents from a vector store."""
    logger.info("Executing vector lookup for query: '%s'", query)
    await asyncio.sleep(0.05)  # Simulate DB query latency
    return [
        "Doc 1: NiriZan provides thread/async-safe execution context tracing.",
        "Doc 2: Continuous evaluation engines rely on non-blocking trace collectors.",
    ]


@trace_span(kind=SpanKind.GENERATION, name="openai_gpt4_inference")
async def generate_response(query: str, documents: list[str]) -> str:
    """Simulate generating an answer using an LLM."""
    logger.info("Calling LLM with %d context documents...", len(documents))
    await asyncio.sleep(0.1)  # Simulate LLM inference latency
    return f"Based on the context, NiriZan tracks async context for query '{query}'."


@trace_span(kind=SpanKind.PLANNING, name="rag_orchestrator")
async def run_rag_pipeline(user_query: str) -> str:
    """Root orchestrator service coordinating retrieval and generation."""
    logger.info("Starting RAG orchestration pipeline...")
    docs = await retrieve_context(user_query)
    answer = await generate_response(user_query, docs)
    return answer


# --- End-to-End Application Execution ---
async def main() -> None:
    print("=" * 60)
    print("Running NiriZan Instrumented RAG Pipeline Demo")
    print("=" * 60)

    # 1. Initialize persistent storage engine & background collector
    db_filename = "rag_demo_traces.db"
    repository = SQLiteTraceRepository(db_path=db_filename)
    collector = TraceCollector(repository=repository)
    await collector.start()

    # 2. Configure global SDK Tracer with the collector exporter
    exporter = CollectorExporter(collector)
    init_tracer(application_name="rag_pipeline_demo", exporter=exporter)

    # 3. Process sample queries
    queries = [
        "How does NiriZan handle context propagation?",
        "What is the role of the TraceCollector?",
    ]
    for q in queries:
        print(f"\n[User Query]: {q}")
        response = await run_rag_pipeline(q)
        print(f"[LLM Answer]: {response}")

    # 4. Gracefully shutdown collector (flushes background queue)
    print("\nStopping collector and flushing remaining traces to SQLite...")
    await collector.stop()

    # 5. Query and verify persisted traces from storage

    print("\nStorage Verification (Querying SQLite Database):")
    traces = await repository.list_by_application(application_name="rag_pipeline_demo", limit=10)
    print(f"Total Traces Persisted: {len(traces)}\n")

    for idx, trace in enumerate(traces, start=1):
        print(f"Trace #{idx} [ID: {trace.trace_id}] - {len(trace.spans)} Spans Captured")
        for span in trace.spans:
            parent_info = (
                f" (Parent: {str(span.parent_span_id)[:8]}...)"
                if span.parent_span_id
                else " (ROOT)"
            )
            print(
                f"  \u2514\u2500 [{span.kind.value.upper()}] {span.name}{parent_info} | {span.started_at}"
            )

    repository.close()
    print("\nDemo run completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())

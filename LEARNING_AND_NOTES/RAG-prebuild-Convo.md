# NGraph Query System Notes

## Current State

The browser is live, but the answers are not coming from an LLM yet.

What exists now:
- a live local HTTP server
- precomputed evidence artifacts
- a deterministic query engine that runs on demand when a canonical question or manual query is submitted

So the canonical questions are not static HTML answers, but the reasoning path is still rule-based and retrieval-based, not true RAG + LLM generation.

## What Is Actually Running

- The page loads the canonical questions from `CANONICAL_QUERIES` and auto-runs the first one on startup.
- Clicking a canonical question fills the text box and calls `runQuery()` again.
- `runQuery()` sends an HTTP request to `/api/query`, so it is executed at request time, not pre-rendered in the page.
- `/api/query` dispatches to the Python query module.
- The query module then routes the question with string rules.

## What Is Precomputed

These are the prebuilt artifacts that the live query engine reads from disk:
- Evidence cards
- The TF-IDF text retrieval index
- VGAE embedding neighbors
- Saved query report output

So:
- query execution is live
- evidence and indexes are precomputed
- there is no LLM call yet

## How the Current Query Logic Works

- “transition” questions are answered by splitting samples by MIS median and ranking taxa by abundance shifts.
- “seeding” questions are answered by ranking taxa using mean abundance, presence count, and predicted-link degree.
- “functional” questions are answered by grouping selected taxa by annotation fields such as `functional_group`, `ecological_role`, and `tea_primary`.
- general questions fall back to TF-IDF semantic retrieval over evidence cards.

That means the current system can answer, but it is not yet “LLM reasoning over retrieved evidence.”

## How the Evidence Cards Are Used

The evidence cards are the retrieval corpus and provenance layer.

Each card contains:
- `card_type`
- `entity_id`
- `title`
- `summary`
- `evidence`
- `threshold`
- `method`
- `core`
- `taxon`
- `module`
- `relation_type`
- `score`
- `observed_status`
- `source_tables`

In practice, the cards are used in three ways:
- filtered in the browser by card type, threshold, method, and relation
- semantically searched by TF-IDF over card text
- shown as relevant evidence in the query output

## How to Use Them for Real RAG

To turn this into real RAG, the evidence cards become the chunks you feed to the LLM.

The clean architecture is:
- retrieve top evidence cards for the question
- retrieve graph context
- build a compact context packet with provenance
- send that packet to an LLM
- require the LLM to answer only from the retrieved evidence and cite card IDs

A good prompt payload would include:
- question text
- top evidence cards
- top predicted links
- relevant module summaries
- provenance fields and `observed_status`
- explicit instruction to cite `card_id` values and label uncertainty

## What Is Missing for a True LLM-Backed RAG

There is no model client wired in yet.

The missing pieces are:
- an LLM adapter function
- a retrieval orchestrator that packages the card and graph evidence
- a response validator that checks citations and prevents unsupported claims
- optional streaming into the browser UI

## Next Step

The next implementation step is a local-first RAG orchestrator that:
- retrieves evidence cards
- assembles graph context
- prepares a prompt bundle
- keeps the current deterministic answer as the fallback

After that, a Google API key can be used as the demo LLM adapter layer.

When you want to turn the demo on, set:
- `NG_LLM_PROVIDER=gemini`
- `GEMINI_API_KEY` or `GOOGLE_API_KEY`

The adapter will use the lightweight `gemini-3.1-flash-lite` model by default unless you override `NG_GEMINI_MODEL`.

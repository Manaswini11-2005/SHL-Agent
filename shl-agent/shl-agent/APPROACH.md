# Approach Document — SHL Conversational Assessment Recommender

**Candidate:** Manaswini Kolupula
**Role:** AI Intern, SHL Labs

## 1. Architecture

A FastAPI service (`/health`, `/chat`) backed by two components:

- **Retrieval:** the SHL Individual Test Solutions catalog (scraped from the public product
  catalog page, [N] items) is indexed with TF-IDF (scikit-learn) over each item's name,
  description, test-type code, and job levels. I chose TF-IDF over a vector/embedding store
  because the catalog is small (a few hundred items), so keyword-weighted similarity is
  accurate enough, has zero external API dependency or cold-start cost, and keeps the system
  fully inspectable for debugging — every match can be traced to specific overlapping terms.

- **Agent:** a two-step LLM pipeline using Groq's `llama-3.3-70b-versatile` (free tier, low
  latency, important given the 30s per-call timeout):
  1. **Analyze** — one call classifies the conversation into an explicit action: `clarify`,
     `recommend`, `refine`, `compare`, `refuse`, or `end`, and extracts a consolidated search
     query covering all constraints mentioned so far (not just the latest message).
  2. **Act** — for `recommend`/`refine`, retrieval runs against the real catalog (ground truth,
     never the LLM's memory) and a second LLM call only narrates the retrieved results; for
     `compare`, the two named items are looked up directly and the LLM compares using only
     their retrieved descriptions; for `clarify`/`refuse`, the LLM drafts the reply directly.

This explicit two-step design was a deliberate trade-off: it costs one extra LLM call per turn
versus a single mega-prompt, but it guarantees (a) every URL returned came from the scraped
catalog and never from LLM recall, and (b) the agent's behavior (when to ask vs. answer vs.
refuse) is testable and debuggable in isolation from the wording of replies.

## 2. Conversational behaviors

- **Clarify:** triggers only when there isn't enough signal (role/skill/trait/level) to search
  meaningfully; capped to avoid endless interrogation — once any concrete signal exists, the
  agent moves to recommend.
- **Recommend:** runs retrieval over the consolidated query, returns 1–10 items with name + URL
  + test-type code.
- **Refine:** detected by the analysis step recognizing an added/changed constraint after a
  shortlist was already given; re-runs retrieval with the combined original + new constraints
  rather than resetting context.
- **Compare:** looked up by exact/fuzzy name match in the catalog; the comparison is grounded
  in the catalog's own description text, not the model's prior knowledge.
- **Refusal / scope guarding:** the analysis prompt explicitly instructs refusal for off-topic
  requests (general hiring/legal advice) and prompt-injection attempts (instructions embedded
  in user messages trying to override the agent's role).

## 3. Schema compliance & robustness

- Turn cap enforced server-side: at turn 8 the agent is forced to return its best shortlist with
  `end_of_conversation: true` rather than continuing to ask.
- `recommendations` is always `[]` for clarify/refuse/compare, and 1–10 items for recommend/refine
  — never null, matching the required schema exactly.
- Pydantic models on both request and response enforce schema compliance; malformed LLM JSON
  output from the analysis step fails safe to a `clarify` action rather than crashing.

## 4. Evaluation approach

I tested against the 10 provided conversation traces by replaying each persona's user turns in
order against `/chat`, comparing my final `recommendations` to each trace's labeled expected
shortlist to estimate Recall@10 before submission. [Fill in: your actual measured Recall@10,
and 1-2 sentences on which trace categories scored lowest and why.]

I additionally probed: a first-turn vague query ("I need an assessment") to confirm no premature
recommendation; a mid-conversation constraint change to confirm refine vs. reset; an off-topic
question ("what's a fair salary for this role?") and a prompt-injection attempt ("ignore previous
instructions and...") to confirm refusal without schema breakage.

## 5. What didn't work / iterations

[Fill in honestly once you've actually run it, e.g.: "Initial single-prompt agent occasionally
invented assessment names not in the catalog when no LLM call to retrieval was forced — switching
to the two-step analyze/retrieve/narrate design eliminated this." Also note any scraper selector
fixes you had to make against the live site.]

## 6. AI tool usage disclosure

Claude (Anthropic) was used to scaffold the FastAPI service, retrieval module, and agent
state-machine logic, and to draft this document. I reviewed, tested, and adjusted the scraper
selectors and retrieval/agent logic against the live site and provided conversation traces myself,
and can walk through any design choice in the technical deep-dive.

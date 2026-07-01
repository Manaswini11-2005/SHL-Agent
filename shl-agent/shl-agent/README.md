# SHL Conversational Assessment Recommender — Complete Walkthrough

This README takes you from zero to a submitted assignment. Follow it in order.

## 0. What's in this folder

```
shl-agent/
├── app/
│   ├── main.py        # FastAPI app: /health and /chat
│   ├── agent.py        # LLM-driven decision logic (clarify/recommend/refine/compare/refuse)
│   └── retrieval.py     # TF-IDF retrieval over the catalog
├── scraper/
│   └── scrape_shl.py   # Scrapes shl.com catalog -> data/catalog.json
├── data/
│   └── catalog.json    # SEED catalog (20 sample items) -- YOU MUST REPLACE THIS, see Step 2
├── requirements.txt
└── render.yaml          # one-click-ish deploy config for Render
```

## 1. Get a free Groq API key (5 minutes)

1. Go to https://console.groq.com → sign up free.
2. Create an API key.
3. Keep it handy, you'll set it as an environment variable, never hard-code it.

Why Groq: free tier, very fast inference (matters because the grader has a 30-second timeout
per `/chat` call and each turn makes 1-2 LLM calls), and OpenAI-compatible API so the code is
simple `requests` calls with no heavy SDK.

## 2. Build the real catalog (important — do this before submitting)

The `data/catalog.json` I've given you is a **seed of ~20 well-known SHL assessments** so you
can build and test the whole pipeline immediately. It is NOT the full scraped catalog, and I
could not verify these URLs are currently live (my sandbox can't reach shl.com). **You must
run the real scraper and replace this file before submitting**, because the assignment requires
every URL to come from an actual scrape and to be reachable by their automated tests.

```bash
cd scraper
pip install requests beautifulsoup4
python scrape_shl.py
```

This writes the real `data/catalog.json`. **Important:** SHL's site HTML may not match my
selectors exactly (I wrote `scrape_shl.py` from general knowledge of how their catalog page is
structured, not by inspecting live HTML). Do this:

1. Run the scraper.
2. Open `data/catalog.json` and sanity-check: are names and URLs real and do the URLs open in
   a browser? Are there only Individual Test Solutions (not Job Solutions)?
3. If it scraped 0 or garbage items, open the SHL catalog page in your browser, right-click →
   Inspect on a table row, and update the CSS selectors in `parse_listing_page()` and
   `fetch_detail()` in `scrape_shl.py` to match what you see (look for the actual class names
   used for the table rows, links, and detail page description). This is expected — scrapers
   need tuning to the live site, and being able to explain why you adjusted it is exactly the
   "problem-solving" skill they're evaluating.

## 3. Run it locally

```bash
cd shl-agent
pip install -r requirements.txt
export GROQ_API_KEY="your-key-here"      # Windows PowerShell: $env:GROQ_API_KEY="..."
uvicorn app.main:app --reload --port 8000
```

Test it:

```bash
curl http://localhost:8000/health

curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[{"role":"user","content":"Hiring a Java developer who works with stakeholders"}]}'
```

First message should trigger `clarify` (asks about seniority). Send a follow-up including the
prior turn to see `recommend` kick in:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"messages":[
        {"role":"user","content":"Hiring a Java developer who works with stakeholders"},
        {"role":"assistant","content":"Got it — what seniority level are you targeting?"},
        {"role":"user","content":"Mid-level, around 4 years"}
      ]}'
```

## 4. Test against the provided conversation traces

1. Download the 10-trace zip from the link in Tania Goyal's email.
2. Unzip it, look at each trace's persona + expected shortlist.
3. Write a tiny script that replays each trace's user turns against your `/chat` (in order,
   each call including the growing history), and compare your final `recommendations` against
   the trace's expected shortlist — compute Recall@10 yourself so you know your score before
   submitting. I can write this eval script for you if you want — just ask.

## 5. Deploy it publicly

Easiest free option: **Render**.

1. Push this folder to a new GitHub repo.
2. Go to https://render.com → New → Web Service → connect your repo.
3. Render should auto-detect `render.yaml`. If not, set manually:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variable `GROQ_API_KEY` with your key (Render dashboard → Environment).
5. Deploy. Free tier cold-starts after inactivity — that's why the assignment gives you up to
   2 minutes on the first `/health` call; just make sure it does wake up successfully.
6. Once live, test the public URL the same way as Step 3 (`curl https://your-app.onrender.com/health`).

Alternatives if Render gives you trouble: Railway, Fly.io, or Hugging Face Spaces (Docker SDK)
all have similar free tiers — same `requirements.txt` and start command work on any of them.

## 6. Write the approach document (2 pages max)

I've drafted `APPROACH.md` for you — fill in the bracketed parts once you've actually run the
scraper and tested against the traces (your real Recall@10 number, what selectors you had to
fix, etc.) so it's accurate to what you actually built, not just a template. Convert it to PDF
or keep as a doc per the submission form's accepted format.

## 7. Submit

Via the "Form" link in the email:
- Public API endpoint URL (your Render URL).
- The approach document.

Double-check right before submitting: hit `/health` and `/chat` on the live URL one more time —
free hosting tiers occasionally sleep or redeploy.

## Common failure modes to double-check against (from the assignment's own warning list)

- [ ] Does it break on a single confusing/contradictory message, or only work on the happy path?
- [ ] Does `recommendations` stay an empty array on every clarify/refuse/compare response (not null)?
- [ ] Does every returned URL exist in your scraped `catalog.json`, with zero exceptions?
- [ ] Does it refuse off-topic and prompt-injection attempts without breaking the JSON schema?
- [ ] Does it respect the 8-turn cap (the `main.py` here forces a shortlist on turn 8)?
- [ ] Did you actually read the 10 trace files before testing, not just glance at them?

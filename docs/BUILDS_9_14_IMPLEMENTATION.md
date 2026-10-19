# Builds 9–14: financial intelligence, what-if analysis, and security review

## Build 9 — evidence-backed plain-language brief
The financial brief starts from server-calculated summaries and MarginGuard findings. The deterministic fallback explains only those findings and repeats uncertainty. AI context excludes transaction IDs and free-text descriptions.

## Build 10 — explicit AI boundary
The brief endpoint requires the same workspace membership and both sales:read and expenses:read permissions as the combined financial overview. AI is opt-in per request (use_ai: true), never receives credentials or raw receipt text, and cannot call transaction mutation tools. A missing token, provider error, timeout, or invalid response falls back to the deterministic brief. The AI output is labelled non-authoritative.

## Build 11 — Gemma through Hugging Face
The backend calls Hugging Face's OpenAI-compatible Inference Providers chat endpoint using HF_TOKEN and HF_GEMMA_MODEL. The model name is configurable so providers/models can be replaced without changing the financial engine. The default is google/gemma-3-12b-it:fastest; availability and billing depend on Hugging Face's current model/provider routing. Do not commit the token. A hosted request sends the bounded structured financial summary and user question to Hugging Face; enable it only when the workspace user knowingly chooses AI assistance.

## Build 12 — provider and licence notes
Gemma weights are distributed under the licence/terms shown on the exact selected model card; do not assume all Gemma generations share the same licence. Review Google's Gemma terms and the Hugging Face model card before redistributing weights or making licensing claims. Hugging Face Inference Providers may be pay-as-you-go and can change provider routing/availability. This implementation uses a hosted API and does not download model weights or run inference inside the Exprofit web container. Keep model/provider identifiers configurable and retain the deterministic fallback.

## Build 13 — deterministic what-if simulator
The simulator applies user-supplied price, volume, and unit-cost percentage assumptions to recorded revenue and explicitly recognised direct costs. Price and volume factors are applied to revenue; unit-cost and volume factors are applied to direct costs. It keeps currencies separate, marks profit unknown when direct-cost records are absent, and does not write any transaction. It is sensitivity analysis, not a demand forecast: product mix, tax, operating expenses, stock constraints, seasonality, and customer behaviour are not modelled.

## Build 14 — focused security and QA hardening
Automated tests cover privacy minimisation in AI context, deterministic fallback wording, scenario arithmetic, missing cost data, and non-mutation of scenario inputs. CI continues to run Ruff, pytest, PostgreSQL migration checks, frontend typecheck and production build. Before release, manually test permission-denied requests, provider timeout/unavailability, the mobile UI, and a complete receipt-to-MarginGuard flow. AI-provider integration itself is not claimed as live-tested by CI unless a separately configured credentialed integration test is run.

## Configuration
Set HF_TOKEN only as a server-side environment secret with Inference Providers permission. Optionally set HF_GEMMA_MODEL to a model available to your account. Without HF_TOKEN, the API returns the deterministic brief with ai_status=not_configured.

## Acceptance gates
- [ ] CI passes on the new branch.
- [ ] Owner and authorised members can access briefs/simulations; unauthorized members are denied server-side.
- [ ] AI is opt-in, provider errors degrade to deterministic output, and no token or provider error leaks to the client.
- [ ] Simulator results are repeatable and do not change the ledger.
- [ ] Exact selected Gemma model terms and provider availability are checked before deployment.
- [ ] Manual mobile and deployed workflow checks pass before release.

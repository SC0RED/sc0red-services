## ADDED Requirements

### Requirement: Financial and operating-model facts are derived by decomposed AI research, not templates

The EBITDA tree and value chain SHALL be produced by a pipeline of small, sharply-scoped structured AI calls — not by selecting a hardcoded industry template via keyword match. The deterministic keyword templates (`_ebitda_templates.py`, `value_chain_templates.py`) and their template-selection logic SHALL be removed. Each research call SHALL be a `RequestStep` (or run within one) wired through the company-analysis factory chain, execute via `run_structured_ai_call`, load its prompt and output schema from `src/pipeline/prompts/`, and return a short structured answer.

#### Scenario: Debt-settlement firm yields a success-fee model, not a template

- **WHEN** the pipeline analyses a debt-settlement company (e.g. Century Support Services)
- **THEN** the derived revenue model reflects success-fee economics (a fee on enrolled/settled debt), and the EBITDA revenue mix does NOT contain template artifacts such as "Subscriptions", "Project-Based Revenue / Retainers / Training", or an R&D cost line that the company does not have

#### Scenario: No keyword template is consulted

- **WHEN** any company is analysed
- **THEN** no business-model keyword-to-template lookup occurs and no default industry template is applied

### Requirement: Research questions run as a parallel/sequential DAG

The research SHALL be organised into rounds executed via `FutureManager`: questions with no unmet dependency run in parallel within a round, and a round begins only after its prerequisite round completes. Independent qualitative questions (company type, revenue model, revenue mix, margin band, cost drivers, operating-model steps) and dependent/quantitative questions (revenue range) SHALL be sequenced so each dependent question receives its predecessors' answers.

#### Scenario: Independent questions execute concurrently

- **WHEN** the first research round runs
- **THEN** its independent questions are submitted to a single `FutureManager` and resolved concurrently (no per-question sequential blocking)

#### Scenario: Dependent question waits for its inputs

- **WHEN** the revenue-range question depends on the revenue model and scale signals
- **THEN** it executes only after those answers are available and is passed them as inputs

### Requirement: Assembled facts are adversarially verified

After assembly, the pipeline SHALL run cheap yes/no plausibility checks (the strategy-map verification pattern) against the scraped content for key facts (at minimum the revenue model). An implausible verdict SHALL downgrade the affected fact's confidence; an implausible *revenue model* SHALL cause the financial surface to render the insufficient-data placeholder rather than assert a model.

#### Scenario: Implausible revenue model is rejected

- **WHEN** the verification check returns "not plausible" for the derived revenue model given the scraped content
- **THEN** the EBITDA tree is not asserted with that model — the surface falls to the insufficient-data placeholder

#### Scenario: Plausible facts pass through

- **WHEN** verification returns "plausible" for the derived facts
- **THEN** the facts are retained with their computed confidence

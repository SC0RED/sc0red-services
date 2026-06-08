## ADDED Requirements

### Requirement: Profile existing-fact fields must be grounded or marked unknown

The profile extraction prompt and schema SHALL require that existing-fact fields — `business_model`, `revenue_model`, `company_size` (and other statements of present reality) — be supported by the scraped site content. When the content gives no signal for such a field, the extraction SHALL return an explicit `"unknown"` sentinel rather than guessing a value.

#### Scenario: No site signal for business model

- **WHEN** the scraped content contains no clear evidence of how the company makes money
- **THEN** the extracted `business_model` is `"unknown"` (not a plausible guess)

#### Scenario: Site signal present

- **WHEN** the scraped content clearly indicates the revenue model (e.g. "we charge a success fee on settled debt")
- **THEN** the extracted `business_model` / `revenue_model` reflects that grounded evidence

### Requirement: `company_size` values align with the downstream size map

The profile schema's `company_size` allowed values SHALL match the keys consumed by the EBITDA size map (`Startup <50`, `Small 50-200`, `Mid-market 200-1000`, `Large 1000-5000`, `Enterprise 5000+`), so a validly-extracted size never silently defaults downstream. The schema MUST NOT instruct the model to emit a value (e.g. `"Enterprise 1000+"`) that is absent from the size map.

#### Scenario: Extracted size resolves in the size map

- **WHEN** the AI extracts a `company_size` per the schema's allowed values
- **THEN** that value is a key in `_SIZE_TO_EMPLOYEES` and does not trigger the size default

#### Scenario: Unknown size is explicit

- **WHEN** the scraped content gives no headcount/size signal
- **THEN** `company_size` is `"unknown"` and the downstream FACT surfaces treat it as ungrounded

### Requirement: Ungroundable profile facts flow to the placeholder contract

When a profile existing-fact field is `"unknown"`, downstream FACT builders SHALL treat it as a no-match and render the insufficient-data placeholder rather than a fabricated value, and the customer-visible profile SHALL omit or placeholder the `"unknown"` field rather than displaying the sentinel text.

#### Scenario: Unknown business model drives placeholders downstream

- **WHEN** `business_model` is `"unknown"`
- **THEN** the EBITDA tree and value chain both render the insufficient-data placeholder state
- **AND** the rendered profile does not show the literal `"unknown"` string as a stated fact

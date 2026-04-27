## ADDED Requirements

### Requirement: SQS max_receive_count accommodates throttling under concurrency limits

The SQS redrive policy SHALL have `max_receive_count` high enough that throttled messages (where Lambda never ran) are not sent to DLQ before a worker becomes available.

#### Scenario: 69 messages with 3 concurrent workers

- **WHEN** 69 SQS messages are queued and `reserved_concurrency=3`
- **THEN** all 69 messages are eventually processed — none are sent to DLQ solely due to throttling

### Requirement: All exceptions in company analysis are caught and recorded

The worker SHALL catch ALL exceptions during company analysis (not just domain errors), record the error on the company record, and consume the message. Programming errors SHALL NOT trigger SQS retry.

#### Scenario: AttributeError during scraping

- **WHEN** the pipeline raises `AttributeError` during `ScrapeAndResolveURL`
- **THEN** the error is recorded on the company record, the full traceback is logged to CloudWatch, and the SQS message is consumed (no retry)

#### Scenario: Company shows as FAILED in the UI after programming error

- **WHEN** any exception occurs during company analysis
- **THEN** the company card shows "FAILED" with the error message on the portfolio page

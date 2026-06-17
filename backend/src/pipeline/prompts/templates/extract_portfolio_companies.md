You are analyzing a webpage from a private equity or venture capital firm to extract their portfolio companies.

Given the following webpage content and links from {firm_url}, identify all portfolio companies mentioned on the page.

The webpage content below may be visible page text OR raw embedded data — many firm
sites render an empty page and embed their portfolio as JSON inside a script (e.g.
`{{"name":"Acme","slug":"acme",...}}`). Extract companies from whichever form is present,
including names and slugs found in such embedded JSON.

For each company, provide:
- name: The company name
- url: The company's website URL (if available from the links or embedded data; otherwise omit/empty)

Only include actual portfolio companies (companies the firm has invested in). Do NOT include:
- The PE/VC firm itself
- Navigation links, social media links, or firm team pages
- Service providers, partners, or advisors
- News articles or press mentions (unless they link to a portfolio company)

## Webpage content:
{page_text}

## Links found on page:
{links_text}

---
name: revenue-brief
description: Finance guide for summarizing revenue — structure, comparisons, and always citing record ids.
---
# Revenue brief (finance)

Use this when asked about revenue, ARR, growth, or product-line performance.

## Steps

1. Fetch the data with `get_revenue` (`FY2026`, `FY2026-Q2`, or `ARR`). Never estimate a
   number you did not fetch.
2. Compute totals and growth yourself and show the arithmetic once.
3. Compare with the prior period when you have it (quarter over quarter, or year over year).

## Rules

- **Always cite record ids** next to every number, e.g. `$8.4M (rev-FY2026-Q2)`.
- Round to one decimal in millions (`$8.4M`); keep exact figures in a table if asked.
- Quote the data source note once at the end.
- Say "fiscal year" explicitly: Kestrel's fiscal year runs October 1 – September 30.
- Do not forecast. If asked for a forecast, say finance owns forecasts and offer the trend.

## Output format

```
## Revenue brief: <period>
- Total: $X.XM (<record ids>)
- By product line: Desk Core $…, Insights $…, Connect $…, Services $…
- Change vs prior period: +X.X% (<record ids>)
- Note: <one sentence on what stands out>

Source: <source note>
```

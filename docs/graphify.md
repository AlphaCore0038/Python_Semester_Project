# AI Digital Locker — Graphify Reference

## Artifacts
- Location: `graphify-out/`
- Contents: `graph.json`, `graph.html`, `GRAPH_REPORT.md`, `manifest.json`, cache, labels.
- `graphify-out/` is intentionally dirty and must never be staged or committed.

## Reported generation baseline
- Graph report says built from commit `d7985ae3`.
- The baseline predates Phase 11A and the final UI changes, so the code graph is
  stale; refresh it after code changes.
- Reported coverage: 888 nodes, 1927 edges, 61 communities, 98% EXTRACTED / 2% INFERRED.

## Safe refresh procedure
- After modifying code: `graphify update .` (AST-only, no API cost).
- Do not run `graphify update` solely to refresh docs unless code changed.
- Do not delete or overwrite existing graph artifacts blindly.
- Do not stage `graphify-out/` changes.

## Navigation commands
- `graphify query "<question>"` — scoped subgraph for codebase questions.
- `graphify path "<A>" "<B>"` — relationships (directed call edges).
- `graphify explain "<concept>"` — focused concept subgraph.
- Use `graphify-out/GRAPH_REPORT.md` only for broad architecture review when queries
  do not surface enough context.

## Limitations
- `graphify path` uses directed edges; a missing directed path is not evidence of no
  relationship. Use `query` for broader discovery.
- The graph is a navigation aid, not authoritative over source code or Git history.
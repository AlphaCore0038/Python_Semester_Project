# Graph Report - PythonProject  (2026-10-20)

## Corpus Check
- 14 files · ~14,953 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 127 nodes · 114 edges · 21 communities (16 shown, 5 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `bff2e68e`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- AI_Digital_Locker_Project_Specification(2).md
- What You Must Do When Invoked
- /graphify
- graphify reference: extra exports and benchmark
- AI Digital Locker
- 14. AI Capabilities
- graphify reference: query, path, explain
- 12. AI Assistant
- opencode.json
- graphify reference: add a URL and watch a folder
- graphify reference: commit hook and native CLAUDE.md integration
- graphify reference: incremental update and cluster-only
- AI Digital Locker
- 21. Supabase
- 3. User Accounts
- 5. Document Storage
- graphify.js
- graphify reference: GitHub clone and cross-repo merge
- graphify reference: transcribe video and audio
- AGENTS.md
- extraction-spec.md

## God Nodes (most connected - your core abstractions)
1. `What You Must Do When Invoked` - 12 edges
2. `/graphify` - 10 edges
3. `graphify reference: extra exports and benchmark` - 8 edges
4. `14. AI Capabilities` - 7 edges
5. `AI Digital Locker` - 7 edges
6. `graphify reference: query, path, explain` - 5 edges
7. `Step 3 - Extract entities and relationships` - 4 edges
8. `graphify reference: add a URL and watch a folder` - 3 edges
9. `graphify reference: commit hook and native CLAUDE.md integration` - 3 edges
10. `graphify reference: incremental update and cluster-only` - 3 edges

## Surprising Connections (you probably didn't know these)
- None detected - all connections are within the same source files.

## Import Cycles
- None detected.

## Communities (21 total, 5 thin omitted)

### Community 0 - "AI_Digital_Locker_Project_Specification(2).md"
Cohesion: 0.08
Nodes (25): 10. File Access, 11. Offline Storage, 13. AI User Interface, 15. AI and Document Modification, 16. AI and Backend Access, 17. AI Installation and Availability, 18. Web Application, 19. Desktop Application (+17 more)

### Community 1 - "What You Must Do When Invoked"
Cohesion: 0.13
Nodes (15): Part A - Structural extraction for code files, Part B - Semantic extraction (parallel subagents), Part C - Merge AST + semantic into final extraction, Step 0 - GitHub repos and multi-path merge (only if a URL or several paths), Step 1 - Ensure graphify is installed, Step 2.5 - Video and audio (only if video files detected), Step 2 - Detect files, Step 3 - Extract entities and relationships (+7 more)

### Community 2 - "/graphify"
Cohesion: 0.20
Nodes (9): For /graphify add and --watch, For /graphify query, For the commit hook and native CLAUDE.md integration, For --update and --cluster-only, /graphify, Honesty Rules, Interpreter guard for subcommands, Usage (+1 more)

### Community 3 - "graphify reference: extra exports and benchmark"
Cohesion: 0.22
Nodes (8): graphify reference: extra exports and benchmark, Step 6b - Wiki (only if --wiki flag), Step 7 - Neo4j export (only if --neo4j or --neo4j-push flag), Step 7a - FalkorDB export (only if --falkordb or --falkordb-push flag), Step 7b - SVG export (only if --svg flag), Step 7c - GraphML export (only if --graphml flag), Step 7d - MCP server (only if --mcp flag), Step 8 - Token reduction benchmark (only if total_words > 5000)

### Community 4 - "AI Digital Locker"
Cohesion: 0.25
Nodes (7): AI Digital Locker, Architecture, Configuration and secrets, Development status, License / scope, Repository layout, Setup (once application phases begin)

### Community 5 - "14. AI Capabilities"
Cohesion: 0.29
Nodes (7): 14. AI Capabilities, Document Assistance, Document Reading, Filename Suggestions, Information Retrieval, Search, Summarization

### Community 6 - "graphify reference: query, path, explain"
Cohesion: 0.33
Nodes (5): For /graphify explain, For /graphify path, graphify reference: query, path, explain, Step 0 — Constrained query expansion (REQUIRED before traversal), Step 1 — Traversal

### Community 7 - "12. AI Assistant"
Cohesion: 0.40
Nodes (5): 12. AI Assistant, AI Options, Cloud AI — OpenRouter, Local AI — Placeholder Only, Privacy and Scope

### Community 8 - "opencode.json"
Cohesion: 0.50
Nodes (3): plugin, $schema, .opencode/plugins/graphify.js

### Community 9 - "graphify reference: add a URL and watch a folder"
Cohesion: 0.50
Nodes (3): For /graphify add, For --watch, graphify reference: add a URL and watch a folder

### Community 10 - "graphify reference: commit hook and native CLAUDE.md integration"
Cohesion: 0.50
Nodes (3): For git commit hook, For native CLAUDE.md integration, graphify reference: commit hook and native CLAUDE.md integration

### Community 11 - "graphify reference: incremental update and cluster-only"
Cohesion: 0.50
Nodes (3): For --cluster-only, For --update (incremental re-extraction), graphify reference: incremental update and cluster-only

### Community 12 - "AI Digital Locker"
Cohesion: 0.67
Nodes (3): 1. Project Overview, 2. Main Goals, AI Digital Locker

### Community 13 - "21. Supabase"
Cohesion: 0.67
Nodes (3): 21. Supabase, PostgreSQL Database, Storage

### Community 14 - "3. User Accounts"
Cohesion: 0.67
Nodes (3): 3. User Accounts, Example, Registration and Login

### Community 15 - "5. Document Storage"
Cohesion: 0.67
Nodes (3): 5. Document Storage, Cloud Storage, Storage Limit

## Knowledge Gaps
- **90 isolated node(s):** `$schema`, `.opencode/plugins/graphify.js`, `Usage`, `What graphify is for`, `Step 0 - GitHub repos and multi-path merge (only if a URL or several paths)` (+85 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 102 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **5 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `14. AI Capabilities` connect `14. AI Capabilities` to `AI_Digital_Locker_Project_Specification(2).md`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Why does `What You Must Do When Invoked` connect `What You Must Do When Invoked` to `/graphify`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **What connects `$schema`, `.opencode/plugins/graphify.js`, `Usage` to the rest of the system?**
  _90 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `AI_Digital_Locker_Project_Specification(2).md` be split into smaller, more focused modules?**
  _Cohesion score 0.07692307692307693 - nodes in this community are weakly interconnected._
- **Should `What You Must Do When Invoked` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._
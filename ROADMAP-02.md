# ROADMAP — Y-GN (Yggdrasil‑Grid Nexus)

**Version**: 0.2 (draft)  
**Last updated**: 2026-02-19  
**Purpose**: fournir une roadmap *exécutable* (YAML) + une source de référence détaillée et sourcée pour une équipe d’agents Claude Code.

---

## 0) TL;DR

Y‑GN vise à fusionner :

- **NEXUS (branche NX‑CG)** comme *control‑plane cognitif* (FSM + HiveMind + Hybrid Swarm + Evidence Packs + gouvernance)  
- **ZeroClaw** comme *data‑plane d’exécution* (runtime Rust, canaux, tunnels, outils, sandbox, mémoire low‑footprint, hardware)

…pour produire un **runtime multi‑agents distribué**, orienté **sécurité** et **observabilité**, capable d’opérer localement, en edge, et en cloud.

> **Important (qualité des sources)** : la proposition “Gemini” que tu as fournie contient des idées solides (µACP, SwiftMem, Zep/Graphiti, MCP‑SandboxScan, SandCell, EvoConfig, Live‑SWE‑agent), mais elle mélange aussi des éléments non présents dans NX‑CG (ex: CGAN/équations physiques). Dans Y‑GN, on conserve les idées *transposables* et on écarte les hypothèses incompatibles avec les deux codebases.


## 0.1 Autonomie : ce que ROADMAP.md permet (et ce qu’elle ne garantit pas)

Cette roadmap est conçue comme **entrée unique** pour une équipe d’agents (Claude Code + sous‑agents).  
Elle est **très proche** d’être suffisante pour un développement autonome, *à condition* d’appliquer une discipline “facts-first” :

- **Fact Pack obligatoire (M0)** : inventaire + “confirmé vs hypothèses”, avec *chemins de fichiers* et *SHA* des repos sources.
- **Environnement reproductible** : versions figées (Rust toolchain, Python), commandes standard (`make/just`) + CI identique au local.
- **Scénarios E2E “golden path”** : 2–3 démos minimales automatisées (CLI + 1 canal + 1 tool + evidence pack + mémoire).
- **Contrats formels** : schémas config + protocole Brain↔Core + versioning.
- **Runbooks** : démarrage, debug, sécurité, release.

➡️ **Règle d’or pour Claude Code** : si une hypothèse de ce document n’est pas confirmée par le code, **mettre à jour `docs/FACT_PACK.md`** et ajuster le YAML *avant* d’implémenter.


---

## 1) Fondations factuelles (ce que font réellement les deux repos)

### 1.1 NEXUS NX‑CG — ce qu’on garde
**Objectif constaté** : NX‑CG (“Cognitive Grid”) pousse NEXUS vers une plateforme d’intelligence collaborative **auditable** (Evidence Packs), orchestrée par `OrchestratorV7` + pipeline HiveMind en 7 phases, avec un essaim hybride multi‑modes (Parallel/Sequential/RedBlue/PingPong/LeadSupport/Specialist).  
Référence interne recommandée : audit technique NX‑CG (2026‑02‑17).  
➡️ Keep (prioritaire) :
- Orchestration : FSM + HiveMind (7 phases) + HybridSwarmEngine
- Validation/qualité : TieredValidator (funnel), guards, red‑team tests
- Observabilité : OpenTelemetry + analytics
- Mémoire : backends hybrides + decay + context compression
- Interop : MCP server/client + “Google A2A protocol” route (à confirmer dans le code)
- “Evidence Pack” (traçabilité / provenance)

⚠️ À réduire / refactor :
- “God object” `OrchestratorV7` et duplications legacy/v2 (extraits audit NX‑CG)

### 1.2 ZeroClaw — ce qu’on garde
**Objectif constaté** : runtime Rust “small & fast”, architecture par traits (providers/channels/tools/memory/…) + CLI/daemon/gateway, tunnels, hardware/peripherals, mémoire SQLite, observabilité (OTLP), et une posture “secure by design”.  
➡️ Keep (prioritaire) :
- Socle CLI + daemon + gateway Axum
- Subsystems par traits (providers / channels / tools / memory / security / runtime)
- Canaux + tunnels (matrix/telegram/discord/… + cloudflared/tailscale/ngrok)
- Skill / skills + registre d’outils
- Mécanismes OS‑level (landlock feature, sandbox)
- Memory engine (SQLite) + caches
- Hardware/peripherals + robot-kit (phase “incarnation”, plus tard)

⚠️ Contraintes légales & branding :
- MIT + Apache‑2.0 (dual license) + notice trademark : ne pas réutiliser le branding “ZeroClaw” dans Y‑GN.

---

## 2) Architecture cible Y‑GN (au‑delà de la fusion)

### 2.1 Principe directeur
**Séparer “raisonnement” et “action”** :

- **YGN‑Brain (Python)** : planification, multi‑agents, gouvernance, scoring, Evidence Packs.
- **YGN‑Core (Rust)** : exécution d’outils, canaux, tunnels, sandboxing, mémoire performante, hardware.

Cette séparation :
- protège le système (surface d’attaque réduite côté “action”)  
- permet de déployer “brain” en cloud et “core” en edge  
- rend possible un **Internet of Agents** (IoA) multi‑machines (voir arXiv IoA)

### 2.2 Contrat Brain ↔ Core
On standardise l’intégration autour de 3 couches :

1) **MCP** comme protocole d’outillage (tool discovery + tool calls).  
2) **A2A** (si confirmé utile) comme protocole agent‑to‑agent entre instances.  
3) **µACP** en option pour nœuds très contraints (microcontrôleurs / liens instables) :
   - 4 verbes : `PING`, `TELL`, `ASK`, `OBSERVE`
   - encodage compact (transport‑agnostic)

### 2.3 Sécurité “multi‑parois”
- Sandbox d’exécution **WASM/WASI** + runtime analysis (MCP‑SandboxScan)  
- OS sandboxing Linux (landlock/bwrap/firejail) quand disponible  
- Approvals / allowlists / RBAC sur les actions externes (réseau, FS, périphériques)  
- Supply‑chain scanning : analyse comportementale runtime (HeteroGAT‑Rank) pour skills/paquets “non‑trusted”  
- Option : isolation “intra‑Rust” inspirée SandCell (à implémenter sous forme de boundaries + policy)

### 2.4 Mémoire de nouvelle génération (RAG + Temporal KG)
On vise une mémoire à trois étages :

- **Hot** : cache sémantique/TTL pour interactions récentes  
- **Warm** : index temporel + tags hiérarchiques (SwiftMem)  
- **Cold** : **Temporal Knowledge Graph** (Zep/Graphiti) + doc store + embeddings

La récupération (retrieval) doit pouvoir basculer sur une stratégie “HippoRAG” (KG + Personalized PageRank) pour les tâches multi‑hop / reasoning lourd.

### 2.5 Boucles d’auto‑amélioration (avec garde‑fous)
- **Live‑SWE‑agent** inspire la capacité à *évoluer le scaffold* pendant l’exécution
- **EvoConfig** inspire la capacité à *auto‑réparer / auto‑configurer l’environnement* (CI + runtime)
- Dans Y‑GN : ces boucles sont **gated** par tests, sandbox, et politiques d’approbation.

---

## 3) Mode d’exécution “Claude Code multi‑agents”

### 3.1 Réglage minimal recommandé (agent teams + subagents)
- Utiliser **Subagents** pour découper les responsabilités (Rust / Python / Sec / Memory / Observability / Docs).
- Activer **Agent Teams** (feature expérimentale) uniquement si nécessaire ; sinon simuler un team via worktrees + subagents.

> Référence : docs officielles “agent teams” et “subagents” de Claude Code (attention : expérimental, désactivé par défaut).

### 3.2 Règles de collaboration (anti‑chaos)
- **Un worktree par epic** (pas de concurrence sur les mêmes fichiers).
- **TDD obligatoire** : aucun code “métier” sans tests (pytest/cargo test).
- **Gates** : fmt/lint/tests/security + “demo scenario” à chaque milestone.
- **Docs synchronisées** : toute décision non triviale → ajout au “Decision Log”.

---

## 4) Roadmap exécutable (YAML)

Le bloc YAML ci‑dessous est la “source of truth” pour Claude Code.

```yaml
project:
  id: YGN
  name: "Y-GN"
  codename: "Yggdrasil-Grid Nexus"
  last_updated: "2026-02-19"
  repos:
    nexus:
      url: "https://github.com/yannabadie/NEXUS/tree/NX-CG"
      notes:
        - "Ignorer le dossier archives (hors scope)."
        - "NX-CG = Cognitive Grid (audit interne du 2026-02-17)."
    zeroclaw:
      url: "https://github.com/zeroclaw-labs/zeroclaw"
  scope:
    mvp:
      - "Un agent utilisable en CLI + daemon, capable de recevoir une requête (CLI ou Telegram), planifier via Brain, exécuter via Core, produire un Evidence Pack, et persister la mémoire."
      - "Sandbox WASM/WASI opérationnelle pour exécuter des tools non-trusted."
    non_goals_initial:
      - "Reproduire toute l'UI React de NEXUS (optionnel, post-MVP)."
      - "Support complet de tous les canaux dès le MVP (on démarre par 1-2 canaux)."
  quality_gates:
    rust:
      - "cargo fmt --check"
      - "cargo clippy -- -D warnings"
      - "cargo test"
    python:
      - "python -m compileall ."
      - "pytest -q"
      - "ruff check ."
      - "mypy ."
    security:
      - "deny (Rust) + pip-audit (Python) + secret scan"
      - "sandbox escape tests"
      - "SSRF/path traversal/prompt-injection regression suite"
    observability:
      - "OpenTelemetry traces emitted (brain+core) on happy-path + error-path"
  agent_team:
    # Aligné avec la doc Claude Code (agent teams + subagents).
    roles:
      - id: RUST_CORE
        name: "@RustCoreLead"
        focus: ["ygn-core", "gateway", "channels", "runtime", "config", "release"]
      - id: PY_BRAIN
        name: "@PyBrainLead"
        focus: ["ygn-brain", "orchestration", "swarm", "evidence", "governance"]
      - id: SEC
        name: "@SecurityLead"
        focus: ["sandbox", "policies", "supply-chain", "threat-model"]
      - id: MEMORY
        name: "@MemoryLead"
        focus: ["sqlite/fts/vector", "temporal KG", "swiftmem-like indexing", "benchmarks"]
      - id: OBS
        name: "@ObservabilityLead"
        focus: ["otel", "metrics", "profiling", "dashboards"]
      - id: DOCS
        name: "@DocsReleaseLead"
        focus: ["ROADMAP", "DECISIONS", "user docs", "release checklist"]
    coordination_rules:
      - "1 epic = 1 worktree"
      - "No cross-epic refactor unless agreed in Decision Log"
      - "Stop-the-line si un gate échoue"

milestones:
  - id: M0
    name: "Bootstrap Y-GN"
    goal: "Monorepo propre, CI verte, agent-team opérationnel."
    demo: "CI passe; `make test` exécute rust+python gates; docs de démarrage OK."
  - id: M1
    name: "Core usable (Rust)"
    goal: "ygn-core compile/run: config + provider minimal + gateway stub."
    demo: "`ygn-core status` + `ygn-core gateway` démarrent; health endpoint OK."
  - id: M2
    name: "Brain usable (Python)"
    goal: "ygn-brain exécute un tour HiveMind minimal et produit un Evidence Pack."
    demo: "`python -m ygn_brain.repl` répond et écrit un evidence pack JSONL."
  - id: M3
    name: "Brain↔Core integration"
    goal: "Contrat stable (MCP ou HTTP) + 1 tool call end-to-end."
    demo: "Brain appelle Core pour exécuter un tool 'echo' sandboxé; logs + traces."
  - id: M4
    name: "Secure tool execution"
    goal: "WASM/WASI sandbox + policies + exploit tests."
    demo: "Tentative d'accès réseau/FS non autorisée bloquée + evidence pack."
  - id: M5
    name: "Memory v1"
    goal: "Mémoire unifiée (hot/warm/cold) + persistance + retrieval benchmark."
    demo: "Rappel cross-session + latency mesurée + tests long-memory."
  - id: M6
    name: "IoA / Distributed swarm (v1)"
    goal: "Registry + messaging + 2 nodes (local+remote) coopèrent."
    demo: "Un node edge reçoit (Telegram) → brain remote planifie → core edge agit."
  - id: M7
    name: "Self-healing + self-evolution (safe)"
    goal: "Boucle d'auto-réparation gated (EvoConfig-like) + scaffold evolution gated (Live-SWE-like)."
    demo: "Build cassé → auto-diagnostic → fix PR local → gates passent."
  - id: M8
    name: "Release ready"
    goal: "Install docs + examples + smoke tests + packaging."
    demo: "Nouvel utilisateur installe et lance en <10 min."

epics:
  - id: E0
    name: "Repo, gouvernance, licences, sécurité de base"
    milestone: M0
    tasks:
      - id: YGN-0000
        title: "Geler les sources + produire un Fact Pack (ground truth)"
        owner: DOCS
        description: |
          Objectif: éliminer le risque “on croit que…”. Tout doit être tracé.
          - Cloner les 2 repos (NEXUS@NX-CG, ZeroClaw@main) et noter les SHA (fichiers: docs/SOURCE_LOCK.md).
          - Exécuter build/tests upstream (ou capturer précisément l'erreur si impossible).
          - Produire docs/FACT_PACK.md avec:
              - Confirmed (faits vérifiés + liens vers chemins de fichiers)
              - Assumptions (hypothèses de cette roadmap à valider)
              - Open Questions / TODO
          - Produire docs/INVENTORY.md: arborescence, langages, entrypoints, crates/packages, configs, scripts.
        acceptance:
          - "docs/SOURCE_LOCK.md contient les SHA + date + commande de clone."
          - "docs/FACT_PACK.md contient Confirmed/Assumptions/TODO (>= 10 items)."
          - "docs/INVENTORY.md généré (>= 1 page)."

      - id: YGN-0004
        title: "Matrice de fusion (capabilities map) + plan de dépréciation"
        owner: DOCS
        description: |
          Construire une matrice “Keep / Merge / Drop” et la tenir à jour.
          - Produire docs/CAPABILITY_MATRIX.md:
              colonnes: Capability | Source (NEXUS/ZeroClaw) | Keep/Merge/Drop | Notes | Target module.
          - Identifier collisions (mémoire, outils, channels, runtime) et proposer stratégie:
              - Adapter (wrap) vs Rewrite vs Vendor+patch.
          - Ajouter au Decision Log les 3 décisions de merge les plus structurantes.
        acceptance:
          - "docs/CAPABILITY_MATRIX.md contient >= 30 lignes."
          - "DECISIONS.md a au moins 3 entrées de merge/priorités."

      - id: YGN-0001
        title: "Créer monorepo Y-GN + conventions"
        owner: DOCS
        description: |
          Initialiser repo 'y-gn' avec 2 racines:
            - ygn-core/ (Rust workspace)
            - ygn-brain/ (Python package)
          Ajouter: CLAUDE.md, AGENTS.md, CONTRIBUTING.md, CODEOWNERS, LICENSE, TRADEMARK.md (si nécessaire).
        acceptance:
          - "Structure créée, README minimal."
          - "Instructions Claude Code présentes et testées."
      - id: YGN-0002
        title: "Décision licensing + branding"
        owner: DOCS
        description: |
          Statuer sur:
            - licence Y-GN (compatibilité avec ZeroClaw MIT/Apache + trademark)
            - statut du code NEXUS (propriétaire → re-licensing interne si besoin)
            - interdiction d'utiliser les marques ZeroClaw
        acceptance:
          - "DECISIONS.md: décision + rationale + plan d'action."
      - id: YGN-0003
        title: "CI/CD initial (Rust + Python)"
        owner: OBS
        description: |
          Ajouter pipelines: fmt/lint/test + security scans.
          Fournir commande locale 'make test' ou 'just test'.
        acceptance:
          - "CI verte sur main."
          - "Commandes locales documentées."

  - id: E1
    name: "YGN-Core — extraction et durcissement du socle ZeroClaw"
    milestone: M1
    tasks:
      - id: YGN-0101
        title: "Fork/Import ZeroClaw → ygn-core"
        owner: RUST_CORE
        description: |
          Importer l'architecture par modules (agent/config/gateway/channels/runtime/security/memory).
          Renommer binaire 'ygn-core' et namespace crate.
        acceptance:
          - "`cargo build -p ygn-core` OK."
          - "`ygn-core --help` OK."
      - id: YGN-0102
        title: "Config schema + identity (AIEOS compatible)"
        owner: RUST_CORE
        description: |
          Conserver l'approche config + JSON schema export.
          Ajouter champs 'ygn.node_role' (edge/core/brain-proxy) et 'trust_tier' (trusted/untrusted).
        acceptance:
          - "`ygn-core config schema` produit un schema valide."
      - id: YGN-0103
        title: "Gateway minimal + health + OTLP"
        owner: OBS
        description: |
          Exposer endpoints:
            - GET /health
            - GET /metrics (si prometheus)
            - OTLP traces (stdout exporter en dev)
        acceptance:
          - "curl /health → 200"
          - "une trace OTLP sur 1 requête"

  - id: E2
    name: "YGN-Brain — extraction NEXUS en 'brain package' minimal"
    milestone: M2
    tasks:
      - id: YGN-0201
        title: "Créer package ygn-brain (Python) + deps minimal"
        owner: PY_BRAIN
        description: |
          Extraire de NEXUS uniquement:
            - core/fsm
            - core/hive_mind
            - core/swarm/hybrid_swarm_engine (+ executors)
            - core/security (guards essentiels)
            - core/telemetry (OTel)
            - core/memory (subset)
            - evidence pack generator (nexus_research.py logic)
          Écarter UI, API complète, docs legacy.
        acceptance:
          - "`python -m ygn_brain.repl` démarre."
          - "1 tour 'diagnosis→analysis→plan' fonctionne en offline stub."
      - id: YGN-0202
        title: "Décomposer OrchestratorV7 (anti-God-object)"
        owner: PY_BRAIN
        description: |
          Appliquer la recommandation de l'audit NX-CG:
          Orchestrator devient un Mediator léger et délègue à:
            - StateMachineHandler
            - TaskRouter
            - ContextBuilder
            - GuardPipeline
            - TaskExecutor
        acceptance:
          - "Couverture tests autour des responsabilités isolées."
      - id: YGN-0203
        title: "Evidence Pack v1 (format stable)"
        owner: DOCS
        description: |
          Définir un schéma d'Evidence Pack stable:
            - inputs
            - decisions (routing, model choices)
            - tool calls (with policy decisions)
            - sources (hashes)
            - outputs
            - telemetry correlation ids
        acceptance:
          - "Schema JSON + validate test."
          - "1 exécution écrit un evidence pack valide."

  - id: E3
    name: "Contrat Brain↔Core (MCP-first) + 1 tool end-to-end"
    milestone: M3
    tasks:
      - id: YGN-0301
        title: "Choisir protocole d’intégration v1 (MCP vs HTTP)"
        owner: DOCS
        description: |
          Décider officiellement: on part MCP-first pour tools.
          Documenter fallback HTTP si nécessaire.
        acceptance:
          - "DECISIONS.md mis à jour."
      - id: YGN-0302
        title: "Implémenter ygn-core MCP server minimal"
        owner: RUST_CORE
        description: |
          Exposer 1 tool: 'echo(text)->text' + 'system.health()'.
          Supporter discovery + invocation.
        acceptance:
          - "Client MCP Python peut découvrir + appeler echo."
      - id: YGN-0303
        title: "Adapter ygn-brain en MCP client"
        owner: PY_BRAIN
        description: |
          Utiliser un client MCP (reprendre client NEXUS si adapté) pour appeler le tool echo.
        acceptance:
          - "E2E: Brain reçoit input → plan → appelle echo → réponse."

  - id: E4
    name: "Sandbox & policies (WASM/WASI + MCP-SandboxScan-like)"
    milestone: M4
    tasks:
      - id: YGN-0401
        title: "Runtime WASM/WASI dans ygn-core"
        owner: SEC
        description: |
          Ajouter wasmtime (ou équivalent) et exécuter des modules WASM en WASI strict.
          Définir profils: no-net, net, read-only-fs, scratch-fs.
        acceptance:
          - "Un module WASM hello world s'exécute."
          - "Un module qui tente réseau est bloqué en no-net."
      - id: YGN-0402
        title: "Scanner/rapport d'exposition runtime (inspiré MCP-SandboxScan)"
        owner: SEC
        description: |
          Avant d'approuver un tool WASM:
            - exécuter en sandbox
            - tracer 'external -> sink' (FS, net, commands)
            - produire un rapport attaché à l'Evidence Pack
        acceptance:
          - "Rapport généré et stocké."
      - id: YGN-0403
        title: "Policies unifiées (action allowlists + approvals)"
        owner: SEC
        description: |
          Unifier:
            - allowlists (channels identities)
            - RBAC (si multi-user)
            - approvals tool-level
        acceptance:
          - "1 action classée HIGH-RISK demande approval explicite."

  - id: E5
    name: "Mémoire unifiée v1 (SwiftMem-like + Zep/Graphiti-like) + HippoRAG mode"
    milestone: M5
    tasks:
      - id: YGN-0501
        title: "Design mémoire 3 tiers (hot/warm/cold) + API"
        owner: MEMORY
        description: |
          Définir API MemoryService:
            - put(event)
            - search(query, time_range?, tags?)
            - get_context(session_id)
            - decay()
        acceptance:
          - "Contrat documenté + tests."
      - id: YGN-0502
        title: "Index temporel + tags hiérarchiques (SwiftMem-inspired)"
        owner: MEMORY
        description: |
          Implémenter:
            - index temporel (range queries)
            - index tags (DAG/hiérarchie)
            - co-consolidation (réorganisation) en batch
        acceptance:
          - "Bench: recherche sub-linéaire vs baseline naive sur dataset synthétique."
      - id: YGN-0503
        title: "Temporal Knowledge Graph store (Zep/Graphiti-inspired) — MVP"
        owner: MEMORY
        description: |
          Implémenter un store graphe minimal:
            - nodes/entities
            - edges/relations
            - timestamps + validity
          + bridging depuis logs conversation + tool calls.
        acceptance:
          - "Requête: retrouver faits cross-session + chronologie."
      - id: YGN-0504
        title: "Retrieval HippoRAG mode (KG + PPR)"
        owner: MEMORY
        description: |
          Ajouter un mode retrieval:
            - construire sous-graphe pertinent
            - Personalized PageRank pour scoring
        acceptance:
          - "Test: multi-hop QA gagne vs baseline sur mini-benchmark."

  - id: E6
    name: "Internet of Agents (IoA) + µACP optional"
    milestone: M6
    tasks:
      - id: YGN-0601
        title: "Registry & discovery des nodes"
        owner: RUST_CORE
        description: |
          Implémenter un registry (local file + optional redis/postgres):
            - node_id
            - role (brain/core/edge)
            - endpoints (mcp/http)
            - trust tier
        acceptance:
          - "2 nodes se découvrent et échangent un ping."
      - id: YGN-0602
        title: "Teaming dynamique + conversation flow control (IoA-inspired)"
        owner: PY_BRAIN
        description: |
          Dans ygn-brain:
            - choisir dynamiquement un team d'agents (local/remote)
            - contrôler le flow (who speaks when) pour éviter echo-chambers
        acceptance:
          - "Démo: un problème est résolu via 2 nodes hétérogènes."
      - id: YGN-0603
        title: "Implémenter µACP codec (Rust + Python) en feature flag"
        owner: SEC
        description: |
          Ajouter un codec µACP:
            - framing + parsing
            - 4 verbes PING/TELL/ASK/OBSERVE
          Fournir property-based tests (proptest/hypothesis).
        acceptance:
          - "Interop Rust<->Python sur 1000 messages aléatoires."
          - "Fuzzing: pas de crash sur corpus."

  - id: E7
    name: "Embodiment / Hardware (robot-kit) + Safety"
    milestone: M6
    tasks:
      - id: YGN-0701
        title: "Simulateur hardware (avant matériel réel)"
        owner: RUST_CORE
        description: |
          Fournir un backend 'sim' pour:
            - drive
            - sense
            - look (stub image)
            - speak (text-to-speech stub)
        acceptance:
          - "Brain peut déclencher une action simulée via toolcall."
      - id: YGN-0702
        title: "Interface VLA (OpenVLA) — expérimental"
        owner: PY_BRAIN
        description: |
          Définir un adapter VLA:
            - input: image + instruction
            - output: action tensors -> mapped to robot-kit actions
          Garder en expérimental (hors MVP).
        acceptance:
          - "Démo offline sur dataset / stub model."

  - id: E8
    name: "Self-healing & Self-evolving (gated) — EvoConfig + Live-SWE inspirations"
    milestone: M7
    tasks:
      - id: YGN-0801
        title: "Auto-diagnostic build/runtime (EvoConfig-inspired)"
        owner: OBS
        description: |
          Lorsqu'un gate échoue:
            - collect logs
            - classifier erreur
            - proposer correctif
            - ré-exécuter gates
          Le tout dans un sandbox de dev.
        acceptance:
          - "Cas: dépendance manquante → fix automatique."
      - id: YGN-0802
        title: "Scaffold evolution loop (Live-SWE-inspired) — safe mode"
        owner: PY_BRAIN
        description: |
          Autoriser l'agent à proposer des modifications de son scaffold:
            - modifications limitées à whitelist de fichiers
            - PR locale auto-générée
            - tests + security suite obligatoires
        acceptance:
          - "Un scaffold fix est généré, testé, et appliqué."

  - id: E9
    name: "Release & productization"
    milestone: M8
    tasks:
      - id: YGN-0901
        title: "Installer + quickstart"
        owner: DOCS
        description: |
          Documenter installation:
            - build from source
            - config minimal
            - run CLI + daemon
            - connect 1 channel (telegram)
        acceptance:
          - "Un utilisateur vierge lance une démo en <10 min."
      - id: YGN-0902
        title: "End-to-end smoke scenarios"
        owner: OBS
        description: |
          Ajouter 3 scénarios:
            1) CLI question simple (fast path)
            2) Telegram message -> plan -> toolcall -> réponse
            3) Tool malveillant bloqué + evidence pack
        acceptance:
          - "3 scénarios passent en CI nightly."
```

---

## 5) Decision Log (résumé)

- **On ne fusionne pas “par copier-coller”** : on extrait les cœurs utiles (brain vs core) et on définit un contrat stable.
- **MCP-first** pour le contrat tools (interop et écosystème).
- **WASM/WASI** pour l’exécution d’outils non‑trusted (complété par OS sandbox quand dispo).
- **Mémoire** : on dépasse le vector-store basique via Temporal KG + index query-aware (SwiftMem).
- **Distribué** : IoA + (option) µACP pour edge très contraint.

---

## 6) Sources (à conserver dans le repo)

### Repos
- NEXUS (NX‑CG): https://github.com/yannabadie/NEXUS/tree/NX-CG
- ZeroClaw: https://github.com/zeroclaw-labs/zeroclaw

### Claude Code
- Agent teams: https://code.claude.com/docs/en/agent-teams
- Subagents: https://code.claude.com/docs/en/subagents

### ArXiv (améliorations intégrées)
- IoA: https://arxiv.org/abs/2407.07061
- CodeAct: https://arxiv.org/abs/2402.01030
- HippoRAG: https://arxiv.org/abs/2405.14831
- OpenVLA: https://arxiv.org/abs/2406.09246
- µACP: https://arxiv.org/abs/2601.00219
- SwiftMem: https://arxiv.org/abs/2601.08160
- Zep / Graphiti: https://arxiv.org/abs/2501.13956
- Supply-chain behavior mining (HeteroGAT-Rank): https://arxiv.org/abs/2601.06948
- MCP-SandboxScan: https://arxiv.org/abs/2601.01241
- SandCell: https://arxiv.org/abs/2509.24032
- EvoConfig: https://arxiv.org/abs/2601.16489
- Live-SWE-agent: https://arxiv.org/abs/2511.13646

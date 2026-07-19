# PROJECT CONTEXT — ComplianceIQ

**Intelligent Multi-Cloud Compliance Platform — AlexSys Solutions internship**

> Paste this entire block at the start of a new AI agent session. It is the complete working context: no re-explanation needed.

---

## 1. WHO I AM

- **2-month engineering internship** at **AlexSys Solutions**, Casablanca, Morocco.
- Team = a **binôme of two 4th-year cybersecurity engineering students**: **Student A** and **Student B**.
- **I am Student B.** I own the **AI / Application track**: GRC Copilot (RAG), backend API, dashboard.
- **Student A** owns the **Infrastructure / Compliance-engine track**: Terraform IaC, scanning engine, hardening, deployment.
- Supervisors: a **company supervisor** (AlexSys), an **academic supervisor**, and a **GRC supervisor** who validates copilot answer quality.
- Governed by a **Cahier des Charges v3.0** (French). Deliverables: working MVP, internship report, technical documentation, oral defense (*soutenance*).
- Project docs are in **French**; technical discussion in French or English.

### ⏱️ TIMELINE — READ THIS BEFORE PROPOSING ANYTHING
**Only 6 weeks remain.** Weeks below are labelled **R1–R6** (remaining weeks), R6 ending with the report and defense. The original CDC assumed 8 weeks; that buffer is gone. Every proposal must fit 6 weeks for **two students**, not a team.

---

## 2. WHAT COMPLIANCEIQ IS

A **multi-cloud compliance platform** that does four things no single tool in our reference set does together:

1. **Scans** cloud environments against a rule base aligned with ISO 27001 and Moroccan Law 05-20 / DNSSI, producing `Finding`s with evidence.
2. **Explains** every finding in natural language via a **RAG copilot grounded in the regulatory corpus, with verified citations** — the `EnrichedFinding`.
3. **Translates risk**: correlates findings into attack paths, and expresses exposure as a **financial range in MAD** — this is the project's real differentiator.
4. **Proposes remediation** as Terraform, justified by RAG, **never applied automatically**.

The differentiator is **Layer 4**. A scanner alone is a commodity; a scanner that says *"these three findings chain into this attack path, worth roughly X–Y MAD of exposure, and here is the Terraform that fixes it"* is not. Protect Layer 4 when cutting scope.

---

## 3. TARGET ARCHITECTURE (8 LAYERS) vs. 6-WEEK MVP

This is the **final architecture** (per the ComplianceIQ diagram). The MVP column is what we can actually build in R1–R6; everything else is documented as the evolution path in the report.

### Layer 1 — Infrastructure Cloud (IaC), Multi-Cloud
- **Target:** Terraform IaC modules provisioning **AWS + Microsoft Azure + Google Cloud** environments.
- **MVP:** **ONE cloud provider only**, sandbox provisioned and destroyed via Terraform, containing **deliberate misconfigurations** as real scanner targets. Terraform modules written so a second provider is additive, not a rewrite.
- ⚠️ **Which provider is not settled — ask me.** Project history has said OCI, then Azure; the diagram shows AWS/Azure/GCP with AWS drawn first. Do not guess.

### Layer 2 — Moteur de Scanning
- **Target:** complete **YAML rule base** (domains: IAM / Network / Encryption / Logging / Storage, aligned ISO 27001 + Loi 05-20 / DNSSI) → **multi-cloud connectors** (`boto3` for AWS / Azure SDK / GCP SDK) → normalization → **Rule Engine** (`NormalizedResource` → `Finding`) → **Scoring engine** (`ComplianceScore` global, per domain, per cloud, per tenant).
- **MVP:** ~20–30 YAML rules across all five domains; **one** connector; the `NormalizedResource` → `Finding` abstraction kept in full (it is what makes multi-cloud additive later); scoring **global + per domain** only (per-cloud and per-tenant deferred).
- **Owner:** Student A.

### Layer 3 — Copilot GRC (Generative AI / RAG) — MY MAIN DELIVERABLE
- **Target pipeline:** Regulatory corpus (**ISO 27001, Loi 05-20, DNSSI, NIST, SOC 2**) → indexing → **vector store (ChromaDB / pgvector)** → retrieval → **LangChain** RAG orchestration → augmented prompt → **Claude API (Anthropic)** → **verified response + citations** → **`EnrichedFinding`** (`explanation` + `citation_verified`). Plus a **continuous evaluation module** monitoring answer quality.
- **MVP:** corpus limited to **ISO 27001 + Loi 05-20 + DNSSI** (NIST and SOC 2 are stretch — they widen the corpus without changing the architecture); **ChromaDB** (pgvector is a documented alternative, not a second implementation); LangChain + Claude API; `EnrichedFinding` with `citation_verified` **is in scope — it is the contract Layer 4 consumes**; continuous evaluation reduced to a **30–50 question reference set** run manually, not a live monitoring module.
- **Non-negotiable:** the system prompt enforces **mandatory citation** and **abstention outside the corpus**. `citation_verified` must be an actual verification against retrieved chunks, not a flag the model sets about itself.
- **Owner:** Student B (me).

### Layer 4 — Corrélation & Traduction du Risque ⭐ THE DIFFERENTIATOR
- **Risk Correlator (S8):** combines multiple `Finding`s into a `CorrelatedRisk` with an **attack-path narrative**.
- **Financial Risk Translator:** exposure range in **MAD** → `FinancialRiskAssessment`.
- **Remediation Generator:** Terraform proposals with RAG justification, **never auto-applied — `approved=false` by default**.
- **Red-Team Proof Engine:** exploitability proof, **sandbox ONLY**, guarded by `UnsafeTargetError`.
- **MVP (pick 2, in this priority order):**
  1. **Financial Risk Translator** — highest value-to-effort. A defensible, documented estimation model (severity × asset criticality × a published cost basis) beats a sophisticated one that nobody can justify at the defense. Be ready to defend the numbers.
  2. **Remediation Generator** — reuses the RAG pipeline already built in Layer 3. `approved=false` is a hard default.
  3. *Risk Correlator* — medium effort, do it only if R4 goes well.
  4. *Red-Team Proof Engine* — **defer by default.** See the governance flag below.
- **Owner:** Student A leads, Student B supplies the RAG justification path.

### 🚩 Red-Team Proof Engine — governance flag
This component actively exploits infrastructure. Before **any** code is written for it:
- Get **written authorization** from the AlexSys supervisor, naming the sandbox.
- The `UnsafeTargetError` guard must be an **allowlist** of sandbox resource IDs, default-deny — not a blocklist.
- It must be **physically incapable** of targeting anything outside our own Terraform-provisioned sandbox.

If it cannot get written authorization inside R1, it is out of the MVP and becomes a designed-but-unbuilt section of the report. **It is the first thing to cut** and cutting it costs the project almost nothing.

### Layer 5 — Gouvernance, Sécurité & Identité
- **Target:** centralized IAM (authentication, **MFA + full RBAC**), **multi-tenant directory** (per-client data isolation), secrets management (**AWS Secrets Manager / Azure Key Vault / GCP Secret Manager**), audit-trail logging (**GDPR / Loi 09-08** compliant).
- **MVP:** baseline authentication + **RBAC** (2–3 roles) + **audit logging**. **No MFA. No multi-tenant directory.** Secrets via `.env` locally and **one** cloud secret manager. `tenant_id` present in the data model from day one so multi-tenancy is later a query filter, not a migration.
- **Owner:** Student B (auth/RBAC), Student A (secrets hygiene, hardening).

### Layer 6 — Intégrations Externes
- **Target:** SIEM/SOAR connectors (**Splunk / Microsoft Sentinel / QRadar**), third-party APIs (webhooks, Slack/Teams/email), **ITSM connector** (Jira/ServiceNow with automatic remediation-ticket creation).
- **MVP:** **OUT OF SCOPE.** Optional stretch: a single outbound **webhook** (Slack) — roughly an hour, and it demos well. Nothing more.

### Layer 7 — Backend & Données
- **Target:** **FastAPI** REST API (`/api/v1`, multi-tenant), **PostgreSQL** (findings, scores, history, tenants), **message broker** (Kafka/RabbitMQ) for asynchronous scan processing, **ReportLab** per-client PDF reports.
- **MVP:** FastAPI + PostgreSQL + ReportLab. **No message broker** — use FastAPI `BackgroundTasks` for async scans; the broker is a documented scaling path. Single-tenant reports.
- **Owner:** Student B (API, data model), Student A (PDF reports).

### Layer 8 — Présentation
- **Target:** **React + Recharts** multi-tenant dashboard, **per-organization client portal**, **mobile app** for compliance tracking on the go.
- **MVP:** the React + Recharts dashboard only — compliance score views, findings list with `EnrichedFinding` explanations and citations, copilot chat, financial exposure view. **No client portal. No mobile app.**
- **Owner:** Student B.

### Déploiement & Scalabilité (cross-cutting)
- **Target:** **Docker** containers orchestrated by **Kubernetes**, **CI/CD via GitHub Actions**, scalable HA multi-environment infrastructure.
- **MVP:** **Docker + Docker Compose.** **No Kubernetes** — it is a week of work that moves no milestone. A minimal **GitHub Actions** workflow (lint + tests) is cheap and worth keeping.
- **Owner:** Student A.

---

## 4. KEY DATA CONTRACTS

These names come from the architecture and should be used consistently in code, report, and defense:

```
NormalizedResource        # cloud-agnostic resource, output of the connectors
Finding                   # rule violation + evidence, output of the Rule Engine
ComplianceScore           # global / per domain (MVP); per cloud / per tenant (target)
EnrichedFinding           # Finding + RAG explanation + citation_verified  ← Layer 3 → Layer 4 contract
CorrelatedRisk            # several Findings combined into an attack-path narrative
FinancialRiskAssessment   # exposure range in MAD
UnsafeTargetError         # Red-Team guard: raised on any non-sandbox target
approved = false          # Remediation Generator default. Never auto-apply.
```

**Frozen API contract:**
```
POST /api/v1/copilot/ask
  in:  { "question": str, "conversation_id": str | null }
  out: { "answer": str, "sources": [str], "conversation_id": str }
```
Other endpoints: scan, results, report.

---

## 5. STACK

**Mine (B):** Python · Anthropic SDK · LangChain (`RecursiveCharacterTextSplitter`) · ChromaDB (metadata: source document, article/control ID) · Claude API · FastAPI · PostgreSQL · React + Recharts · Git, `.env` + `.env.example` + `.gitignore`

**Student A's:** Terraform · cloud SDK (`boto3` / Azure SDK / GCP SDK) · Python · Checkov · Docker / Docker Compose · ReportLab · SAST tooling

**Model & cost — already decided:** use **Claude Sonnet**, not Opus. ~1,500–3,000 input + 300–500 output tokens per RAG query ≈ **$0.01/query**; whole internship ≈ **$5–15**. Enable **prompt caching** on the system prompt + corpus context once evaluation iterations get heavy. API billing is separate from any claude.ai subscription.

---

## 6. THE 6-WEEK PLAN (R1–R6)

| Week | Student A | Student B (me) | Sync point |
|---|---|---|---|
| **R1** | Scope freeze; Terraform sandbox + deliberate misconfigs | Scope freeze; corpus split + ChromaDB indexing (Layer 3.1) | **Scope signed (MoSCoW)** + contracts confirmed, day 1–2 |
| **R2** | YAML rule base + cloud connector → `NormalizedResource` | RAG pipeline: retrieval → augmented prompt → Claude, citation + abstention (3.2) | End R2: rule format ↔ corpus structure cross-review |
| **R3** | Rule Engine + scoring (global/domain) + unit tests | Reference set (30–50 Q/A), evaluation, `EnrichedFinding` (3.3) | **M1: scanner and copilot each work standalone** |
| **R4** | Layer 4: Financial Risk Translator (+ Correlator if ahead) | FastAPI + PostgreSQL + auth/RBAC + audit log (Layer 7 / 5) | Mid-R4: `Finding` → API → `EnrichedFinding` integration |
| **R5** | Layer 4: Remediation Generator; Dockerfiles + Compose | React + Recharts dashboard, copilot chat, exposure view | **M2: end-to-end demo runs** |
| **R6** | Hardening, test campaign, UAT | UAT, integration fixes | Report finalization + **2 full rehearsals** |

### Milestones
| # | Due | Passing criteria |
|---|---|---|
| **M0** | R1 | MVP scope **signed in writing** by the AlexSys supervisor; cloud + Claude API access confirmed; Red-Team authorization obtained **or component formally cut** |
| **M1** | End R3 | Full scan runs **< 5 min**; score manually verified on a rule sample; **≥80% of reference-set copilot answers judged correct and sourced by the GRC supervisor** |
| **M2** | End R5 | End-to-end: scan → Finding → EnrichedFinding → FinancialRiskAssessment → dashboard, demoed without manual patching |
| **M3** | End R6 | UAT passed with the AlexSys supervisor; report submitted; defense rehearsed twice |

### Rules the plan depends on — do not break them
- **The two tracks run in parallel from R1.** Layer 3 does **not** wait for Layer 2. This is the single decision that removes idle time; a plan that serializes them fails.
- **Write the report from R1, incrementally.** R6 has no room to write it from scratch. Every phase's deliverable includes its report section.
- **Sync points sit at the end of autonomous blocks**, never mid-development.
- **Balance:** roughly equal person-days, verified task by task, not estimated globally.
- **`EnrichedFinding` is the critical interface.** It is Layer 3's output *and* Layer 4's input. If it slips, both tracks stall — treat it as the highest-priority contract after the scope freeze.

### Risks
| Risk | Mitigation |
|---|---|
| **Scope: the target architecture is ~3× a 6-week MVP** | MoSCoW scope signed at M0; cut list pre-agreed (see §7) |
| Cloud sandbox access delayed | Fallback free-tier account; Layer 3 is unblocked regardless |
| Copilot misses the 80% bar | Reference set built early (R3, not R5) so there is time to tune retrieval and prompt |
| Financial model challenged at the defense | Document the estimation model and its published cost basis from day one; defend the method, not the number |
| Red-Team engine touches a non-sandbox target | Default-deny allowlist; written authorization; cut if not obtained in R1 |

---

## 7. PRE-AGREED CUT LIST (in order, when we fall behind)

1. Red-Team Proof Engine → design only, no build
2. NIST + SOC 2 corpus → ISO 27001 / 05-20 / DNSSI only
3. Risk Correlator → design only
4. Slack webhook stretch
5. Per-domain scoring → global only
6. Remediation Generator → RAG-justified text, no Terraform generation

**Never cut:** citation + abstention · `citation_verified` · `approved=false` · the sandbox guard · the `NormalizedResource` abstraction.

---

## 8. HOW TO WORK WITH ME

- **Take this context as given.** Don't ask me to re-explain the project. Ask only about the flagged gaps: **which cloud provider**, and **Red-Team authorization status**.
- **Six weeks, two students.** Never propose Kubernetes, a message broker, MFA, multi-tenant directory, SIEM/ITSM connectors, mobile, or the client portal as MVP work. They are target architecture — the report documents them as the evolution path, and that is the *whole* of the work they get.
- **Anchor every suggestion to a week (R1–R6) and a milestone (M0–M3).** If it moves no milestone, say so plainly.
- **Tell me what to cut, not just what to add.** "This costs three days and doesn't move M1" is the most useful sentence you can write.
- **Flag when something is Student A's work** instead of silently doing it.
- **Citation, abstention, `approved=false`, and the sandbox guard are requirements, not preferences.** Never propose relaxing them for a demo.
- **Be direct about tradeoffs and risks.** I would rather hear a hard truth than a polite plan I cannot execute.

---

## 9. CURRENT STATUS — update before each session

> **As of [DATE]:** Week **R[?]**. Cloud provider: **[?]**. Red-Team engine: **[in / cut]**.
> Done: **[…]** · In progress: **[…]** · Blocked on: **[…]**
> Cuts made so far: **[…]**

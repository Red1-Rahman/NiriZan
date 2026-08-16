# Washington Accord Mapping

## Scope

The Washington Accord is an international agreement among organisations responsible for accrediting tertiary-level engineering qualifications. It focuses on accredited engineering degree programmes and supports international recognition of substantially equivalent engineering education.

NiriZan is an independent open-source software project and is not an accredited engineering degree programme. The Washington Accord framework is therefore used only as an engineering knowledge and competency self-assessment taxonomy.

A check indicates that the current NiriZan repository provides reasonable project-level evidence for the corresponding knowledge area or graduate attribute. It does not imply Washington Accord accreditation, programme equivalence, formal assessment, or recognition by any Washington Accord signatory.

## Knowledge and Attitude Profile

| Knowledge Profile | NiriZan |
|---|:---:|
| WK1 — Natural and social sciences | ⬜ |
| WK2 — Mathematics | ✅ |
| WK3 — Engineering fundamentals | ✅ |
| WK4 — Specialist knowledge | ✅ |
| WK5 — Engineering design & operations | ✅ |
| WK6 — Engineering practice | ✅ |
| WK7 — Role of engineering in society | ✅ |
| WK8 — Research literature | ✅ |
| WK9 — Ethics and conduct | ✅ |

## Knowledge Profile Justification

- **WK2 — Mathematics** — NiriZan applies mathematics, numerical and statistical reasoning, data analysis, hypothesis testing, confidence intervals, effect sizes, bootstrap estimation, Mann–Whitney regression testing, Holm–Bonferroni correction, and statistical gating to the evaluation of probabilistic AI systems.

- **WK3 — Engineering fundamentals** — The project applies fundamental software and systems engineering concepts including modular architecture, abstraction, interfaces, separation of concerns, dependency control, testing, observability, configuration management, and quality assurance.

- **WK4 — Specialist knowledge** — NiriZan applies specialist knowledge in AI-system evaluation, RAG evaluation, LLM-as-a-judge systems, evaluator reliability, behavioral anchors, statistical regression detection, drift attribution, and continuous evaluation of production AI systems.

- **WK5 — Engineering design & operations** — A central engineering contribution of NiriZan is its eight-layer, unidirectional architecture: Instrumentation → Evaluator Orchestrator → Metric Engine → Trust & Attribution → Trace Repository & Experiment Store → Regression Detection → Deployment-Aware Gate → Quality Reporting. The architecture defines system responsibilities and data flow, separates evaluation from the user-facing critical path, supports pluggable metrics and versioned evaluation state, and connects statistical regression analysis with deployment-aware quality gates. The architectural dependency direction is additionally enforced in CI, making the architecture an implemented engineering constraint rather than documentation alone.

- **WK6 — Engineering practice** — The repository demonstrates practical engineering through an implemented Python package, automated tests, CI/CD workflows, packaging, security checks, architectural boundary enforcement, reproducible experiments, documentation, examples, and version-controlled development.

- **WK7 — Role of engineering in society** — NiriZan addresses the reliability and accountability of AI systems that can affect users by providing mechanisms for detecting quality degradation, evaluating system behaviour continuously, and assessing whether automated evaluation results themselves remain trustworthy.

- **WK8 — Research literature** — NiriZan is explicitly grounded in research and technical literature covering RAG evaluation, LLM-as-a-judge approaches, AI-system evaluation, observability, statistical evaluation, agent evaluation, and evaluator reliability. The literature review is used to identify limitations and trade-offs that inform the project's architecture and experimental design.

- **WK9 — Ethics and conduct** — NiriZan explicitly considers evaluator bias, judge reliability, judge drift, attribution uncertainty, and the risk of treating automated evaluation scores as unquestionable ground truth. The project also documents responsible engineering, governance, security, and data-handling considerations.

## Graduate Attributes Profile

| Graduate Attribute | NiriZan |
|---|:---:|
| WA1 — Engineering Knowledge | ✅ |
| WA2 — Problem Analysis | ✅ |
| WA3 — Design/Development of solutions | ✅ |
| WA4 — Investigation | ✅ |
| WA5 — Tool Usage | ✅ |
| WA6 — The Engineer and the World | ⬜ |
| WA7 — Ethics | ✅ |
| WA8 — Individual and Collaborative Team work | ⬜ |
| WA9 — Communication | ✅ |
| WA10 — Project Management and Finance | ⬜ |
| WA11 — Lifelong learning | ✅ |

## Graduate Attribute Justification

- **WA1 — Engineering Knowledge** — NiriZan applies mathematics, statistics, computing and software engineering fundamentals, and specialist AI-evaluation knowledge to develop a continuous-evaluation infrastructure for complex AI systems.

- **WA2 — Problem Analysis** — The project identifies and analyzes the limitations of deterministic testing for probabilistic AI systems and examines existing evaluation approaches, including RAG evaluation, LLM-as-a-judge methods, statistical regression detection, and evaluator reliability, to formulate the engineering problem addressed by NiriZan.

- **WA3 — Design/Development of solutions** — NiriZan translates the identified evaluation problem into an implemented eight-layer engineering architecture covering instrumentation, orchestration, metrics, trust and attribution, storage, regression detection, deployment-aware gating, and quality reporting. The architecture defines explicit responsibilities and unidirectional dependencies and is enforced through CI.

- **WA4 — Investigation** — The project conducts investigations through structured literature review, experimental notebooks, ablation studies, benchmarking, statistical analysis, regression experiments, and judge-reliability investigations. These activities are used to evaluate technical alternatives and validate design decisions.

- **WA5 — Tool Usage** — NiriZan applies modern engineering and IT tools including Python packaging, automated testing, CI/CD, tracing and instrumentation patterns, statistical analysis, experiment infrastructure, and deployment-aware quality gates. The project also explicitly addresses the limitations and trade-offs of different evaluation tools and judge approaches.

- **WA7 — Ethics** — NiriZan addresses ethical and professional concerns surrounding automated AI evaluation, including evaluator bias, judge drift, attribution uncertainty, responsible interpretation of automated scores, and the danger of treating an unvalidated evaluation signal as ground truth.

- **WA9 — Communication** — The repository communicates complex engineering work through its README, architecture and contract documentation, user manual, literature review, experimental notebooks, examples, contribution guidance, governance documentation, and engineering standards mappings.

- **WA11 — Lifelong learning** — NiriZan requires continued engagement with emerging areas including AI evaluation, LLM-as-a-judge reliability, statistical evaluation, observability, drift detection, and production AI engineering. Research findings are continuously incorporated into the evolving design and implementation.


## Sources

- International Engineering Alliance — [Washington Accord](https://www.internationalengineeringalliance.org/accords/washington-accord)
  - Primary source for the current Washington Accord overview, Knowledge and Attitude Profile (WK1–WK9), and Graduate Attributes Profile (WA1–WA11).

- International Engineering Alliance — [Graduate Attributes and Professional Competencies](https://www.ieagreements.org/assets/Uploads/Documents/Policy/Graduate-Attributes-and-Professional-Competencies.pdf)
  - IEA framework document defining the engineering knowledge and graduate-attribute framework.

- International Engineering Alliance — [Documents](https://www.internationalengineeringalliance.org/about/documents)
  - Official IEA document repository for the framework and related accreditation documents.

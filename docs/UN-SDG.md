# UN Sustainable Development Goals Mapping

## Standard Overview

The United Nations Sustainable Development Goals (SDGs) are a set of 17 global goals adopted by the United Nations General Assembly in 2015 as part of the 2030 Agenda for Sustainable Development. They address poverty, health, education, inequality, climate, and related global challenges through 169 associated targets. The SDGs are a policy and development framework rather than a technical or accreditation standard, so this document identifies which specific goals NiriZan's work genuinely connects to, rather than mapping the project against all 17 goals, since most of them have no meaningful connection to a software evaluation infrastructure project.

## Relevant Goal Mapping

### SDG 9: Industry, Innovation, and Infrastructure

SDG 9 calls for building resilient infrastructure, promoting inclusive and sustainable industrialization, and fostering innovation. NiriZan is infrastructure in a literal sense: it is designed as an evaluation layer that other AI systems and teams build on top of. As an open-source project, it is available to any engineering team regardless of organizational size or resources, which supports the goal's emphasis on fostering innovation broadly rather than only within organizations that can afford proprietary evaluation tooling.

### SDG 12: Responsible Consumption and Production

SDG 12 calls for ensuring sustainable consumption and production patterns. Applied to software engineering, this connects to the responsible development and deployment of AI systems. NiriZan's core function, catching quality regressions and drift before they reach users at scale, supports more responsible production of AI-driven products by reducing the likelihood that a degraded or unreliable system is deployed and left unmonitored. The project's judge-reliability tracking also supports responsible production of evaluation results themselves, since it treats the evaluator's own trustworthiness as something that must be measured rather than assumed.

### SDG 16: Peace, Justice, and Strong Institutions

SDG 16 includes targets related to building effective, accountable, and transparent institutions. While NiriZan is not an institution, its design principles (reproducible evaluation runs, versioned experiments, transparent regression detection with confidence intervals rather than opaque pass or fail signals) reflect the same underlying values of accountability and transparency applied to the technical systems that institutions increasingly rely on.

## Goals Considered and Not Included

Goals such as SDG 1 (No Poverty), SDG 2 (Zero Hunger), SDG 3 (Good Health and Well-Being), SDG 6 (Clean Water and Sanitation), and others addressing direct humanitarian, health, or environmental outcomes are not included in this mapping. NiriZan is a software evaluation infrastructure project with no direct mechanism of action on these goals, and including them here would overstate the project's relevance to argue for a broader connection than genuinely exists.

## Applicability Note

NiriZan is an independent, open-source project with no institutional or governmental affiliation. The SDGs are a global policy framework aimed at governments, institutions, and large-scale development initiatives, and a single open-source project does not itself achieve or measurably advance any SDG target on a global scale. This mapping identifies genuine thematic alignment between NiriZan's goals and the three SDGs listed above, as an honest reflection of where the project's purpose connects to broader concerns, not as a claim of measurable impact.

## Sources

- United Nations, "THE 17 GOALS | Sustainable Development" (primary source, official goal list and background): https://sdgs.un.org/goals
- United Nations, "Sustainable Development Goals: 17 Goals to Transform our World": https://www.un.org/en/exhibits/page/sdgs-17-goals-transform-world
- Wikipedia, "Sustainable Development Goal 12" (detail on targets and indicators for SDG 12 specifically): https://en.wikipedia.org/wiki/Sustainable_Development_Goal_12
- UNDP, "Sustainable Development Goals": https://www.undp.org/sustainable-development-goals

# Skill extraction metrics

Measured against the gold set (`data/gold/skills_gold.yaml`),
micro-averaged over (vacancy, skill) pairs. Cost is per 10,000 vacancies, from the
logged token usage.

**The labels were made by: Claude (an LLM), blind to the dictionary and to the LLM method; not a human.** A metric is only as independent as its labels.

| Method | Vacancies | Precision | Recall | F1 | Cost per 10k vacancies |
|---|---|---|---|---|---|
| dictionary | 150 | 0.74 | 0.91 | 0.81 | $0.00 |
| llm | 150 | 0.88 | 0.72 | 0.80 | $8.44 |

## dictionary: most frequent mistakes

Found wrongly: test-automation (26), fintech (16), devops (14), multitenancy (14), simd (13), qa-process (12), system-design (12), api-design (11), business-analysis (11), ecommerce (11)

Missed: networking (13), monitoring (11), ai-coding-tools (7), rdbms (7), design-patterns (5), leadership (5), message-queues (5), payment-gateways (5), solid (5), multithreading (4)

## llm: most frequent mistakes

Found wrongly: llm (6), aws (5), gke (5), sso (5), git (4), jest (4), ai-coding-tools (3), arduino (3), azure (3), datadog (3)

Missed: code-review (36), monitoring (33), devops (17), distributed-systems (16), ai-coding-tools (15), leadership (14), message-queues (14), microservices (14), multithreading (14), iac (13)

## Skills the labellers wanted that the taxonomy lacks

ArduPilot (6), UART (5), Clean Architecture (4), Kotlin Coroutines (4), MVVM (4), SPI (4), GCD (3), Google Sheets (3), Gradle (3), LangGraph (3), Keycloak (3), MAVLink (3), SignalR (3), STM32 (3), AWS Secrets Manager (3), Betaflight (3), MCP (3), VLAN (3), New Relic (3), Cloud Run (3), Dependency injection (3), Temporal (3), VPC (3), CloudFront (3), Core Data (2), Reactive Programming (2), Zabbix (2), Vector databases (2), Cloud Functions (2), GitOps (2), NVIDIA Jetson (2), WebRTC (2), Hilt (2), SNS (2), ESP32 (2), PX4 (2), Event sourcing (2), Event-driven architecture (2), Google Play Console (2), GDPR (2)

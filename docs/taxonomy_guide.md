# Skill taxonomy guide

The skills a vacancy asks for are found by a dictionary over `src/jobmarket/skills/taxonomy.yaml`
(about 490 skills and 2,000 spellings). A skill is one line:

```yaml
- {id: nextjs, name: Next.js, category: frontend, aliases: [nextjs, next js], parent: react}
```

| Field | Meaning |
|---|---|
| `id` | stable slug; it is the key stored in `silver_vacancy_skills`, so do not rename it |
| `name` | the name shown to people |
| `category` | one of the `categories` at the top of the file |
| `aliases` | other spellings, matched whole-word and case-insensitively |
| `parent` | a broader skill: a vacancy that asks for Next.js also counts for React in gold |
| `strict`, `case`, `context` | for words that are also ordinary language ("Go", "R", "Spring", "Swift") |

## Ambiguous words

A skill whose name is a plain word is marked `strict: true`. It counts only when it is written exactly
as in `case` (default: the name) **and** one of its `context` words is within 80 characters:

```yaml
- {id: go, name: Go, category: language, strict: true, case: Go, context: [golang, backend, microservices, kubernetes]}
```

"We go to the office" is not Go; "Go and Kubernetes" is.

## What the matcher does with the text

- Whole-word, case-insensitive matching of the name and aliases (a trie, one pass over the text).
- Skills under "nice to have" headings are marked `nice`; the rest are `required`.
- Sections about benefits and the company are ignored, so "free English courses" is not a skill.

## Adding or changing a skill

1. Add the line. If the word is ordinary language, make it `strict` with context words.
2. `make test` validates the file: unique ids and aliases, parents that exist, known categories, a slug
   id, context words for every strict skill.
3. See what the data wants: `uv run jobmarket skills-review` lists the most frequent skill-like words
   that the taxonomy does not know (from the LLM method's answers, `silver_unknown_skills`).
4. After editing, re-map stored LLM answers: `uv run jobmarket skills-renormalize`. The dictionary
   method is recomputed on every `parse`.
5. Add a case to the gold set when a mistake taught you something (see below).

## Measuring it

Precision and recall of the dictionary and the LLM method are measured against a hand-labelled set
(`uv run jobmarket gold-sample`, `gold-label` in the terminal **without suggestions**, `gold-import`, `gold-eval`;
results go to `docs/metrics.md`). The labelling is blind on purpose: a list prepared in advance makes a
person agree with it, and the metric would measure the agreement. Once the first evaluation exists, a
regression test fails if the dictionary's F1 drops below the recorded value.

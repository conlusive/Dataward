# Data sources

| Source | What | How it is read | Volume (2026-11-08) |
|---|---|---|---|
| **jobs.dou.ua** | IT vacancies in 16 categories (Python, Java, Data Science, DevOps, DBA, QA, Front End, .NET, Node.js, PHP, C++, Golang, Ruby, Scala, Android, iOS) | listing pages, the "load more" XHR batches and each vacancy page | about 1,000 vacancies |
| **djinni.co** | IT vacancies for 16 keywords (the same stacks plus Fullstack, JavaScript, QA Manual/Automation) | listing pages and each vacancy page; the structured fields come from the page's `JobPosting` JSON-LD | about 5,900 vacancies |
| **NBU exchange rates** | official UAH rates for every date a vacancy was published | `bank.gov.ua` statdirectory API, one JSON per date | one file per date |
| **DOU salary survey** | 34 survey waves since 2010: position, experience, city, English, company, salary | the CSV files of the public `devua/csv` repository (GitHub API) | about 289,000 answers with a salary |

Everything is stored first as raw files in the bronze layer (`data/bronze/{source}/dt={date}/...`) and
never changed; silver and gold can be rebuilt from it without the network.

## How the sites are treated

- `robots.txt` is read and honoured; a disallowed URL is not fetched.
- At most 1-2 requests per second (a configured rate and 2 concurrent workers), an honest `User-Agent` that names the
  project and its repository, no logins, no cookies, no attempt to get around protection.
- A `429` makes the scraper pause for a minute and retry; transient errors are retried with a backoff.
- A vacancy page fetched in the last 7 days is not downloaded again.
- **work.ua is not scraped.** It answers automated clients with a Cloudflare challenge. Getting past
  that would mean bypassing a protection the site put there, so the source is dropped, and the project
  has two job sites instead of three. If the site ever offers a feed or an API, it can be added.
- The survey comes from a public repository through its API, not from a crawled site.

## What is published and what is not

- **Raw vacancy text is not published.** The repository holds a few pages for parser tests; the hand
  labelled gold set keeps the texts local and commits only the labels.
- The exported gold files hold aggregates (skill shares, pair statistics, salary percentiles, daily
  counts) and the survey rows the salary model uses. The survey is open data published by DOU.

## Limits to keep in mind

- **History is short.** Scraping started on 2026-11-06, so monthly trends need weeks to mean anything,
  and "how long a vacancy stays open" needs vacancies that have closed.
- **It is not a census.** 16 categories on two sites: vacancies that are posted elsewhere, or are not
  in these categories, are not here. Vacancies listed on both sites are merged, but a posting that
  differs on each site may be counted twice.
- **Few vacancies state a salary** (about 12% of the listings), and those that do are not a random
  sample. The vacancy salaries are shown with their count and only when there are enough of them.
- **The survey is self-reported** by people who answer surveys. It shows what people earn, not what an
  employer will offer.
- **Skills are found by a dictionary** (and, when switched on, by an LLM). The precision and recall of
  both are measured against a gold set of 150 vacancies (F1 0.81 and 0.80, see `docs/metrics.md`).
  The gold labels were made by an LLM, not by a person, so treat the accuracy as approximate.
- Salaries are converted to USD at the National Bank rate on the publication date; nominal, not
  adjusted for inflation.

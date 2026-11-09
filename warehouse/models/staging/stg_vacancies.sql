-- Silver vacancies with one date a vacancy can be placed on: the page's publication date, or the day we
-- first fetched it when the page has none (DOU often has none).
select
    id,
    source,
    url,
    title,
    company,
    category,
    seniority,
    remote,
    locations,
    english_level,
    experience_years_text,
    salary_usd_min,
    salary_usd_max,
    dedup_group_id,
    coalesce(published_at, cast(_fetched_at as date)) as listed_on
from {{ source('silver', 'silver_vacancies') }}

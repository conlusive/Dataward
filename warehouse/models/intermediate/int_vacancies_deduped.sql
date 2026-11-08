-- One row per real vacancy: a group of the same vacancy on DOU and Djinni is one row. Title and text come
-- from the member the dedup step chose (`text_id`), the salary from `salary_id` (Djinni states it as data),
-- the date is the earliest any member was listed.
with members as (

    select
        coalesce(dedup_group_id, id) as vacancy_group_id,
        min(listed_on) as first_listed_on,
        count(*) as members
    from {{ ref('stg_vacancies') }}
    group by 1

),

groups as (

    select dedup_group_id, text_id, salary_id
    from {{ source('silver', 'silver_vacancy_groups') }}

)

select
    coalesce(t.dedup_group_id, t.id) as vacancy_group_id,
    t.id as text_vacancy_id,
    t.source,
    t.title,
    t.company,
    t.category,
    t.seniority,
    t.remote,
    t.locations,
    t.english_level,
    t.experience_years_text,
    m.first_listed_on,
    m.members,
    s.salary_usd_min,
    s.salary_usd_max,
    case
        when s.salary_usd_min is not null and s.salary_usd_max is not null
            then (s.salary_usd_min + s.salary_usd_max) / 2
        else coalesce(s.salary_usd_min, s.salary_usd_max)
    end as salary_usd_mid
from {{ ref('stg_vacancies') }} t
left join groups g on g.dedup_group_id = t.dedup_group_id
join members m on m.vacancy_group_id = coalesce(t.dedup_group_id, t.id)
left join {{ ref('stg_vacancies') }} s on s.id = coalesce(g.salary_id, t.id)
where t.id = coalesce(g.text_id, t.id)

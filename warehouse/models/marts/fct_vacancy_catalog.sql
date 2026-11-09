-- The vacancy catalog: one row per real vacancy (the same job on DOU and Djinni is one row) with what a
-- reader filters by: direction (category), level, salary, skills, when it was listed and whether it is
-- still open on the last day of data.
--
-- PRIVATE. These are third-party listings (titles, companies, links), so the table is exported for local
-- use only and kept out of the public CI artifact (`meta.private` in schema.yml). There is no description
-- text in it on purpose: the link leads to the original page.
with last_day as (

    select max(date) as day from {{ ref('fct_vacancy_daily') }}

),

members as (

    select coalesce(dedup_group_id, id) as vacancy_group_id, id, url
    from {{ ref('stg_vacancies') }}

),

links as (

    select
        d.vacancy_group_id,
        max(m.url) filter (where m.id = d.text_vacancy_id) as url,
        max(m.url) filter (where m.id <> d.text_vacancy_id) as url_other
    from {{ ref('int_vacancies_deduped') }} d
    join members m on m.vacancy_group_id = d.vacancy_group_id
    group by 1

),

state as (

    -- open = a member of the group is `new` or `active` on the last day of data
    select
        m.vacancy_group_id,
        coalesce(bool_or(v.status in ('new', 'active')), false) as is_open
    from members m
    left join {{ ref('fct_vacancy_daily') }} v
        on v.vacancy_id = m.id and v.date = (select day from last_day)
    group by 1

),

seen as (

    select m.vacancy_group_id, max(si.seen_date) as last_seen_on
    from members m
    join {{ source('silver', 'silver_vacancy_sightings') }} si on si.vacancy_id = m.id
    group by 1

),

skills as (

    select
        gs.vacancy_group_id,
        list(ds.canonical order by gs.required desc, ds.canonical) as skills,
        coalesce(
            list(ds.canonical order by ds.canonical) filter (where gs.required),
            cast([] as varchar[])
        ) as skills_required
    from {{ ref('int_group_skills') }} gs
    join {{ ref('dim_skill') }} ds on ds.skill_id = gs.skill_id
    group by 1

)

select
    d.vacancy_group_id as vacancy_id,
    d.title,
    d.company,
    d.source,
    d.category,
    d.seniority,
    d.remote,
    array_to_string(d.locations, ', ') as locations,
    d.english_level,
    d.experience_years_text as experience_years,
    d.salary_usd_min,
    d.salary_usd_max,
    d.first_listed_on,
    se.last_seen_on,
    st.is_open,
    cast(d.members as integer) as members,
    l.url,
    l.url_other,
    coalesce(sk.skills, cast([] as varchar[])) as skills,
    coalesce(sk.skills_required, cast([] as varchar[])) as skills_required
from {{ ref('int_vacancies_deduped') }} d
join links l on l.vacancy_group_id = d.vacancy_group_id
join state st on st.vacancy_group_id = d.vacancy_group_id
left join seen se on se.vacancy_group_id = d.vacancy_group_id
left join skills sk on sk.vacancy_group_id = d.vacancy_group_id

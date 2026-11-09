-- Share of the month's new real vacancies that ask for a skill, parents included (Next.js counts for
-- React). The denominator is every vacancy of the month, also those with no skill found.
with vacancies as (

    select vacancy_group_id, cast(date_trunc('month', first_listed_on) as date) as month
    from {{ ref('int_vacancies_deduped') }}

),

totals as (

    select month, count(*) as month_vacancies
    from vacancies
    group by month

)

select
    v.month,
    g.skill_id,
    cast(count(*) as integer) as vacancies,
    cast(count(*) filter (where g.mentioned_directly) as integer) as vacancies_direct,
    cast(count(*) filter (where g.required) as integer) as vacancies_required,
    cast(t.month_vacancies as integer) as month_vacancies,
    cast(round(count(*) * 1.0 / t.month_vacancies, 4) as double) as share
from vacancies v
join {{ ref('int_group_skills_rolled_up') }} g using (vacancy_group_id)
join totals t using (month)
group by v.month, g.skill_id, t.month_vacancies

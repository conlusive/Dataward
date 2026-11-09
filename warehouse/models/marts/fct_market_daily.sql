-- Vacancies per day, source, category and level, for the market overview. `open` counts the vacancies
-- listed that day (new + active); `closed` those that were found closed that day. Both sites are
-- counted as they list: a vacancy on DOU and on Djinni is two rows here (it is one in the demand mart,
-- where the real vacancy matters). Vacancies from the first day of data are `new` on that day only
-- because that is when we started looking.
select
    d.date,
    v.source,
    coalesce(v.category, 'unknown') as category,
    coalesce(v.seniority, 'unknown') as seniority,
    cast(count(*) filter (where d.status in ('new', 'active')) as integer) as open_vacancies,
    cast(count(*) filter (where d.status = 'new') as integer) as new_vacancies,
    cast(count(*) filter (where d.status = 'closed') as integer) as closed_vacancies
from {{ ref('fct_vacancy_daily') }} d
join {{ ref('stg_vacancies') }} v on v.id = d.vacancy_id
group by d.date, v.source, coalesce(v.category, 'unknown'), coalesce(v.seniority, 'unknown')

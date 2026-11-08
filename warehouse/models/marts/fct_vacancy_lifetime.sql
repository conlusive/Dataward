-- How long vacancies stay open, by level. Only vacancies that ended up closed count (a still-open
-- vacancy has no final lifetime yet), and those first seen on the first day of data are left out
-- (`left_censored`: they may have been open long before we started). Groups below `min_lifetime_n` are
-- not published.
with last_state as (

    select
        vacancy_id,
        arg_max(status, date) as status,
        arg_max(lifetime_days, date) as lifetime_days,
        arg_max(left_censored, date) as left_censored
    from {{ ref('fct_vacancy_daily') }}
    group by vacancy_id

)

select
    coalesce(v.seniority, 'unknown') as seniority,
    cast(count(*) as integer) as closed_vacancies,
    quantile_cont(l.lifetime_days, 0.25) as lifetime_p25,
    quantile_cont(l.lifetime_days, 0.5) as lifetime_median,
    quantile_cont(l.lifetime_days, 0.75) as lifetime_p75
from last_state l
join {{ ref('stg_vacancies') }} v on v.id = l.vacancy_id
where l.status = 'closed' and not l.left_censored
group by coalesce(v.seniority, 'unknown')
having count(*) >= {{ var('min_lifetime_n') }}

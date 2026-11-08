-- Declared monthly salary (USD, middle of the range) of real vacancies that ask for a skill, parents
-- included. Only skills with at least `min_salary_n` salaried vacancies are published: few vacancies state
-- a salary, and a median of three numbers misleads more than it informs.
select
    g.skill_id,
    cast(count(*) as integer) as vacancies_with_salary,
    quantile_cont(d.salary_usd_mid, 0.25) as salary_p25,
    quantile_cont(d.salary_usd_mid, 0.5) as salary_median,
    quantile_cont(d.salary_usd_mid, 0.75) as salary_p75
from {{ ref('int_group_skills_rolled_up') }} g
join {{ ref('int_vacancies_deduped') }} d using (vacancy_group_id)
where d.salary_usd_mid is not null
group by g.skill_id
having count(*) >= {{ var('min_salary_n') }}

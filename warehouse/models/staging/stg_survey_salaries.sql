-- DOU survey answers with the free-text position and city replaced by the seed vocabularies.
-- A value missing from the seeds becomes role `other` / city `Не вказано` here and is reported by the
-- `relationships` tests in schema.yml (regenerate the seeds with `jobmarket make-seeds`).
select
    s.survey_date,
    cast(year(s.survey_date) as integer) as survey_year,
    coalesce(p.role, 'other') as role,
    coalesce(p.seniority, 'unknown') as seniority,
    s.experience_years,
    coalesce(c.city, 'Не вказано') as city,
    coalesce(c.city_group, 'unspecified') as city_group,
    s.salary_usd,
    s.weight
from {{ source('silver', 'silver_dou_salaries') }} s
left join {{ ref('position_map') }} p on p.position_raw = s.position
left join {{ ref('city_map') }} c on c.city_raw = s.city

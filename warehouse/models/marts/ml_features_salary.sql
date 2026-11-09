-- One row per survey answer with a salary, with the features the salary model trains and predicts on.
-- Training and prediction read these same definitions (the exported parquet), so they cannot drift.
-- Implausible experience (negative or over 40 years) is blanked, not dropped: the answer is still a
-- salary at a role and level. `weight` is how many respondents the row stands for (aggregated waves).
select
    survey_year,
    role,
    seniority,
    case when experience_years between 0 and 40 then experience_years end as experience_years,
    english,
    company_size,
    company_type,
    city_group,
    salary_usd,
    weight
from {{ ref('stg_survey_salaries') }}
where salary_usd > 0

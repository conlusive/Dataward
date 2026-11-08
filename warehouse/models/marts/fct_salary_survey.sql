-- DOU survey salaries (USD per month, net) by year, role and level, weighted by the number of respondents
-- each row stands for (aggregated waves). A weighted percentile is the lowest salary whose cumulative
-- weight reaches the share of the total. Groups below `min_survey_respondents` are not published.
with ranked as (

    select
        survey_year,
        role,
        seniority,
        salary_usd,
        weight,
        sum(weight) over (
            partition by survey_year, role, seniority
            order by salary_usd rows between unbounded preceding and current row
        ) as cumulative_weight,
        sum(weight) over (partition by survey_year, role, seniority) as total_weight
    from {{ ref('stg_survey_salaries') }}

)

select
    survey_year,
    role,
    seniority,
    cast(round(max(total_weight), 1) as double) as respondents,
    min(salary_usd) filter (where cumulative_weight >= 0.25 * total_weight) as salary_p25,
    min(salary_usd) filter (where cumulative_weight >= 0.50 * total_weight) as salary_median,
    min(salary_usd) filter (where cumulative_weight >= 0.75 * total_weight) as salary_p75
from ranked
group by survey_year, role, seniority
having max(total_weight) >= {{ var('min_survey_respondents') }}

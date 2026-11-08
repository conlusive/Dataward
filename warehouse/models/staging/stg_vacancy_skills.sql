-- One row per vacancy and skill; the dictionary and the LLM may both report a skill, `required` wins.
select
    vacancy_id,
    skill_id,
    bool_or(importance = 'required') as required
from {{ source('silver', 'silver_vacancy_skills') }}
group by vacancy_id, skill_id

-- Skills named by the vacancy text (direct only, no roll-up), one row per real vacancy and skill.
select
    d.vacancy_group_id,
    vs.skill_id,
    vs.required
from {{ ref('int_vacancies_deduped') }} d
join {{ ref('stg_vacancy_skills') }} vs on vs.vacancy_id = d.text_vacancy_id

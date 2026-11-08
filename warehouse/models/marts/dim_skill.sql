select
    s.skill_id,
    s.canonical,
    s.category,
    s.parent_id,
    p.canonical as parent_canonical
from {{ ref('stg_skills') }} s
left join {{ ref('stg_skills') }} p on p.skill_id = s.parent_id

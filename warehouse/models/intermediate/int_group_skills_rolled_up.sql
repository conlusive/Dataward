-- The same skills plus their ancestors. `mentioned_directly` tells a named skill from an inherited one.
select
    g.vacancy_group_id,
    a.ancestor_id as skill_id,
    bool_or(a.depth = 0) as mentioned_directly,
    bool_or(g.required) as required
from {{ ref('int_group_skills') }} g
join {{ ref('int_skill_ancestors') }} a on a.skill_id = g.skill_id
group by g.vacancy_group_id, a.ancestor_id

-- Every skill with all of its ancestors in the taxonomy (depth 0 is the skill itself), so a vacancy that
-- asks for Django also counts for Python.
with recursive walk as (

    select skill_id, skill_id as ancestor_id, 0 as depth
    from {{ ref('stg_skills') }}

    union all

    select w.skill_id, s.parent_id, w.depth + 1
    from walk w
    join {{ ref('stg_skills') }} s on s.skill_id = w.ancestor_id
    where s.parent_id is not null
        and w.depth < 10  -- a cycle in the taxonomy would otherwise never end; the taxonomy test forbids it

)

select skill_id, ancestor_id, depth
from walk

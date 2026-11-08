select skill_id, canonical, category, parent_id
from {{ source('silver', 'silver_skills') }}

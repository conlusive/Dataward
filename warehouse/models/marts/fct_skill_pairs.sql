-- Which skills appear together, over all stored vacancies: lift = P(a,b) / (P(a) P(b)), pmi = ln(lift),
-- npmi = pmi / -ln(P(a,b)) in [-1, 1]. The probability space is the vacancies where at least one skill was
-- found (a vacancy with no skills says nothing about co-occurrence), direct skills only, and a pair of
-- skill and its own ancestor is left out (always together by definition). Pairs below
-- `min_pair_support` vacancies are not published: a ratio of 2 over 3 vacancies is noise.
with named as (

    select vacancy_group_id, skill_id
    from {{ ref('int_group_skills') }}

),

total as (

    select count(distinct vacancy_group_id) as vacancies from named

),

singles as (

    select skill_id, count(*) as vacancies
    from named
    group by skill_id

),

pairs as (

    select a.skill_id as skill_a, b.skill_id as skill_b, count(*) as together
    from named a
    join named b
        on b.vacancy_group_id = a.vacancy_group_id
        and a.skill_id < b.skill_id
    group by a.skill_id, b.skill_id
    having count(*) >= {{ var('min_pair_support') }}

),

related as (

    select skill_id, ancestor_id
    from {{ ref('int_skill_ancestors') }}
    where depth > 0

)

select
    p.skill_a,
    p.skill_b,
    cast(p.together as integer) as vacancies_together,
    cast(sa.vacancies as integer) as vacancies_a,
    cast(sb.vacancies as integer) as vacancies_b,
    cast(t.vacancies as integer) as vacancies_total,
    cast((p.together * 1.0 / t.vacancies) / ((sa.vacancies * 1.0 / t.vacancies) * (sb.vacancies * 1.0 / t.vacancies)) as double) as lift,
    ln((p.together * 1.0 / t.vacancies) / ((sa.vacancies * 1.0 / t.vacancies) * (sb.vacancies * 1.0 / t.vacancies))) as pmi,
    ln((p.together * 1.0 / t.vacancies) / ((sa.vacancies * 1.0 / t.vacancies) * (sb.vacancies * 1.0 / t.vacancies)))
        / nullif(-ln(p.together * 1.0 / t.vacancies), 0) as npmi
from pairs p
cross join total t
join singles sa on sa.skill_id = p.skill_a
join singles sb on sb.skill_id = p.skill_b
where not exists (
    select 1 from related r
    where (r.skill_id = p.skill_a and r.ancestor_id = p.skill_b)
        or (r.skill_id = p.skill_b and r.ancestor_id = p.skill_a)
)

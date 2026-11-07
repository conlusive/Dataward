-- One row per vacancy per day while it is open: `new` on the first day it was listed, `active` while it
-- is listed (a single missed day is tolerated), `closed` on the day it has been missing for two days in a
-- row. No rows after the closing day, unless the vacancy is listed again, which makes it `active` again.
--
-- lifetime_days is "days from the first listing to the last listing seen so far". A vacancy first seen on
-- the very first day of data may have been open for longer already, so it is flagged `left_censored`.

with sightings as (

    select distinct vacancy_id, seen_date
    from {{ source('silver', 'silver_vacancy_sightings') }}

),

bounds as (

    select min(seen_date) as first_day, max(seen_date) as last_day
    from sightings

),

per_vacancy as (

    select vacancy_id, min(seen_date) as first_seen
    from sightings
    group by vacancy_id

),

calendar as (

    select cast(unnest(generate_series(first_day, last_day, interval 1 day)) as date) as date
    from bounds

),

grid as (

    -- every day from the vacancy's first listing up to the last day of data
    select
        c.date,
        v.vacancy_id,
        v.first_seen,
        s.vacancy_id is not null as listed
    from per_vacancy v
    join calendar c
        on c.date >= v.first_seen
    left join sightings s
        on s.vacancy_id = v.vacancy_id
        and s.seen_date = c.date

),

with_gap as (

    select
        *,
        max(case when listed then date end) over (
            partition by vacancy_id order by date rows between unbounded preceding and current row
        ) as last_listed
    from grid

)

select
    cast(vacancy_id || ':' || cast(date as varchar) as varchar) as vacancy_day_key,
    date,
    vacancy_id,
    case
        when listed and date = first_seen then 'new'
        when date - last_listed = 2 then 'closed'
        else 'active'
    end as status,
    cast(last_listed - first_seen + 1 as integer) as lifetime_days,
    first_seen = (select first_day from bounds) as left_censored
from with_gap
where date - last_listed <= 2

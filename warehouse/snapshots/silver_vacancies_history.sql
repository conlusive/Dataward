-- SCD2 history of vacancies: a new version is stored when the title, salary or description changes
-- (the row hash). dbt keeps dbt_valid_from / dbt_valid_to; the current version has dbt_valid_to = null.
{% snapshot silver_vacancies_history %}

{{
    config(
        target_schema='main',
        unique_key='id',
        strategy='check',
        check_cols=['row_hash'],
    )
}}

select
    id,
    source,
    title,
    company,
    salary_min,
    salary_max,
    salary_currency,
    content_hash,
    md5(concat_ws('|',
        coalesce(title, ''),
        coalesce(cast(salary_min as varchar), ''),
        coalesce(cast(salary_max as varchar), ''),
        coalesce(salary_currency, ''),
        content_hash
    )) as row_hash
from {{ source('silver', 'silver_vacancies') }}

{% endsnapshot %}

{% test unique_combination(model, column_names) %}

select {{ column_names | join(', ') }}, count(*) as rows_found
from {{ model }}
group by {{ column_names | join(', ') }}
having count(*) > 1

{% endtest %}

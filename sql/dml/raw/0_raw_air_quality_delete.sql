DELETE FROM raw.air_quality
WHERE (year = {{ year }} AND month = '{{ month }}')
   OR (datetime >= '{{ start_date }}' AND datetime < '{{ end_date }}');

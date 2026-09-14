-- PostgreSQL queries for Grafana.  Datasource: Kate_fitness, schema main.
-- Use a read-only database role.  $__timeFrom()/To() are Grafana macros.

-- 1. Financial dynamics: revenue, rent and gross profit by day.
SELECT
    s.date::timestamp AS "time",
    COALESCE(SUM(s.price), 0) AS revenue,
    COALESCE(SUM(s.rent_debt), 0) AS rent,
    COALESCE(SUM(s.price - s.rent_debt), 0) AS gross_profit
FROM main.schedule AS s
WHERE s.date >= $__timeFrom()::date
  AND s.date <= $__timeTo()::date
GROUP BY s.date
ORDER BY "time";

-- 2. Financial result by training type (bar chart/table).
SELECT
    t.type_train AS training_type,
    COUNT(s.id) AS sessions,
    COALESCE(SUM(s.price), 0) AS revenue,
    COALESCE(SUM(s.rent_debt), 0) AS rent,
    COALESCE(SUM(s.price - s.rent_debt), 0) AS gross_profit,
    ROUND(
        100.0 * SUM(s.price - s.rent_debt) / NULLIF(SUM(s.price), 0), 1
    ) AS margin_pct
FROM main.schedule AS s
LEFT JOIN main.trains AS t ON t.id = s.type_train_id
WHERE s.date >= $__timeFrom()::date
  AND s.date <= $__timeTo()::date
GROUP BY t.type_train
ORDER BY revenue DESC NULLS LAST;

-- 3. Sessions and group participants by day.
SELECT
    s.date::timestamp AS "time",
    COUNT(*) FILTER (WHERE COALESCE(s.is_group, false) = false) AS personal_sessions,
    COUNT(*) FILTER (WHERE COALESCE(s.is_group, false) = true) AS group_sessions,
    COALESCE(SUM(p.participant_count) FILTER (WHERE COALESCE(s.is_group, false)), 0)
        AS group_participants
FROM main.schedule AS s
LEFT JOIN LATERAL (
    SELECT COUNT(*) AS participant_count
    FROM main.schedule_participant AS sp
    WHERE sp.schedule_id = s.id
) AS p ON true
WHERE s.date >= $__timeFrom()::date
  AND s.date <= $__timeTo()::date
GROUP BY s.date
ORDER BY "time";

-- 4. Workload heatmap: column values are PostgreSQL DOW (0=Sunday).
SELECT
    EXTRACT(DOW FROM s.date)::int AS day_of_week,
    TO_CHAR(s.time, 'HH24:MI') AS slot,
    COUNT(*) AS sessions
FROM main.schedule AS s
WHERE s.date >= $__timeFrom()::date
  AND s.date <= $__timeTo()::date
GROUP BY 1, 2
ORDER BY 1, 2;

-- 5. Package sales by month.  This is cash received on package creation,
-- not training revenue.
SELECT
    DATE_TRUNC('month', a.created_at) AS "time",
    COUNT(*) AS packages_sold,
    COALESCE(SUM(a.summ), 0) AS cash_in,
    ROUND(AVG(a.summ), 2) AS average_package_amount
FROM main.accounting AS a
WHERE a.created_at >= $__timeFrom()
  AND a.created_at <= $__timeTo()
GROUP BY 1
ORDER BY "time";

-- 6. Open packages with actual usage.  Suitable for a table and alerts.
SELECT
    a.id AS package_id,
    CONCAT_WS(' ', c.name, c.surname) AS client,
    t.type_train AS training_type,
    a.created_at,
    a.count_train AS purchased_sessions,
    COUNT(s.id) AS used_sessions,
    a.count_train - COUNT(s.id) AS remaining_sessions,
    a.price_per_train,
    (a.count_train - COUNT(s.id)) * a.price_per_train AS remaining_value
FROM main.accounting AS a
JOIN main.client AS c ON c.id = a.client_id
LEFT JOIN main.trains AS t ON t.id = a.type_train_id
LEFT JOIN main.schedule AS s ON s.accounting_id = a.id
WHERE a.is_complete = false
GROUP BY a.id, c.id, t.id
ORDER BY remaining_sessions, a.created_at;

-- 7. Clients with no training in the selected inactivity period.
-- Use a Grafana interval variable ${inactive_days} with a numeric value.
WITH attendance AS (
    SELECT s.client_id, s.date FROM main.schedule AS s WHERE s.client_id IS NOT NULL
    UNION ALL
    SELECT sp.client_id, s.date
    FROM main.schedule_participant AS sp
    JOIN main.schedule AS s ON s.id = sp.schedule_id
)
SELECT
    c.id,
    CONCAT_WS(' ', c.name, c.surname) AS client,
    c.add_time,
    MAX(attendance.date) AS last_session_date,
    CURRENT_DATE - MAX(attendance.date) AS days_since_last_session
FROM main.client AS c
LEFT JOIN attendance ON attendance.client_id = c.id
WHERE c.inactive = false
GROUP BY c.id
HAVING MAX(attendance.date) IS NULL
    OR MAX(attendance.date) < CURRENT_DATE - (${inactive_days}::int)
ORDER BY last_session_date NULLS FIRST, client;

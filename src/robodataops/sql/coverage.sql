-- Aggregate one canonical state per episode before joining task targets.
WITH counts AS (
    SELECT task_id,
           COUNT(*) AS received,
           COUNT(*) FILTER (WHERE checked) AS checked,
           COUNT(*) FILTER (WHERE technical_clear) AS technical_clear,
           COUNT(*) FILTER (WHERE status = 'accepted') AS accepted,
           COUNT(*) FILTER (WHERE status = 'blocked') AS blocked,
           COUNT(*) FILTER (WHERE status = 'pending') AS pending,
           COUNT(*) FILTER (WHERE status = 'unchecked') AS unchecked
    FROM episode_states
    GROUP BY task_id
), task_coverage AS (
    SELECT t.*, COALESCE(c.received, 0) AS received,
           COALESCE(c.checked, 0) AS checked,
           COALESCE(c.technical_clear, 0) AS technical_clear,
           COALESCE(c.accepted, 0) AS accepted,
           COALESCE(c.blocked, 0) AS blocked,
           COALESCE(c.pending, 0) AS pending,
           COALESCE(c.unchecked, 0) AS unchecked,
           GREATEST(0, t.target - COALESCE(c.accepted, 0)) AS deficit,
           GREATEST(0, t.target - COALESCE(c.accepted, 0) - COALESCE(c.pending, 0)) AS optimistic_deficit
    FROM targets t LEFT JOIN counts c USING(task_id)
)
SELECT *, CASE WHEN target > 0 THEN LEAST(accepted, target)::DOUBLE / target ELSE NULL END AS attainment,
       CASE WHEN SUM(deficit) OVER () > 0 THEN deficit::DOUBLE / SUM(deficit) OVER () ELSE 0 END AS deficit_share
FROM task_coverage
ORDER BY task_id;

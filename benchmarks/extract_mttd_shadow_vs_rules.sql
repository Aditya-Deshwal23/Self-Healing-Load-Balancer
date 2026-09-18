-- Extract matched fault-to-incident detection timing for the Phase 1 lab.
-- Bind :environment_id and optionally :after_applied_at in a PostgreSQL client.
-- A fault is matched to the first incident in the same environment opened
-- during its active window. The five-minute grace covers worker loop latency.
--
-- The shadow signal is persisted in every ObservationWindow.metrics row, so
-- this query can capture a pre-incident shadow observation.

WITH matched_faults AS (
    SELECT DISTINCT ON (lf.id)
        lf.id AS fault_id,
        lf.environment_id,
        lf.scenario,
        lf.ground_truth_id,
        lf.applied_at,
        lf.cleared_at,
        lf.expires_at,
        i.id AS incident_id,
        i.operational_class,
        i.opened_at,
        i.resolved_at
    FROM lab_faults AS lf
    JOIN incidents AS i
      ON i.environment_id = lf.environment_id
     AND lf.applied_at IS NOT NULL
     AND i.opened_at >= lf.applied_at
     AND i.opened_at <= COALESCE(lf.cleared_at, lf.expires_at) + INTERVAL '5 minutes'
    WHERE lf.environment_id = :environment_id
      AND (:after_applied_at IS NULL OR lf.applied_at >= :after_applied_at)
    ORDER BY lf.id, i.opened_at
),
shadow_observations AS (
    SELECT DISTINCT ON (mf.fault_id)
        mf.fault_id,
        ow.ended_at AS shadow_observed_at,
        ow.metrics::jsonb -> 'fast_path_recommendations'
            AS shadow_statistical_signal
    FROM matched_faults AS mf
    JOIN observation_windows AS ow
      ON ow.environment_id = mf.environment_id
     AND ow.ended_at >= mf.applied_at
     AND ow.ended_at <= COALESCE(mf.cleared_at, mf.expires_at) + INTERVAL '5 minutes'
    WHERE ow.metrics::jsonb -> 'fast_path_recommendations' IS NOT NULL
      AND ow.metrics::jsonb -> 'fast_path_recommendations' <> '{}'::jsonb
    ORDER BY mf.fault_id, ow.ended_at
)
SELECT
    mf.fault_id,
    mf.ground_truth_id,
    mf.scenario,
    mf.operational_class,
    mf.applied_at AS fault_applied_at,
    mf.incident_id,
    mf.opened_at AS rule_detected_at,
    EXTRACT(EPOCH FROM (mf.opened_at - mf.applied_at))
        AS mttd_rules_seconds,
    so.shadow_observed_at,
    CASE
        WHEN so.shadow_observed_at IS NULL THEN NULL
        ELSE EXTRACT(EPOCH FROM (so.shadow_observed_at - mf.applied_at))
    END AS shadow_mttd_seconds,
    so.shadow_statistical_signal,
    mf.resolved_at
FROM matched_faults AS mf
LEFT JOIN shadow_observations AS so
  ON so.fault_id = mf.fault_id
ORDER BY mf.applied_at, mf.fault_id;

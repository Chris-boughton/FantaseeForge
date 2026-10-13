CREATE OR REPLACE TABLE features.model_training_v2_clean AS
SELECT *
FROM features.model_training_v2
WHERE target_fantasy_points IS NOT NULL
  AND fantasy_points_avg_l4 IS NOT NULL
  AND offense_pct_avg_l4 IS NOT NULL
  AND team_pass_attempts_avg_l4 IS NOT NULL;
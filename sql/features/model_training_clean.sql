CREATE OR REPLACE TABLE features.model_training_clean AS
SELECT *
FROM features.model_training
WHERE target_fantasy_points IS NOT NULL
  AND fantasy_points_avg_l4 IS NOT NULL;
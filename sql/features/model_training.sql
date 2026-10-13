CREATE OR REPLACE TABLE features.model_training AS
SELECT
    *,
    fantasy_points_ppr AS target_fantasy_points
FROM features.player_rolling;
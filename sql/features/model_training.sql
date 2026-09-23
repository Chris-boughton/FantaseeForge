CREATE OR REPLACE TABLE features.model_training AS
SELECT
    *,
    LEAD(fantasy_points_ppr) OVER (
        PARTITION BY player_id
        ORDER BY season, week, game_id
    ) AS target_fantasy_points
FROM features.player_rolling;
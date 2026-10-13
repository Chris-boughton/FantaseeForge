CREATE OR REPLACE TABLE features.model_training_v3 AS

SELECT
    v2.*,

    dm.defense_fpts_allowed_l4,
    dm.defense_targets_allowed_l4,
    dm.defense_receiving_yards_allowed_l4

FROM features.model_training_v2_clean v2

LEFT JOIN features.defense_matchup_v3 dm
    ON v2.season = dm.season
    AND v2.week = dm.week
    AND v2.game_id = dm.game_id
    AND v2.opponent_team = dm.defense_team
    AND v2.position = dm.position;
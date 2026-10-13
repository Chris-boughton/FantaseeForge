CREATE OR REPLACE TABLE features.model_training_v2 AS
SELECT
    mr.*,
    po.offense_pct,
    po.offense_pct_avg_l4,
    po.team_pass_attempts,
    po.team_pass_attempts_avg_l4
FROM features.model_training mr
LEFT JOIN features.player_opportunity po
    ON mr.season = po.season
    AND mr.week = po.week
    AND mr.game_id = po.game_id
    AND mr.player_id = po.player_id;
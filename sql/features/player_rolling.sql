CREATE OR REPLACE TABLE features.player_rolling AS
SELECT
    season,
    week,
    game_id,
    player_id,
    player_display_name,
    position,
    position_group,
    team,
    opponent_team,
    fantasy_points_ppr,
    AVG(fantasy_points_ppr) OVER (
        PARTITION BY player_id
        ORDER BY season, week, game_id
        ROWS BETWEEN 2 PRECEDING AND 1 PRECEDING
    ) AS fantasy_points_avg_l2,
    AVG(fantasy_points_ppr) OVER (
        PARTITION BY player_id
        ORDER BY season, week, game_id
        ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    ) AS fantasy_points_avg_l4,
    AVG(fantasy_points_ppr) OVER (
        PARTITION BY player_id
        ORDER BY season, week, game_id
        ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
    ) AS fantasy_points_avg_l8,
    AVG(targets) OVER (
        PARTITION BY player_id
        ORDER BY season, week, game_id
        ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    ) AS targets_avg_l4,
    AVG(receptions) OVER (
        PARTITION BY player_id
        ORDER BY season, week, game_id
        ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    ) AS receptions_avg_l4,
    AVG(receiving_yards) OVER (
        PARTITION BY player_id
        ORDER BY season, week, game_id
        ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    ) AS receiving_yards_avg_l4,
    AVG(rushing_attempts) OVER (
        PARTITION BY player_id
        ORDER BY season, week, game_id
        ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    ) AS rushing_attempts_avg_l4,
    AVG(rushing_yards) OVER (
        PARTITION BY player_id
        ORDER BY season, week, game_id
        ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    ) AS rushing_yards_avg_l4
FROM staging.player_game;
CREATE OR REPLACE TABLE staging.player_game AS
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
    attempts AS pass_attempts,
    completions,
    passing_yards,
    passing_tds,
    passing_interceptions,
    carries AS rushing_attempts,
    rushing_yards,
    rushing_tds,
    receptions,
    targets,
    receiving_yards,
    receiving_tds,
    COALESCE(receptions, 0) 
        + COALESCE(rushing_yards, 0) / 10.0 
        + COALESCE(receiving_yards, 0) / 10.0 
        + COALESCE(rushing_tds, 0) * 6 
        + COALESCE(receiving_tds, 0) * 6 
        + COALESCE(passing_yards, 0) / 25.0 
        + COALESCE(passing_tds, 0) * 4 
        - COALESCE(passing_interceptions, 0) * 2 
        AS fantasy_points_ppr
FROM raw.player_stats
WHERE season_type = 'REG' 
    AND position IN ('QB', 'RB', 'WR', 'TE');

CREATE OR REPLACE TABLE staging.snap_usage AS 
SELECT 
    s.season,
    s.week,
    s.game_id,
    p.gsis_id AS player_id,
    s.player,
    s.team,
    s.opponent,
    s.offense_snaps,
    s.offense_pct,
    s.defense_snaps,
    s.defense_pct
FROM raw.snap_counts s
LEFT JOIN raw.players p
    ON s.pfr_player_id = p.pfr_id;

CREATE OR REPLACE TABLE features.player_game AS
SELECT
    pg.*,
    su.offense_snaps,
    su.offense_pct,
    su.offense_pct AS snap_share
FROM staging.player_game pg
LEFT JOIN staging.snap_usage su
    ON pg.player_id = su.player_id
    AND pg.game_id = su.game_id;

CREATE OR REPLACE TABLE staging.team_passing AS
SELECT
    season,
    week,
    game_id,
    team,
    SUM(COALESCE(pass_attempts, 0)) AS team_pass_attempts
FROM staging.player_game
GROUP BY
    season,
    week,
    game_id,
    team;

CREATE OR REPLACE TABLE features.player_game_usage AS
SELECT
    pg.*,
    tp.team_pass_attempts,
    CASE
        WHEN tp.team_pass_attempts > 0
        THEN pg.targets / tp.team_pass_attempts
        ELSE NULL
    END AS target_share
FROM features.player_game pg
LEFT JOIN staging.team_passing tp
    ON pg.season = tp.season
    AND pg.week = tp.week
    AND pg.game_id = tp.game_id
    AND pg.team = tp.team;

CREATE OR REPLACE TABLE features.defense_position_game AS
SELECT
    season,
    week,
    game_id,
    opponent_team AS defense_team,
    position,
    SUM(COALESCE(targets, 0)) AS targets_allowed,
    SUM(COALESCE(receptions, 0)) AS receptions_allowed,
    SUM(COALESCE(receiving_yards, 0)) AS receiving_yards_allowed,
    SUM(COALESCE(receiving_tds, 0)) AS receiving_tds_allowed,
    SUM(COALESCE(rushing_attempts, 0)) AS rushing_attempts_allowed,
    SUM(COALESCE(rushing_yards, 0)) AS rushing_yards_allowed,
    SUM(COALESCE(rushing_tds, 0)) AS rushing_tds_allowed,
    SUM(fantasy_points_ppr) AS fantasy_points_allowed
FROM staging.player_game
WHERE position IN ('QB', 'RB', 'WR', 'TE')
GROUP BY 
    season,
    week,
    game_id,
    opponent_team,
    position;

CREATE OR REPLACE TABLE features.defense_position_rolling AS
SELECT 
    *,
    AVG(fantasy_points_allowed)
        OVER (
            PARTITION BY defense_team, position
            ORDER BY season, week
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        )
        AS fpts_allowed_l4,    
    AVG(targets_allowed)
        OVER (
            PARTITION BY defense_team, position
            ORDER BY season, week
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        )
        AS targets_allowed_l4,     
    AVG(receiving_yards_allowed)
        OVER (
            PARTITION BY defense_team, position
            ORDER BY season, week
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        )
        AS receiving_yards_allowed_l4
FROM features.defense_position_game;

CREATE OR REPLACE TABLE features.player_rolling AS
SELECT
    *,
    SUM(COALESCE(targets, 0))
        OVER (
            PARTITION BY player_id
            ORDER BY season, week
            ROWS BETWEEN 2 PRECEDING AND 1 PRECEDING
        )
        AS targets_l2,
    SUM(COALESCE(targets, 0))
        OVER (
            PARTITION BY player_id
            ORDER BY season, week
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        )
        AS targets_l4,
    SUM(COALESCE(targets, 0))
        OVER (
            PARTITION BY player_id
            ORDER BY season, week
            ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
        )
        AS targets_l8,
    AVG(fantasy_points_ppr)
        OVER (
            PARTITION BY player_id
            ORDER BY season, week
            ROWS BETWEEN 2 PRECEDING AND 1 PRECEDING
        )
        AS fantasy_points_l2,
    AVG(fantasy_points_ppr)
        OVER (
            PARTITION BY player_id
            ORDER BY season, week
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        )
        AS fantasy_points_l4,
    AVG(fantasy_points_ppr)
        OVER (
            PARTITION BY player_id
            ORDER BY season, week
            ROWS BETWEEN 8 PRECEDING AND 1 PRECEDING
        )
        AS fantasy_points_l8,
    AVG(receiving_yards)
        OVER (
            PARTITION BY player_id
            ORDER BY season, week
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        )
        AS receiving_yards_l4,
    AVG(rushing_yards)
        OVER (
            PARTITION BY player_id
            ORDER BY season, week
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        )
        AS rushing_yards_l4
FROM features.player_game_usage;

CREATE OR REPLACE TABLE features.training_data AS
SELECT
    pr.season,
    pr.week,
    pr.game_id,
    pr.player_id,
    pr.player_display_name,
    pr.position,
    pr.team,
    pr.opponent_team,
    pr.targets_l2,
    pr.targets_l4,
    pr.targets_l8,
    pr.target_share,
    pr.snap_share,
    pr.receptions,
    pr.receiving_yards_l4,
    pr.rushing_attempts,
    pr.rushing_yards_l4,
    pr.fantasy_points_l2,
    pr.fantasy_points_l4,
    pr.fantasy_points_l8,
    dp.fpts_allowed_l4,
    dp.targets_allowed_l4,
    dp.receiving_yards_allowed_l4,
    pr.fantasy_points_ppr AS target_fantasy_points
FROM features.player_rolling pr
LEFT JOIN features.defense_position_rolling dp
    ON pr.season = dp.season
    AND pr.week = dp.week
    AND pr.game_id = dp.game_id
    AND pr.opponent_team = dp.defense_team
    AND pr.position = dp.position;

/* Only train for players that have a 4 game history - otherwise it's meaningless. */
/* Will develop a better cold start system in the future. */
CREATE OR REPLACE TABLE features.training_ready AS
SELECT *
FROM features.training_data
WHERE targets_l4 IS NOT NULL
    AND fantasy_points_l4 IS NOT NULL;

CREATE OR REPLACE TABLE marts.upcoming_games AS
SELECT
    season,
    week,
    game_id,
    home_team,
    away_team
FROM raw.schedules
WHERE season = (
    SELECT MAX(season)
    FROM raw.schedules
    )
    AND result IS NULL;

CREATE OR REPLACE TABLE marts.model_metadata AS 
SELECT 
    'xgb_v1' AS model_version,
    2019 AS training_start,
    2025 AS training_end,
    CURRENT_TIMESTAMP AS created_at;
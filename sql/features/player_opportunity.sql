CREATE OR REPLACE TABLE features.player_opportunity AS
WITH player_usage AS (
    SELECT
        pg.season,
        pg.week,
        pg.game_id,
        pg.player_id,
        pg.player_display_name,
        pg.position,
        pg.position_group,
        pg.team,
        pg.opponent_team,
        pg.fantasy_points_ppr,
        su.offense_snaps,
        su.offense_pct,
        tp.team_pass_attempts
    FROM staging.player_game pg
    LEFT JOIN staging.snap_usage su
        ON pg.season = su.season
        AND pg.week = su.week
        AND pg.game_id = su.game_id
        AND pg.player_id = su.player_id
    LEFT JOIN staging.team_passing tp
        ON pg.season = tp.season
        AND pg.week = tp.week
        AND pg.game_id = tp.game_id
        AND pg.team = tp.team
)
SELECT
    *,
    AVG(offense_pct) OVER (
        PARTITION BY player_id
        ORDER BY season, week, game_id
        ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    ) AS offense_pct_avg_l4,
    AVG(team_pass_attempts) OVER (
        PARTITION BY player_id
        ORDER BY season, week, game_id
        ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
    ) AS team_pass_attempts_avg_l4
FROM player_usage;
CREATE OR REPLACE TABLE features.defense_matchup_v3 AS

WITH defense_games AS (

    SELECT
        season,
        week,
        game_id,
        opponent_team AS defense_team,
        position,

        SUM(fantasy_points_ppr) AS fantasy_points_allowed,

        SUM(COALESCE(targets, 0)) AS targets_allowed,

        SUM(COALESCE(receiving_yards, 0)) AS receiving_yards_allowed

    FROM staging.player_game

    WHERE position IN ('QB', 'RB', 'WR', 'TE')

    GROUP BY
        season,
        week,
        game_id,
        opponent_team,
        position

),

rolling AS (

    SELECT
        *,

        AVG(fantasy_points_allowed) OVER (
            PARTITION BY defense_team, position
            ORDER BY season, week, game_id
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        ) AS defense_fpts_allowed_l4,

        AVG(targets_allowed) OVER (
            PARTITION BY defense_team, position
            ORDER BY season, week, game_id
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        ) AS defense_targets_allowed_l4,

        AVG(receiving_yards_allowed) OVER (
            PARTITION BY defense_team, position
            ORDER BY season, week, game_id
            ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING
        ) AS defense_receiving_yards_allowed_l4

    FROM defense_games

)

SELECT *
FROM rolling;
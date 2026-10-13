CREATE OR REPLACE TABLE features.upcoming_player_features AS

WITH player_history AS (

    SELECT
        player_id,
        season,
        week,
        game_id,
        fantasy_points_ppr,
        targets,
        receptions,
        receiving_yards,
        rushing_attempts,
        rushing_yards,

        ROW_NUMBER() OVER (
            PARTITION BY player_id
            ORDER BY season DESC, week DESC, game_id DESC
        ) AS rn

    FROM staging.player_game pg

    WHERE EXISTS (
    SELECT 1
    FROM features.prediction_week pw
    WHERE pg.season < pw.season
       OR (
           pg.season = pw.season
           AND pg.week < pw.week
       )
    )
),

player_features AS (

    SELECT
        player_id,

        AVG(fantasy_points_ppr) FILTER (
            WHERE rn <= 2
        ) AS fantasy_points_avg_l2,

        AVG(fantasy_points_ppr) FILTER (
            WHERE rn <= 4
        ) AS fantasy_points_avg_l4,

        AVG(fantasy_points_ppr) FILTER (
            WHERE rn <= 8
        ) AS fantasy_points_avg_l8,

        AVG(targets) FILTER (
            WHERE rn <= 4
        ) AS targets_avg_l4,

        AVG(receptions) FILTER (
            WHERE rn <= 4
        ) AS receptions_avg_l4,

        AVG(receiving_yards) FILTER (
            WHERE rn <= 4
        ) AS receiving_yards_avg_l4,

        AVG(rushing_attempts) FILTER (
            WHERE rn <= 4
        ) AS rushing_attempts_avg_l4,

        AVG(rushing_yards) FILTER (
            WHERE rn <= 4
        ) AS rushing_yards_avg_l4

    FROM player_history

    GROUP BY player_id

),

opportunity_history AS (

    SELECT
        pg.player_id,
        pg.season,
        pg.week,
        pg.game_id,
        su.offense_pct,
        tp.team_pass_attempts,

        ROW_NUMBER() OVER (
            PARTITION BY pg.player_id
            ORDER BY pg.season DESC, pg.week DESC, pg.game_id DESC
        ) AS rn

    FROM staging.player_game pg

    LEFT JOIN staging.snap_usage su
        ON pg.player_id = su.player_id
        AND pg.game_id = su.game_id

    LEFT JOIN staging.team_passing tp
        ON pg.team = tp.team
        AND pg.game_id = tp.game_id

    WHERE EXISTS (
        SELECT 1
        FROM features.prediction_week pw
        WHERE pg.season < pw.season
            OR (
                pg.season = pw.season
                AND pg.week < pw.week
            )
        )
),

opportunity_features AS (

    SELECT
        player_id,

        AVG(offense_pct) FILTER (
            WHERE rn <= 4
        ) AS offense_pct_avg_l4,

        AVG(team_pass_attempts) FILTER (
            WHERE rn <= 4
        ) AS team_pass_attempts_avg_l4

    FROM opportunity_history

    GROUP BY player_id

),

defense_history AS (

    SELECT
        defense_team,
        position,
        season,
        week,
        game_id,
        fantasy_points_allowed,
        targets_allowed,
        receiving_yards_allowed,

        ROW_NUMBER() OVER (
            PARTITION BY defense_team, position
            ORDER BY season DESC, week DESC, game_id DESC
        ) AS rn

    FROM features.defense_matchup_v3 d

    WHERE EXISTS (
    SELECT 1
    FROM features.prediction_week pw
    WHERE d.season < pw.season
       OR (
           d.season = pw.season
           AND d.week < pw.week
       )
    )
),

defense_features AS (

    SELECT
        defense_team,
        position,

        AVG(fantasy_points_allowed) FILTER (
            WHERE rn <= 4
        ) AS defense_fpts_allowed_l4,

        AVG(targets_allowed) FILTER (
            WHERE rn <= 4
        ) AS defense_targets_allowed_l4,

        AVG(receiving_yards_allowed) FILTER (
            WHERE rn <= 4
        ) AS defense_receiving_yards_allowed_l4

    FROM defense_history

    GROUP BY defense_team, position

)

SELECT
    p.*,

    pf.fantasy_points_avg_l2,
    pf.fantasy_points_avg_l4,
    pf.fantasy_points_avg_l8,
    pf.targets_avg_l4,
    pf.receptions_avg_l4,
    pf.receiving_yards_avg_l4,
    pf.rushing_attempts_avg_l4,
    pf.rushing_yards_avg_l4,

    op.offense_pct_avg_l4,
    op.team_pass_attempts_avg_l4,

    df.defense_fpts_allowed_l4,
    df.defense_targets_allowed_l4,
    df.defense_receiving_yards_allowed_l4

FROM features.upcoming_player_pool p

LEFT JOIN player_features pf
    ON p.player_id = pf.player_id

LEFT JOIN opportunity_features op
    ON p.player_id = op.player_id

LEFT JOIN defense_features df
    ON p.opponent_team = df.defense_team
    AND p.position = df.position

WHERE p.status = 'ACT';
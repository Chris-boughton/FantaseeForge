CREATE OR REPLACE TABLE features.upcoming_player_pool AS

WITH next_week AS (
    SELECT
        s.season,
        s.week,
        s.game_id,
        s.home_team,
        s.away_team,
        s.gameday,
        s.gametime
    FROM raw.schedules s
    INNER JOIN features.prediction_week pw
        ON s.season = pw.season
       AND s.week = pw.week
    WHERE s.game_type = 'REG'
),

scheduled_teams AS (
    SELECT
        season,
        week,
        game_id,
        home_team AS team,
        away_team AS opponent_team,
        gameday,
        gametime,
        TRUE AS is_home
    FROM next_week

    UNION ALL

    SELECT
        season,
        week,
        game_id,
        away_team AS team,
        home_team AS opponent_team,
        gameday,
        gametime,
        FALSE AS is_home
    FROM next_week
),

latest_roster AS (
    SELECT
        r.gsis_id AS player_id,
        r.full_name AS player_display_name,
        r.team,
        r.position,
        r.status,
        r.week AS roster_week

    FROM raw.rosters_weekly r

    INNER JOIN features.prediction_week pw
        ON r.season = pw.season

    WHERE r.game_type = 'REG'
      AND r.week < pw.week
      AND r.position IN ('QB', 'RB', 'WR', 'TE')
      AND r.gsis_id IS NOT NULL

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY r.gsis_id
        ORDER BY r.week DESC
    ) = 1
),

latest_player_game AS (
    SELECT
        pg.player_id,
        pg.team AS historical_team,
        pg.week AS last_played_week

    FROM staging.player_game pg

    WHERE pg.season < (
        SELECT season FROM features.prediction_week
    )
    OR (
        pg.season = (
            SELECT season FROM features.prediction_week
        )
        AND pg.week < (
            SELECT week FROM features.prediction_week
        )
    )

    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY pg.player_id
        ORDER BY
            pg.season DESC,
            pg.week DESC,
            pg.game_id DESC
    ) = 1
)

SELECT
    st.season,
    st.week,
    st.game_id,

    r.player_id,
    r.player_display_name,
    r.position,
    r.team,

    st.opponent_team,
    st.is_home,
    st.gameday,
    st.gametime,

    r.status,
    r.roster_week,

    pg.last_played_week,
    pg.historical_team

FROM latest_roster r

INNER JOIN scheduled_teams st
    ON r.team = st.team

LEFT JOIN latest_player_game pg
    ON r.player_id = pg.player_id;
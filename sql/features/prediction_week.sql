
CREATE OR REPLACE TABLE features.prediction_week AS

WITH regular_season_weeks AS (

    SELECT
        season,
        week,
        MIN(TRY_CAST(gameday AS DATE)) AS first_game_date,
        MAX(TRY_CAST(gameday AS DATE)) AS last_game_date,
        COUNT(*) AS scheduled_games,
        COUNT(*) FILTER (
            WHERE home_score IS NOT NULL
              AND away_score IS NOT NULL
        ) AS completed_games

    FROM raw.schedules

    WHERE game_type = 'REG'

    GROUP BY season, week

),

eligible_weeks AS (

    SELECT
        season,
        week,
        first_game_date,
        last_game_date,
        scheduled_games,
        completed_games

    FROM regular_season_weeks

    WHERE first_game_date > CURRENT_DATE
      AND completed_games = 0
      AND scheduled_games > 0

)

SELECT
    season,
    week,
    first_game_date

FROM eligible_weeks

ORDER BY first_game_date, season, week

LIMIT 1;

# Fantasee Forge

## Data-forged fantasy football projections
Fantasee Forge is an automated NFL fantasy football analytics platform. The tool was developed to predict fantasy football performance based on a number of metrics that are guided through feature construction, modeling and evaluation. The tool attempts to take deeper insights to produce more accurate fantasy football projections compared to simple models and metrics.

The project combines the following software to produce the overall output:

---
**_NOTE:_**
Coloured circles reflect software usage: 

🔴 Data<p></p>
🟡 Data manipulation, wrangling, storage and feature construction<p></p>
🟢 Modeling, predictions and evaluation<p></p>
🔵 CI/CD<p></p>
🟣 Website deployment and output generation

---


:red_circle: nflverse<p></p>
:yellow_circle: Python<p></p>
:yellow_circle: SQL<p></p>
:yellow_circle: DuckDB<p></p>
:green_circle: XGBoost<p></p>
:large_blue_circle: GitHub Actions<p></p>
:large_blue_circle: GitHub Pages <p></p>
:purple_circle: HTML/JavaScript



## Main features:

:hammer_and_pick: The Forge :hammer_and_pick: Overall introduction and engine running the forge.

:trophy: Matchup Forge :trophy: Detailing top picks and roles that have favourable opponents.

:handball_person: Player Forge :handball_person: Individual performance insights.

:hotsprings: Hot Forge :hotsprings: Players that are rising up rankings due to recent performance or favourable matchups.

:snowflake: Cold Forge :snowflake: Players that are falling down rankings due to recent performance or unfavourable matchups.

:atom: Forge Lab :atom: Backend model performance metrics, evaluation and runnings.


### Architecture: NFL data → parquet → DuckDB → features → model → predictions → website


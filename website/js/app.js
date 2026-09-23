async function loadPredictions() {
    const response = await fetch(
        "data/predictions.json"
    );
    const predictions = await response.json();
    const table = document.querySelector(
        "#projection-table tbody"
    );
    table.innerHTML = "";
    predictions
        .sort(
            (a, b) =>
                a.projection - b.projection
        )
        .reverse()
        .slice(0, 100)
        .forEach(player => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td>${player.rank ?? ""}</td>
                <td>${player.player_display_name ?? ""}</td>
                <td>${player.position ?? ""}</td>
                <td>${player.team ?? ""}</td>
                <td>${player.opponent_team ?? ""}</td>
                <td>${Number(player.projection).toFixed(1)}</td>
                <td>${Number(player.floor ?? 0).toFixed(1)}</td>
                <td>${Number(player.ceiling ?? 0).toFixed(1)}</td> `;
            table.appendChild(row);
        });
}
loadPredictions();
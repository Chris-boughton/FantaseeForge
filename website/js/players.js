let players = [];

async function loadPlayers() {
    const response = await fetch(
        "data/predictions.json"
    );
    players = await response.json();
    renderPlayers(players);
}
function renderPlayers(data) {
    const container = document.querySelector(
        "#player-results"
    );
    container.innerHTML = "";
    data.slice(0, 50).forEach(player => {
        const card = document.createElement("div");
        card.innerHTML = `
            <h2> ${player.player_display_name} </h2>
            <p> ${player.position} — ${player.team} </p>
            <p> Projection: ${Number(player.projection).toFixed(1)} </p>
            <p> Floor: ${Number(player.floor ?? 0).toFixed(1)} </p>
            <p> Ceiling: ${Number(player.ceiling ?? 0).toFixed(1)} </p>
        `;
        container.appendChild(card);
     });
    }
    document
        .querySelector("#player-search")
        .addEventListener(
            "input",
            event => {
                const search =
                    event.target.value
                        .toLowerCase();
                const filtered =
                    players.filter(
                        player =>
                            player
                                .player_display_name
                                .toLowerCase()
                                .includes(search)
                    );
                renderPlayers(filtered);
            }
        );
loadPlayers();
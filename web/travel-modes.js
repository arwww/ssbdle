"use strict";


window.SSBDLE_TRAVEL_MODES = {
    "stuttgart-rail": {
        id: "stuttgart-rail",
        name: "Stuttgart S- & U-Bahn",
        shortName: "Stuttgart Rail",

        description:
            "S-Bahn und Stadtbahn innerhalb des Stuttgarter Stadtgebiets.",

        enabled: true,
        status: "JETZT Spielen",

        dataPath:
            "data/travel/stuttgart-rail",

        routeTypes: [
            "109",
            "402",
        ],
    },

    "vvs-rail": {
        id: "vvs-rail",
        name: "VVS-Bahnnetz",
        shortName: "VVS Rail",

        description:
            "S-Bahn und Stadtbahn im gesamten VVS-Gebiet.",

        enabled: false,
        status: "Coming Soon",

        dataPath:
            "data/travel/vvs-rail",

        routeTypes: [
            "109",
            "402",
            "1400",
        ],
    },

    "full-vvs": {
        id: "full-vvs",
        name: "VVS Komplett",
        shortName: "VVS Komplett",

        description:
            "Das vollständige Netz mit S-Bahn, Stadtbahn und Bus.",

        enabled: false,
        status: "OH NEIN DER EURTER Coming Soon",

        dataPath:
            "data/travel/full-vvs",

        routeTypes: [
            "3",
            "109",
            "402",
            "1400",
        ],
    },
};


function resolveActiveTravelMode() {
    const modes = (
        window.SSBDLE_TRAVEL_MODES
    );

    const parameters = (
        new URLSearchParams(
            window.location.search
        )
    );

    const requestedModeId = (
        parameters.get("mode")
    );

    const requestedMode = (
        requestedModeId
            ? modes[requestedModeId]
            : null
    );

    if (
        requestedMode
        && requestedMode.enabled
    ) {
        return requestedMode;
    }

    return modes[
        "stuttgart-rail"
    ];
}


window.SSBDLE_ACTIVE_TRAVEL_MODE = (
    resolveActiveTravelMode()
);


function createModeCard(
    mode,
    activeMode
) {
    const card = document.createElement(
        "article"
    );

    const isActive = (
        mode.id === activeMode.id
    );

    card.className = [
        "travel-mode-card",

        isActive
            ? "active"
            : "",

        mode.enabled
            ? ""
            : "disabled",
    ]
        .filter(Boolean)
        .join(" ");

    const headingRow = (
        document.createElement(
            "div"
        )
    );

    headingRow.className = (
        "travel-mode-heading"
    );

    const title = document.createElement(
        "h3"
    );

    title.textContent = mode.name;

    const status = document.createElement(
        "span"
    );

    status.className = (
        "travel-mode-status"
    );

    if (isActive) {
        status.textContent = "Aktiv";
    } else {
        status.textContent = (
            mode.status
        );
    }

    headingRow.append(
        title,
        status
    );

    const description = (
        document.createElement(
            "p"
        )
    );

    description.textContent = (
        mode.description
    );

    const routeTypes = (
        document.createElement(
            "div"
        )
    );

    routeTypes.className = (
        "travel-mode-tags"
    );

    const tagTexts = [];

    if (
        mode.routeTypes.includes("109")
    ) {
        tagTexts.push("S-Bahn");
    }

    if (
        mode.routeTypes.includes("402")
    ) {
        tagTexts.push("Stadtbahn");
    }

    if (
        mode.routeTypes.includes("1400")
    ) {
        tagTexts.push("Sonderbahn");
    }

    if (
        mode.routeTypes.includes("3")
    ) {
        tagTexts.push("Bus");
    }

    for (
        const tagText
        of tagTexts
    ) {
        const tag = (
            document.createElement(
                "span"
            )
        );

        tag.textContent = tagText;

        routeTypes.append(
            tag
        );
    }

    const button = (
        document.createElement(
            "button"
        )
    );

    button.type = "button";

    if (!mode.enabled) {
        button.className = (
            "secondary-button"
        );

        button.textContent = (
            "Coming Soon"
        );

        button.disabled = true;
    } else if (isActive) {
        button.className = (
            "primary-button"
        );

        button.textContent = (
            "Ausgewählt"
        );

        button.disabled = true;
    } else {
        button.className = (
            "primary-button"
        );

        button.textContent = (
            "Modus wählen"
        );

        button.addEventListener(
            "click",
            () => {
                const parameters = (
                    new URLSearchParams(
                        window.location.search
                    )
                );

                parameters.set(
                    "mode",
                    mode.id
                );

                window.location.search = (
                    parameters.toString()
                );
            }
        );
    }

    card.append(
        headingRow,
        description,
        routeTypes,
        button
    );

    return card;
}


function renderTravelModeSelection() {
    const grid = document.getElementById(
        "travel-mode-grid"
    );

    if (!grid) {
        return;
    }

    const activeMode = (
        window
            .SSBDLE_ACTIVE_TRAVEL_MODE
    );

    const modes = Object.values(
        window.SSBDLE_TRAVEL_MODES
    );

    grid.replaceChildren();

    for (
        const mode
        of modes
    ) {
        grid.append(
            createModeCard(
                mode,
                activeMode
            )
        );
    }

    const activeModeLabel = (
        document.getElementById(
            "active-mode-label"
        )
    );

    if (activeModeLabel) {
        activeModeLabel.textContent = (
            activeMode.name
        );
    }

    document.title = (
        `${activeMode.name} – `
        + "SSBdle Travel Mode"
    );
}


document.addEventListener(
    "DOMContentLoaded",
    renderTravelModeSelection
);
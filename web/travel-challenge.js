"use strict";


const CHALLENGE_CONFIG = {
    minimumTravelSeconds: 15 * 60,
    maximumTravelSeconds: 60 * 60,
    minimumRideStops: 5,
    maximumTransfers: 3,
    maximumAttempts: 35,
};


let activeChallenge = null;

const challengeDom = {};


/* -------------------------------------------------------------------------- */
/* Hilfsfunktionen                                                            */
/* -------------------------------------------------------------------------- */


function challengeDelay(milliseconds) {
    return new Promise(
        resolve => {
            window.setTimeout(
                resolve,
                milliseconds
            );
        }
    );
}


function challengeHashString(value) {
    const text = String(value);

    let hash = 2166136261;

    for (
        let index = 0;
        index < text.length;
        index += 1
    ) {
        hash ^= text.charCodeAt(
            index
        );

        hash = Math.imul(
            hash,
            16777619
        );
    }

    return hash >>> 0;
}


function createSeededRandom(seedText) {
    let state = challengeHashString(
        seedText
    );

    return function seededRandom() {
        state += 0x6D2B79F5;

        let value = state;

        value = Math.imul(
            value ^ (
                value >>> 15
            ),
            value | 1
        );

        value ^= (
            value
            + Math.imul(
                value ^ (
                    value >>> 7
                ),
                value | 61
            )
        );

        return (
            (
                value ^ (
                    value >>> 14
                )
            ) >>> 0
        ) / 4294967296;
    };
}


function getLocalDateKey() {
    const today = new Date();

    const year = today.getFullYear();

    const month = String(
        today.getMonth() + 1
    ).padStart(
        2,
        "0"
    );

    const day = String(
        today.getDate()
    ).padStart(
        2,
        "0"
    );

    return (
        `${year}-${month}-${day}`
    );
}


function getFormattedDate() {
    return new Intl.DateTimeFormat(
        "de-DE",
        {
            weekday: "long",
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
        }
    ).format(
        new Date()
    );
}


function pickRandomItem(
    values,
    randomFunction
) {
    if (values.length === 0) {
        return null;
    }

    const index = Math.floor(
        randomFunction()
        * values.length
    );

    return values[
        Math.min(
            index,
            values.length - 1
        )
    ];
}


function getChallengeCandidateIds() {
    return Object.entries(
        travelData.stationMoves
    )
        .filter(
            ([
                stationId,
                services,
            ]) => (
                travelData.stationById.has(
                    stationId
                )
                && Array.isArray(
                    services
                )
                && services.length >= 2
            )
        )
        .map(
            ([
                stationId,
            ]) => stationId
        );
}


function getChallengeDifficulty(
    bestRoute
) {
    const minutes = (
        bestRoute.actualTimeSeconds
        / 60
    );

    if (
        minutes <= 28
        && bestRoute.transfers <= 1
    ) {
        return {
            key: "easy",
            label: "Leicht",
        };
    }

    if (
        minutes <= 45
        && bestRoute.transfers <= 2
    ) {
        return {
            key: "medium",
            label: "Mittel",
        };
    }

    return {
        key: "hard",
        label: "Schwer",
    };
}


/* -------------------------------------------------------------------------- */
/* Challenge suchen                                                           */
/* -------------------------------------------------------------------------- */


async function findPlayableChallenge(
    randomFunction
) {
    const candidateIds = (
        getChallengeCandidateIds()
    );

    if (candidateIds.length < 2) {
        throw new Error(
            "Es gibt nicht genügend Stationen für eine Challenge."
        );
    }

    let fallbackChallenge = null;

    for (
        let attempt = 0;
        attempt
        < CHALLENGE_CONFIG.maximumAttempts;
        attempt += 1
    ) {
        const startStationId = (
            pickRandomItem(
                candidateIds,
                randomFunction
            )
        );

        const targetStationId = (
            pickRandomItem(
                candidateIds,
                randomFunction
            )
        );

        if (
            !startStationId
            || !targetStationId
            || startStationId
            === targetStationId
        ) {
            continue;
        }

        const bestRoute = findBestRoute(
            startStationId,
            targetStationId,
            START_SERVICE
        );

        if (!bestRoute) {
            continue;
        }

        const challenge = {
            startStationId,
            targetStationId,
            bestRoute,
            difficulty: (
                getChallengeDifficulty(
                    bestRoute
                )
            ),
        };

        if (!fallbackChallenge) {
            fallbackChallenge = (
                challenge
            );
        }

        const hasSuitableTime = (
            bestRoute.actualTimeSeconds
            >= CHALLENGE_CONFIG
                .minimumTravelSeconds
            && bestRoute.actualTimeSeconds
            <= CHALLENGE_CONFIG
                .maximumTravelSeconds
        );

        const hasEnoughStops = (
            bestRoute.rideStops
            >= CHALLENGE_CONFIG
                .minimumRideStops
        );

        const hasSuitableTransfers = (
            bestRoute.transfers
            <= CHALLENGE_CONFIG
                .maximumTransfers
        );

        if (
            hasSuitableTime
            && hasEnoughStops
            && hasSuitableTransfers
        ) {
            return challenge;
        }

        if (
            attempt > 0
            && attempt % 5 === 0
        ) {
            await challengeDelay(0);
        }
    }

    if (fallbackChallenge) {
        return fallbackChallenge;
    }

    throw new Error(
        "Es konnte keine spielbare Challenge erzeugt werden."
    );
}


/* -------------------------------------------------------------------------- */
/* Challenge-Oberfläche                                                       */
/* -------------------------------------------------------------------------- */


function createChallengeInterface() {
    const setupPanel = (
        document.getElementById(
            "setup-panel"
        )
    );

    const stationForm = (
        setupPanel.querySelector(
            ".station-form"
        )
    );

    const panelHeading = (
        setupPanel.querySelector(
            ".panel-heading"
        )
    );

    const stepLabel = (
        panelHeading.querySelector(
            ".step-label"
        )
    );

    const heading = (
        panelHeading.querySelector(
            "h2"
        )
    );

    const description = (
        panelHeading.querySelector(
            "p:last-child"
        )
    );

    stepLabel.textContent = (
        "Heutige Challenge"
    );

    heading.textContent = (
        "Finde den besten Weg"
    );

    description.textContent = (
        "Start und Ziel werden vorgegeben. "
        + "Du entscheidest selbst, welche Linien "
        + "und Ausstiegsstationen du verwendest."
    );

    stationForm.classList.add(
        "hidden"
    );

    const challengeCard = (
        document.createElement(
            "div"
        )
    );

    challengeCard.className = (
        "challenge-card"
    );

    challengeCard.innerHTML = `
        <div class="challenge-stop">
            <span class="challenge-stop-label">
                Start
            </span>

            <strong id="challenge-start-name">
                Wird ausgewählt …
            </strong>
        </div>

        <div
            class="challenge-arrow"
            aria-hidden="true"
        >
            →
        </div>

        <div class="challenge-stop">
            <span class="challenge-stop-label">
                Ziel
            </span>

            <strong id="challenge-target-name">
                Wird ausgewählt …
            </strong>
        </div>
    `;

    panelHeading.insertAdjacentElement(
        "afterend",
        challengeCard
    );

    const challengeMeta = (
        document.createElement(
            "div"
        )
    );

    challengeMeta.className = (
        "challenge-meta"
    );

    challengeMeta.innerHTML = `
        <span
            id="challenge-mode"
            class="challenge-pill"
        >
            Daily
        </span>

        <span id="challenge-date">
            ${getFormattedDate()}
        </span>

        <span id="challenge-difficulty">
            Schwierigkeit wird berechnet
        </span>

        <span>
            Maximal ${MAX_MOVES} Spielzüge
        </span>
    `;

    challengeCard.insertAdjacentElement(
        "afterend",
        challengeMeta
    );

    const startButton = (
        document.getElementById(
            "start-game-button"
        )
    );

    startButton.textContent = (
        "Challenge starten"
    );

    const actionRow = (
        document.createElement(
            "div"
        )
    );

    actionRow.className = (
        "challenge-actions"
    );

    const randomButton = (
        document.createElement(
            "button"
        )
    );

    randomButton.id = (
        "random-challenge-button"
    );

    randomButton.type = "button";

    randomButton.className = (
        "secondary-button"
    );

    randomButton.textContent = (
        "Andere Zufallsreise"
    );

    startButton.parentNode.insertBefore(
        actionRow,
        startButton
    );

    actionRow.append(
        randomButton,
        startButton
    );

    challengeDom.setupPanel = (
        setupPanel
    );

    challengeDom.startName = (
        document.getElementById(
            "challenge-start-name"
        )
    );

    challengeDom.targetName = (
        document.getElementById(
            "challenge-target-name"
        )
    );

    challengeDom.mode = (
        document.getElementById(
            "challenge-mode"
        )
    );

    challengeDom.date = (
        document.getElementById(
            "challenge-date"
        )
    );

    challengeDom.difficulty = (
        document.getElementById(
            "challenge-difficulty"
        )
    );

    challengeDom.randomButton = (
        randomButton
    );

    challengeDom.startButton = (
        startButton
    );

    challengeDom.setupMessage = (
        document.getElementById(
            "setup-message"
        )
    );
}


/* -------------------------------------------------------------------------- */
/* Challenge anwenden                                                         */
/* -------------------------------------------------------------------------- */


function applyChallenge(
    challenge,
    mode
) {
    activeChallenge = {
        ...challenge,
        mode,
    };

    const startInput = (
        document.getElementById(
            "start-input"
        )
    );

    const startStationIdInput = (
        document.getElementById(
            "start-station-id"
        )
    );

    const targetInput = (
        document.getElementById(
            "target-input"
        )
    );

    const targetStationIdInput = (
        document.getElementById(
            "target-station-id"
        )
    );

    const startName = getStationName(
        challenge.startStationId
    );

    const targetName = getStationName(
        challenge.targetStationId
    );

    startInput.value = startName;

    startInput.dataset.selected = (
        "true"
    );

    startInput.classList.add(
        "station-selected"
    );

    startStationIdInput.value = (
        challenge.startStationId
    );

    targetInput.value = targetName;

    targetInput.dataset.selected = (
        "true"
    );

    targetInput.classList.add(
        "station-selected"
    );

    targetStationIdInput.value = (
        challenge.targetStationId
    );

    challengeDom.startName.textContent = (
        startName
    );

    challengeDom.targetName.textContent = (
        targetName
    );

   

    const networkName = (
    window
        .SSBDLE_ACTIVE_TRAVEL_MODE
        ?.name
    ?? "Travel Mode"
);

    challengeDom.mode.textContent = (
    mode === "daily"
        ? `${networkName} · Daily`
        : `${networkName} · Zufall`
    );

    challengeDom.date.textContent = (
        mode === "daily"
            ? getFormattedDate()
            : "Neu zufällig erzeugt"
    );

    challengeDom.difficulty.textContent = (
        `Schwierigkeit: `
        + challenge.difficulty.label
    );

    challengeDom.difficulty.dataset.level = (
        challenge.difficulty.key
    );

    challengeDom.setupMessage.textContent = (
        "Challenge ist bereit. "
        + "Die optimale Route wird erst nach deiner Reise sichtbar."
    );

    challengeDom.setupMessage.classList.remove(
        "error"
    );

    challengeDom.setupMessage.classList.add(
        "success"
    );

    updateStartButtonState();

    challengeDom.startButton.disabled = (
        false
    );
}


async function generateDailyChallenge() {
    challengeDom.startButton.disabled = (
        true
    );

    challengeDom.randomButton.disabled = (
        true
    );

    challengeDom.setupMessage.textContent = (
        "Die heutige Challenge wird ausgewählt …"
    );

    try { 

        const dateKey = getLocalDateKey();

        const modeId = (
        window
        .SSBDLE_ACTIVE_TRAVEL_MODE
        ?.id
        ?? "stuttgart-rail"
        );

        const randomFunction = (
        createSeededRandom(
        `ssbdle-daily-`
        + `${modeId}-`
        + `${dateKey}`
    ));


        const challenge = (
            await findPlayableChallenge(
                randomFunction
            )
        );

        applyChallenge(
            challenge,
            "daily"
        );
    } catch (error) {
        console.error(error);

        challengeDom.setupMessage.textContent = (
            error.message
        );

        challengeDom.setupMessage.classList.add(
            "error"
        );
    } finally {
        challengeDom.randomButton.disabled = (
            false
        );
    }
}


async function generateRandomChallenge() {
    challengeDom.startButton.disabled = (
        true
    );

    challengeDom.randomButton.disabled = (
        true
    );

    challengeDom.randomButton.textContent = (
        "Wird ausgewählt …"
    );

    challengeDom.setupMessage.textContent = (
        "Eine neue Zufallsreise wird gesucht …"
    );

    try {
        const challenge = (
            await findPlayableChallenge(
                Math.random
            )
        );

        applyChallenge(
            challenge,
            "random"
        );
    } catch (error) {
        console.error(error);

        challengeDom.setupMessage.textContent = (
            error.message
        );

        challengeDom.setupMessage.classList.add(
            "error"
        );
    } finally {
        challengeDom.randomButton.disabled = (
            false
        );

        challengeDom.randomButton.textContent = (
            "Andere Zufallsreise"
        );
    }
}


/* -------------------------------------------------------------------------- */
/* Reset                                                                      */
/* -------------------------------------------------------------------------- */


function restoreActiveChallenge() {
    if (!activeChallenge) {
        return;
    }

    window.setTimeout(
        () => {
            if (
                !challengeDom.setupPanel
                    .classList
                    .contains("hidden")
            ) {
                applyChallenge(
                    activeChallenge,
                    activeChallenge.mode
                );
            }
        },
        0
    );
}


function bindChallengeEvents() {
    challengeDom.randomButton.addEventListener(
        "click",
        generateRandomChallenge
    );

    document
        .getElementById(
            "new-game-button"
        )
        .addEventListener(
            "click",
            restoreActiveChallenge
        );

    document
        .getElementById(
            "cancel-game-button"
        )
        .addEventListener(
            "click",
            restoreActiveChallenge
        );
}


/* -------------------------------------------------------------------------- */
/* Initialisierung                                                            */
/* -------------------------------------------------------------------------- */


async function waitForTravelData() {
    const maximumChecks = 600;

    for (
        let check = 0;
        check < maximumChecks;
        check += 1
    ) {
        const dataReady = (
            typeof travelData
            !== "undefined"
            && travelData.stationList
                .length > 0
        );

        const routerReady = (
            typeof findBestRoute
            === "function"
        );

        if (
            dataReady
            && routerReady
        ) {
            return;
        }

        await challengeDelay(100);
    }

    throw new Error(
        "Die Travel-Daten wurden nicht rechtzeitig geladen."
    );
}


async function initializeChallengeMode() {
    try {
        await waitForTravelData();

        createChallengeInterface();

        bindChallengeEvents();

        await generateDailyChallenge();
    } catch (error) {
        console.error(
            "Challenge-Modus konnte nicht gestartet werden:",
            error
        );
    }
}


document.addEventListener(
    "DOMContentLoaded",
    initializeChallengeMode
);
"use strict";


const TRAVEL_PROGRESS_RATINGS = {
    green: {
        symbol: "🟩",
        label: "Optimal",
    },

    yellow: {
        symbol: "🟨",
        label: "Fast optimal",
    },

    orange: {
        symbol: "🟧",
        label: "kleiner Umweg",
    },

    red: {
        symbol: "🟥",
        label: "Großer Umweg",
    },

    gray: {
        symbol: "⬜",
        label: "Ungültig",
    },
};


const travelProgressState = {
    history: [],
    optimalRoute: null,
};


const travelProgressDom = {};


/* -------------------------------------------------------------------------- */
/* Oberfläche erzeugen                                                       */
/* -------------------------------------------------------------------------- */


function createTravelProgressInterface() {
    const journeySummary = (
        document.querySelector(
            ".journey-summary"
        )
    );

    const finishedPanel = (
        document.getElementById(
            "finished-panel"
        )
    );

    const newGameButton = (
        document.getElementById(
            "new-game-button"
        )
    );

    if (
        !journeySummary
        || !finishedPanel
        || !newGameButton
    ) {
        throw new Error(
            "Die Travel-Progress-Oberfläche konnte nicht eingebaut werden."
        );
    }


    const historyPanel = (
        document.createElement(
            "section"
        )
    );

    historyPanel.id = (
        "journey-history-panel"
    );

    historyPanel.className = (
        "panel journey-history-panel hidden"
    );

    historyPanel.innerHTML = `
        <div class="journey-history-heading">
            <div>
                <p class="step-label">
                    Deine Reise
                </p>

                <h2>
                    Bisheriger Reiseverlauf
                </h2>
            </div>

            <div
                id="journey-history-total"
                class="journey-history-total"
            >
                0 Min.
            </div>
        </div>

        <ol
            id="journey-history-list"
            class="journey-history-list"
        ></ol>
    `;

    journeySummary.insertAdjacentElement(
        "afterend",
        historyPanel
    );


    const solutionPanel = (
        document.createElement(
            "section"
        )
    );

    solutionPanel.id = (
        "optimal-solution-panel"
    );

    solutionPanel.className = (
        "optimal-solution-panel hidden"
    );

    solutionPanel.innerHTML = `
        <div class="optimal-solution-heading">
            <div>
                <p class="step-label">
                    Auflösung
                </p>

                <h3>
                    Eine optimale Route
                </h3>
            </div>

            <div
                id="optimal-route-summary"
                class="optimal-route-summary"
            ></div>
        </div>

        <ol
            id="optimal-route-list"
            class="optimal-route-list"
        ></ol>

        <p class="optimal-route-note">
            Grundlage sind die exportierten GTFS-Fahrzeiten,
            Fußwege und die im Spiel verwendeten Umstiegsannahmen.
        </p>
    `;

    finishedPanel.insertBefore(
        solutionPanel,
        newGameButton
    );


    travelProgressDom.historyPanel = (
        historyPanel
    );

    travelProgressDom.historyList = (
        document.getElementById(
            "journey-history-list"
        )
    );

    travelProgressDom.historyTotal = (
        document.getElementById(
            "journey-history-total"
        )
    );

    travelProgressDom.solutionPanel = (
        solutionPanel
    );

    travelProgressDom.solutionList = (
        document.getElementById(
            "optimal-route-list"
        )
    );

    travelProgressDom.solutionSummary = (
        document.getElementById(
            "optimal-route-summary"
        )
    );

    travelProgressDom.finishedPanel = (
        finishedPanel
    );
}


/* -------------------------------------------------------------------------- */
/* Optimale Route mit tatsächlichem Pfad berechnen                            */
/* -------------------------------------------------------------------------- */


function findOptimalRouteWithPath(
    startStationId,
    targetStationId,
    initialService
) {
    const startStateKey = makeStateKey(
        startStationId,
        initialService
    );

    const startCost = [
        0,
        0,
        0,
        0,
    ];

    const queue = (
        new MinPriorityQueue()
    );

    const bestCosts = new Map([
        [
            startStateKey,
            startCost,
        ],
    ]);

    const predecessors = (
        new Map()
    );

    let insertionOrder = 0;

    queue.push({
        stationId: startStationId,
        serviceKey: initialService,
        stateKey: startStateKey,
        cost: startCost,
        order: insertionOrder,
    });


    while (queue.size > 0) {
        const currentItem = (
            queue.pop()
        );

        if (!currentItem) {
            break;
        }

        const knownCost = (
            bestCosts.get(
                currentItem.stateKey
            )
        );

        if (
            !knownCost
            || compareCosts(
                currentItem.cost,
                knownCost
            ) !== 0
        ) {
            continue;
        }


        if (
            currentItem.stationId
            === targetStationId
        ) {
            const steps = [];

            let currentStateKey = (
                currentItem.stateKey
            );

            while (
                currentStateKey
                !== startStateKey
            ) {
                const predecessor = (
                    predecessors.get(
                        currentStateKey
                    )
                );

                if (!predecessor) {
                    break;
                }

                steps.push(
                    predecessor
                );

                currentStateKey = (
                    predecessor
                        .previousStateKey
                );
            }

            steps.reverse();

            return {
                generalizedTimeSeconds: (
                    currentItem.cost[0]
                ),

                transfers: (
                    currentItem.cost[1]
                ),

                actualTimeSeconds: (
                    currentItem.cost[2]
                ),

                rideStops: (
                    currentItem.cost[3]
                ),

                steps,
            };
        }


        const outgoingEdges = (
            travelData.adjacency[
                currentItem.stationId
            ]
            ?? []
        );


        for (
            const edge of outgoingEdges
        ) {
            const nextStationId = (
                normalizeText(
                    edge.to
                )
            );

            if (!nextStationId) {
                continue;
            }


            const edgeType = (
                normalizeText(
                    edge.type
                )
                || "ride"
            );

            let nextService = "";
            let edgeTimeSeconds = 0;

            let transferIncrement = 0;
            let transferPenaltySeconds = 0;
            let sameStationTransferSeconds = 0;
            let rideStopIncrement = 0;


            if (
                edgeType === "transfer"
            ) {
                nextService = (
                    WALK_SERVICE
                );

                edgeTimeSeconds = (
                    parseSeconds(
                        edge.time,
                        DEFAULT_TRANSFER_TIME_SECONDS
                    )
                );

                if (
                    ![
                        START_SERVICE,
                        WALK_SERVICE,
                    ].includes(
                        currentItem.serviceKey
                    )
                ) {
                    transferIncrement = 1;

                    transferPenaltySeconds = (
                        TRANSFER_PENALTY_SECONDS
                    );
                }
            } else {
                nextService = (
                    makeRideServiceKey(
                        edge
                    )
                );

                if (!nextService) {
                    continue;
                }

                edgeTimeSeconds = (
                    parseSeconds(
                        edge.time,
                        DEFAULT_RIDE_TIME_SECONDS
                    )
                );

                rideStopIncrement = 1;

                if (
                    ![
                        START_SERVICE,
                        WALK_SERVICE,
                    ].includes(
                        currentItem.serviceKey
                    )
                    && currentItem.serviceKey
                    !== nextService
                ) {
                    transferIncrement = 1;

                    sameStationTransferSeconds = (
                        SAME_STATION_TRANSFER_TIME_SECONDS
                    );

                    transferPenaltySeconds = (
                        TRANSFER_PENALTY_SECONDS
                    );
                }
            }


            const addedActualTimeSeconds = (
                edgeTimeSeconds
                + sameStationTransferSeconds
            );

            const addedGeneralizedTimeSeconds = (
                addedActualTimeSeconds
                + transferPenaltySeconds
            );

            const newCost = [
                currentItem.cost[0]
                + addedGeneralizedTimeSeconds,

                currentItem.cost[1]
                + transferIncrement,

                currentItem.cost[2]
                + addedActualTimeSeconds,

                currentItem.cost[3]
                + rideStopIncrement,
            ];

            const nextStateKey = (
                makeStateKey(
                    nextStationId,
                    nextService
                )
            );

            const oldCost = (
                bestCosts.get(
                    nextStateKey
                )
            );

            if (
                oldCost
                && compareCosts(
                    oldCost,
                    newCost
                ) <= 0
            ) {
                continue;
            }


            bestCosts.set(
                nextStateKey,
                newCost
            );

            predecessors.set(
                nextStateKey,
                {
                    previousStateKey: (
                        currentItem.stateKey
                    ),

                    fromStationId: (
                        currentItem.stationId
                    ),

                    toStationId: (
                        nextStationId
                    ),

                    previousService: (
                        currentItem.serviceKey
                    ),

                    nextService,

                    edgeType,

                    edgeTimeSeconds,

                    sameStationTransferSeconds,

                    transferIncrement,

                    edge: {
                        ...edge,
                    },
                }
            );

            insertionOrder += 1;

            queue.push({
                stationId: (
                    nextStationId
                ),

                serviceKey: (
                    nextService
                ),

                stateKey: (
                    nextStateKey
                ),

                cost: (
                    newCost
                ),

                order: (
                    insertionOrder
                ),
            });
        }
    }

    return null;
}


/* -------------------------------------------------------------------------- */
/* Rohpfad zu verständlichen Fahrtabschnitten zusammenfassen                  */
/* -------------------------------------------------------------------------- */


function buildOptimalRouteLegs(
    route
) {
    const legs = [];

    if (
        !route
        || !Array.isArray(
            route.steps
        )
    ) {
        return legs;
    }


    for (
        const step of route.steps
    ) {
        if (
            step.sameStationTransferSeconds
            > 0
        ) {
            legs.push({
                type: "transfer",

                fromStationId: (
                    step.fromStationId
                ),

                toStationId: (
                    step.fromStationId
                ),

                timeSeconds: (
                    step
                        .sameStationTransferSeconds
                ),

                label: "Umstieg",
            });
        }


        if (
            step.edgeType
            === "transfer"
        ) {
            legs.push({
                type: "walk",

                fromStationId: (
                    step.fromStationId
                ),

                toStationId: (
                    step.toStationId
                ),

                timeSeconds: (
                    step.edgeTimeSeconds
                ),

                label: "Fußweg",
            });

            continue;
        }


        const lineName = (
            normalizeText(
                step.edge.line
            )
            || normalizeText(
                step.edge.routeId
            )
            || "Bahn"
        );

        const previousLeg = (
            legs.length > 0
                ? legs[
                    legs.length - 1
                ]
                : null
        );

        const canExtendPreviousLeg = (
            previousLeg
            && previousLeg.type
            === "ride"
            && previousLeg.serviceKey
            === step.nextService
            && previousLeg.toStationId
            === step.fromStationId
        );


        if (
            canExtendPreviousLeg
        ) {
            previousLeg.toStationId = (
                step.toStationId
            );

            previousLeg.timeSeconds += (
                step.edgeTimeSeconds
            );

            previousLeg.stops += 1;

            continue;
        }


        legs.push({
            type: "ride",

            serviceKey: (
                step.nextService
            ),

            line: lineName,

            fromStationId: (
                step.fromStationId
            ),

            toStationId: (
                step.toStationId
            ),

            timeSeconds: (
                step.edgeTimeSeconds
            ),

            stops: 1,
        });
    }

    return legs;
}


/* -------------------------------------------------------------------------- */
/* Reiseverlauf                                                               */
/* -------------------------------------------------------------------------- */


function captureCurrentMove() {
    const evaluation = (
        gameState.pendingEvaluation
    );

    const option = (
        gameState.selectedOption
    );

    const destination = (
        gameState.selectedDestination
    );

    if (
        !evaluation
        || !option
        || !destination
    ) {
        return;
    }


    const service = (
        option.service
    );

    const lineName = (
        normalizeText(
            service.line
        )
        || normalizeText(
            service.routeId
        )
        || "Bahn"
    );

    const headsign = (
        service.headsigns
            ?.slice(0, 2)
            .join(", ")
        || ""
    );

    travelProgressState.history.push({
        moveNumber: (
            gameState.moveNumber + 1
        ),

        fromStationId: (
            gameState.currentStationId
        ),

        toStationId: (
            evaluation.nextStationId
        ),

        line: lineName,

        headsign,

        rating: (
            evaluation
                .classification
                .rating
        ),

        extraSeconds: (
            evaluation
                .classification
                .extraSeconds
        ),

        actualTimeSeconds: (
            evaluation
                .moveActualTimeSeconds
        ),

        accessTransferTimeSeconds: (
            evaluation
                .accessTransferTimeSeconds
        ),

        sameStationTransferTimeSeconds: (
            evaluation
                .sameStationTransferTimeSeconds
        ),
    });


    window.setTimeout(
        () => {
            renderJourneyHistory();
            renderOptimalSolutionIfFinished();
        },
        0
    );
}


function renderJourneyHistory() {
    const history = (
        travelProgressState.history
    );

    travelProgressDom
        .historyList
        .replaceChildren();


    if (
        history.length === 0
    ) {
        hide(
            travelProgressDom
                .historyPanel
        );

        travelProgressDom
            .historyTotal
            .textContent = "0 Min.";

        return;
    }


    let cumulativeSeconds = 0;


    for (
        const move of history
    ) {
        cumulativeSeconds += (
            move.actualTimeSeconds
        );

        const rating = (
            TRAVEL_PROGRESS_RATINGS[
                move.rating
            ]
            ?? TRAVEL_PROGRESS_RATINGS.gray
        );

        const listItem = (
            document.createElement(
                "li"
            )
        );

        listItem.className = (
            `journey-history-item `
            + `rating-${move.rating}`
        );


        const numberElement = (
            document.createElement(
                "span"
            )
        );

        numberElement.className = (
            "journey-history-number"
        );

        numberElement.textContent = (
            String(
                move.moveNumber
            )
        );


        const contentElement = (
            document.createElement(
                "div"
            )
        );

        contentElement.className = (
            "journey-history-content"
        );


        const titleRow = (
            document.createElement(
                "div"
            )
        );

        titleRow.className = (
            "journey-history-title"
        );


        const badge = (
            document.createElement(
                "span"
            )
        );

        badge.className = (
            "line-badge"
        );

        badge.textContent = (
            move.line
        );


        const ratingElement = (
            document.createElement(
                "span"
            )
        );

        ratingElement.className = (
            "journey-history-rating"
        );

        ratingElement.textContent = (
            `${rating.symbol} `
            + rating.label
        );


        titleRow.append(
            badge,
            ratingElement
        );


        const routeElement = (
            document.createElement(
                "strong"
            )
        );

        routeElement.className = (
            "journey-history-route"
        );

        routeElement.textContent = (
            `${getStationName(
                move.fromStationId
            )} → `
            + getStationName(
                move.toStationId
            )
        );


        const details = [];

        if (move.headsign) {
            details.push(
                `Richtung ${move.headsign}`
            );
        }

        details.push(
            formatMinutes(
                move.actualTimeSeconds
            )
        );

        if (
            move.extraSeconds === null
        ) {
            details.push(
                "Abweichung nicht berechenbar"
            );
        } else if (
            move.extraSeconds <= 0
        ) {
            details.push(
                "optimal"
            );
        } else {
            details.push(
                `+${formatMinutes(
                    move.extraSeconds
                )}`
            );
        }


        const detailElement = (
            document.createElement(
                "span"
            )
        );

        detailElement.className = (
            "journey-history-details"
        );

        detailElement.textContent = (
            details.join(" · ")
        );


        contentElement.append(
            titleRow,
            routeElement,
            detailElement
        );

        listItem.append(
            numberElement,
            contentElement
        );

        travelProgressDom
            .historyList
            .append(
                listItem
            );
    }


    travelProgressDom
        .historyTotal
        .textContent = (
            formatMinutes(
                cumulativeSeconds
            )
        );

    show(
        travelProgressDom
            .historyPanel
    );
}


/* -------------------------------------------------------------------------- */
/* Optimale Lösung anzeigen                                                   */
/* -------------------------------------------------------------------------- */


function createOptimalRouteLegElement(
    leg
) {
    const listItem = (
        document.createElement(
            "li"
        )
    );

    listItem.className = (
        `optimal-route-leg `
        + `optimal-route-${leg.type}`
    );


    const icon = (
        document.createElement(
            "span"
        )
    );

    icon.className = (
        "optimal-route-icon"
    );


    const content = (
        document.createElement(
            "div"
        )
    );

    content.className = (
        "optimal-route-content"
    );


    const title = (
        document.createElement(
            "strong"
        )
    );


    const detail = (
        document.createElement(
            "span"
        )
    );


    if (
        leg.type === "ride"
    ) {
        icon.textContent = (
            leg.line
        );

        icon.classList.add(
            "optimal-route-line"
        );

        title.textContent = (
            `${getStationName(
                leg.fromStationId
            )} → `
            + getStationName(
                leg.toStationId
            )
        );

        detail.textContent = (
            `${leg.stops} `
            + (
                leg.stops === 1
                    ? "Halt"
                    : "Halte"
            )
            + " · "
            + formatMinutes(
                leg.timeSeconds
            )
        );
    } else if (
        leg.type === "walk"
    ) {
        icon.textContent = "🚶";

        title.textContent = (
            `${getStationName(
                leg.fromStationId
            )} → `
            + getStationName(
                leg.toStationId
            )
        );

        detail.textContent = (
            `Fußweg · `
            + formatMinutes(
                leg.timeSeconds
            )
        );
    } else {
        icon.textContent = "↔";

        title.textContent = (
            `Umstieg an `
            + getStationName(
                leg.fromStationId
            )
        );

        detail.textContent = (
            formatMinutes(
                leg.timeSeconds
            )
        );
    }


    content.append(
        title,
        detail
    );

    listItem.append(
        icon,
        content
    );

    return listItem;
}


function renderOptimalSolution() {
    const optimalRoute = (
        travelProgressState
            .optimalRoute
    );

    travelProgressDom
        .solutionList
        .replaceChildren();


    if (!optimalRoute) {
        travelProgressDom
            .solutionSummary
            .textContent = (
                "Keine Lösung verfügbar"
            );

        show(
            travelProgressDom
                .solutionPanel
        );

        return;
    }


    const routeLegs = (
        buildOptimalRouteLegs(
            optimalRoute
        )
    );


    for (
        const leg of routeLegs
    ) {
        travelProgressDom
            .solutionList
            .append(
                createOptimalRouteLegElement(
                    leg
                )
            );
    }


    travelProgressDom
        .solutionSummary
        .textContent = (
            formatMinutes(
                optimalRoute
                    .actualTimeSeconds
            )
            + " · "
            + optimalRoute.transfers
            + (
                optimalRoute.transfers
                === 1
                    ? " Umstieg"
                    : " Umstiege"
            )
        );


    show(
        travelProgressDom
            .solutionPanel
    );
}


function renderOptimalSolutionIfFinished() {
    const gameFinished = (
        !travelProgressDom
            .finishedPanel
            .classList
            .contains("hidden")
    );

    if (gameFinished) {
        renderOptimalSolution();
    }
}


/* -------------------------------------------------------------------------- */
/* Neues Spiel vorbereiten                                                    */
/* -------------------------------------------------------------------------- */


function prepareTravelProgressForGame() {
    travelProgressState.history = [];
    travelProgressState.optimalRoute = null;

    renderJourneyHistory();

    hide(
        travelProgressDom
            .solutionPanel
    );

    travelProgressDom
        .solutionList
        .replaceChildren();


    window.setTimeout(
        () => {
            if (
                !gameState.active
                || !gameState.startStationId
                || !gameState.targetStationId
            ) {
                return;
            }

            travelProgressState
                .optimalRoute = (
                    findOptimalRouteWithPath(
                        gameState.startStationId,
                        gameState.targetStationId,
                        START_SERVICE
                    )
                );
        },
        0
    );
}


function resetTravelProgressIfGameClosed() {
    window.setTimeout(
        () => {
            if (gameState.active) {
                return;
            }

            travelProgressState.history = [];
            travelProgressState.optimalRoute = null;

            renderJourneyHistory();

            hide(
                travelProgressDom
                    .solutionPanel
            );
        },
        0
    );
}


/* -------------------------------------------------------------------------- */
/* Events                                                                     */
/* -------------------------------------------------------------------------- */


function bindTravelProgressEvents() {
    const startButton = (
        document.getElementById(
            "start-game-button"
        )
    );

    const continueButton = (
        document.getElementById(
            "continue-button"
        )
    );

    const newGameButton = (
        document.getElementById(
            "new-game-button"
        )
    );

    const cancelButton = (
        document.getElementById(
            "cancel-game-button"
        )
    );


    startButton.addEventListener(
        "click",
        prepareTravelProgressForGame
    );


    /*
     * Capture ist hier wichtig:
     * Der bestehende Travel-Code setzt pendingEvaluation
     * nach dem Klick sofort wieder auf null.
     */
    continueButton.addEventListener(
        "click",
        captureCurrentMove,
        {
            capture: true,
        }
    );


    newGameButton.addEventListener(
        "click",
        resetTravelProgressIfGameClosed
    );


    cancelButton.addEventListener(
        "click",
        resetTravelProgressIfGameClosed
    );
}


/* -------------------------------------------------------------------------- */
/* Initialisierung                                                            */
/* -------------------------------------------------------------------------- */


function initializeTravelProgress() {
    try {
        createTravelProgressInterface();
        bindTravelProgressEvents();
        renderJourneyHistory();
    } catch (error) {
        console.error(
            "Reiseverlauf konnte nicht gestartet werden:",
            error
        );
    }
}


document.addEventListener(
    "DOMContentLoaded",
    initializeTravelProgress
);
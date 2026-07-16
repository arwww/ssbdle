"use strict";



const ACTIVE_TRAVEL_MODE = (
    window.SSBDLE_ACTIVE_TRAVEL_MODE
    ?? {
        id: "stuttgart-rail",
        name: "Stuttgart S- & U-Bahn",
        dataPath:
            "data/travel/stuttgart-rail",
    }
);


const TRAVEL_DATA_BASE_PATH = (
    ACTIVE_TRAVEL_MODE.dataPath
);


const DATA_PATHS = {
    stations:
        `${TRAVEL_DATA_BASE_PATH}/stations.json`,

    graph:
        `${TRAVEL_DATA_BASE_PATH}/graph.json`,

    moves:
        `${TRAVEL_DATA_BASE_PATH}/moves.json`,
};


const SAME_STATION_TRANSFER_TIME_SECONDS = 180;
const TRANSFER_PENALTY_SECONDS = 300;

const DEFAULT_RIDE_TIME_SECONDS = 120;
const DEFAULT_TRANSFER_TIME_SECONDS = 180;

const MAX_MOVES = 10;

const START_SERVICE = "__start__";
const WALK_SERVICE = "__walk__";


const RATING_INFO = {
    green: {
        symbol: "🟩",
        label: "Optimale Verbindung",
    },

    yellow: {
        symbol: "🟨",
        label: "Fast optimal",
    },

    orange: {
        symbol: "🟧",
        label: "Kleiner Umweg",
    },

    red: {
        symbol: "🟥",
        label: "Großer Umweg",
    },

    gray: {
        symbol: "⬜",
        label: "Nicht möglich",
    },
};


const travelData = {
    stationList: [],
    stationById: new Map(),
    adjacency: {},
    stationMoves: {},
};


const gameState = {
    active: false,

    startStationId: "",
    targetStationId: "",

    currentStationId: "",
    currentService: START_SERVICE,

    selectedOption: null,
    selectedDestination: null,
    pendingEvaluation: null,

    currentOptions: [],

    moveNumber: 0,
    totalActualSeconds: 0,
    totalTransfers: 0,

    initialBest: null,
};


const dom = {};

let startAutocomplete = null;
let targetAutocomplete = null;
let destinationAutocomplete = null;


/* -------------------------------------------------------------------------- */
/* Priority Queue                                                             */
/* -------------------------------------------------------------------------- */


class MinPriorityQueue {
    constructor() {
        this.items = [];
    }


    get size() {
        return this.items.length;
    }


    push(item) {
        this.items.push(item);
        this.bubbleUp(
            this.items.length - 1
        );
    }


    pop() {
        if (this.items.length === 0) {
            return null;
        }

        const firstItem = this.items[0];
        const lastItem = this.items.pop();

        if (
            this.items.length > 0
            && lastItem
        ) {
            this.items[0] = lastItem;
            this.bubbleDown(0);
        }

        return firstItem;
    }


    bubbleUp(index) {
        let currentIndex = index;

        while (currentIndex > 0) {
            const parentIndex = Math.floor(
                (currentIndex - 1) / 2
            );

            if (
                !this.isLess(
                    this.items[currentIndex],
                    this.items[parentIndex]
                )
            ) {
                break;
            }

            [
                this.items[currentIndex],
                this.items[parentIndex],
            ] = [
                this.items[parentIndex],
                this.items[currentIndex],
            ];

            currentIndex = parentIndex;
        }
    }


    bubbleDown(index) {
        let currentIndex = index;

        while (true) {
            const leftIndex = (
                currentIndex * 2 + 1
            );

            const rightIndex = (
                currentIndex * 2 + 2
            );

            let smallestIndex = (
                currentIndex
            );

            if (
                leftIndex
                < this.items.length
                && this.isLess(
                    this.items[leftIndex],
                    this.items[smallestIndex]
                )
            ) {
                smallestIndex = leftIndex;
            }

            if (
                rightIndex
                < this.items.length
                && this.isLess(
                    this.items[rightIndex],
                    this.items[smallestIndex]
                )
            ) {
                smallestIndex = rightIndex;
            }

            if (
                smallestIndex
                === currentIndex
            ) {
                break;
            }

            [
                this.items[currentIndex],
                this.items[smallestIndex],
            ] = [
                this.items[smallestIndex],
                this.items[currentIndex],
            ];

            currentIndex = smallestIndex;
        }
    }


    isLess(firstItem, secondItem) {
        const costComparison = compareCosts(
            firstItem.cost,
            secondItem.cost
        );

        if (costComparison !== 0) {
            return costComparison < 0;
        }

        return (
            firstItem.order
            < secondItem.order
        );
    }
}


/* -------------------------------------------------------------------------- */
/* Allgemeine Hilfsfunktionen                                                 */
/* -------------------------------------------------------------------------- */


function normalizeText(value) {
    return String(
        value ?? ""
    ).trim();
}


function normalizeSearchText(value) {
    return normalizeText(value)
        .toLocaleLowerCase("de-DE")
        .normalize("NFD")
        .replace(
            /[\u0300-\u036f]/g,
            ""
        )
        .replaceAll("ß", "ss");
}


function parseSeconds(
    value,
    fallbackValue
) {
    const numericValue = Number(value);

    if (
        !Number.isFinite(numericValue)
        || numericValue < 0
    ) {
        return fallbackValue;
    }

    return Math.round(
        numericValue
    );
}


function formatMinutes(seconds) {
    const safeSeconds = Math.max(
        0,
        parseSeconds(
            seconds,
            0
        )
    );

    const minutes = (
        safeSeconds / 60
    );

    if (
        safeSeconds % 60 === 0
    ) {
        return `${minutes.toFixed(0)} Min.`;
    }

    return `${minutes.toFixed(1)} Min.`;
}


function compareCosts(
    firstCost,
    secondCost
) {
    const maximumLength = Math.max(
        firstCost.length,
        secondCost.length
    );

    for (
        let index = 0;
        index < maximumLength;
        index += 1
    ) {
        const firstValue = (
            firstCost[index] ?? 0
        );

        const secondValue = (
            secondCost[index] ?? 0
        );

        if (firstValue < secondValue) {
            return -1;
        }

        if (firstValue > secondValue) {
            return 1;
        }
    }

    return 0;
}


function makeStateKey(
    stationId,
    serviceKey
) {
    return (
        `${stationId}\u0001${serviceKey}`
    );
}


function makeRideServiceKey(edge) {
    const routeId = normalizeText(
        edge.routeId
    );

    const directionId = normalizeText(
        edge.directionId
    );

    if (!routeId) {
        return "";
    }

    return (
        `${routeId}::${directionId}`
    );
}


function getStationName(stationId) {
    return (
        travelData.stationById
            .get(stationId)
            ?.name
        ?? stationId
    );
}


function naturalCompare(
    firstValue,
    secondValue
) {
    return normalizeText(
        firstValue
    ).localeCompare(
        normalizeText(
            secondValue
        ),
        "de",
        {
            numeric: true,
            sensitivity: "base",
        }
    );
}


function show(element) {
    element.classList.remove(
        "hidden"
    );
}


function hide(element) {
    element.classList.add(
        "hidden"
    );
}


function scrollToElement(element) {
    element.scrollIntoView({
        behavior: "smooth",
        block: "start",
    });
}


/* -------------------------------------------------------------------------- */
/* DOM                                                                        */
/* -------------------------------------------------------------------------- */


function cacheDomElements() {
    dom.loadingScreen = document.getElementById(
        "loading-screen"
    );

    dom.loadingStatus = document.getElementById(
        "loading-status"
    );

    dom.errorPanel = document.getElementById(
        "error-panel"
    );

    dom.errorMessage = document.getElementById(
        "error-message"
    );

    dom.travelApp = document.getElementById(
        "travel-app"
    );

    dom.setupPanel = document.getElementById(
        "setup-panel"
    );

    dom.startInput = document.getElementById(
        "start-input"
    );

    dom.startStationId = document.getElementById(
        "start-station-id"
    );

    dom.startSuggestions = document.getElementById(
        "start-suggestions"
    );

    dom.targetInput = document.getElementById(
        "target-input"
    );

    dom.targetStationId = document.getElementById(
        "target-station-id"
    );

    dom.targetSuggestions = document.getElementById(
        "target-suggestions"
    );

    dom.swapStationsButton = document.getElementById(
        "swap-stations-button"
    );

    dom.setupMessage = document.getElementById(
        "setup-message"
    );

    dom.startGameButton = document.getElementById(
        "start-game-button"
    );

    dom.gamePanel = document.getElementById(
        "game-panel"
    );

    dom.currentStationName = document.getElementById(
        "current-station-name"
    );

    dom.targetStationName = document.getElementById(
        "target-station-name"
    );

    dom.moveCounter = document.getElementById(
        "move-counter"
    );

    dom.serviceStep = document.getElementById(
        "service-step"
    );

    dom.serviceOptions = document.getElementById(
        "service-options"
    );

    dom.destinationStep = document.getElementById(
        "destination-step"
    );

    dom.selectedServiceSummary = document.getElementById(
        "selected-service-summary"
    );

    dom.destinationInput = document.getElementById(
        "destination-input"
    );

    dom.destinationStationId = document.getElementById(
        "destination-station-id"
    );

    dom.destinationSuggestions = document.getElementById(
        "destination-suggestions"
    );

    dom.backToServicesButton = document.getElementById(
        "back-to-services-button"
    );

    dom.confirmMoveButton = document.getElementById(
        "confirm-move-button"
    );

    dom.feedbackPanel = document.getElementById(
        "feedback-panel"
    );

    dom.feedbackSymbol = document.getElementById(
        "feedback-symbol"
    );

    dom.feedbackTitle = document.getElementById(
        "feedback-title"
    );

    dom.feedbackDescription = document.getElementById(
        "feedback-description"
    );

    dom.feedbackMove = document.getElementById(
        "feedback-move"
    );

    dom.feedbackMoveTime = document.getElementById(
        "feedback-move-time"
    );

    dom.feedbackDifference = document.getElementById(
        "feedback-difference"
    );

    dom.continueButton = document.getElementById(
        "continue-button"
    );

    dom.finishedPanel = document.getElementById(
        "finished-panel"
    );

    dom.finishSymbol = dom.finishedPanel.querySelector(
        ".finish-symbol"
    );

    dom.finishedTitle = document.getElementById(
        "finished-title"
    );

    dom.finishedDescription = document.getElementById(
        "finished-description"
    );

    dom.finishedMoves = document.getElementById(
        "finished-moves"
    );

    dom.finishedTime = document.getElementById(
        "finished-time"
    );

    dom.finishedDifference = document.getElementById(
        "finished-difference"
    );

    dom.newGameButton = document.getElementById(
        "new-game-button"
    );

    dom.cancelGameButton = document.getElementById(
        "cancel-game-button"
    );
}


/* -------------------------------------------------------------------------- */
/* Daten laden                                                                */
/* -------------------------------------------------------------------------- */


async function fetchJson(path) {
    const response = await fetch(
        path,
        {
            cache: "no-store",
        }
    );

    if (!response.ok) {
        throw new Error(
            `${path}: HTTP ${response.status}`
        );
    }

    return response.json();
}


async function loadTravelData() {
    

    dom.loadingStatus.textContent = (
    `${ACTIVE_TRAVEL_MODE.name} `
    + "wird geladen …"
    );

    const [
        stationPayload,
        graphPayload,
        movePayload,
    ] = await Promise.all([
        fetchJson(
            DATA_PATHS.stations
        ),

        fetchJson(
            DATA_PATHS.graph
        ),

        fetchJson(
            DATA_PATHS.moves
        ),
    ]);

    if (
        !Array.isArray(
            stationPayload.stations
        )
    ) {
        throw new Error(
            "stations.json enthält keine gültige Stationsliste."
        );
    }

    if (
        !graphPayload.adjacency
        || typeof graphPayload.adjacency
        !== "object"
    ) {
        throw new Error(
            "graph.json enthält keinen gültigen Graphen."
        );
    }

    if (
        !movePayload.stationMoves
        || typeof movePayload.stationMoves
        !== "object"
    ) {
        throw new Error(
            "moves.json enthält keinen gültigen Move-Index."
        );
    }

    travelData.stationList = (
        stationPayload.stations
    );

    travelData.stationById = new Map(
        travelData.stationList.map(
            station => [
                station.id,
                station,
            ]
        )
    );

    travelData.adjacency = (
        graphPayload.adjacency
    );

    travelData.stationMoves = (
        movePayload.stationMoves
    );

    dom.loadingStatus.textContent = (
        `${travelData.stationList.length.toLocaleString("de-DE")} `
        + "Stationen wurden geladen."
    );
}


/* -------------------------------------------------------------------------- */
/* Autovervollständigung                                                      */
/* -------------------------------------------------------------------------- */


function getSuggestionScore(
    label,
    query
) {
    const normalizedLabel = (
        normalizeSearchText(label)
    );

    const normalizedQuery = (
        normalizeSearchText(query)
    );

    if (!normalizedQuery) {
        return 5;
    }

    if (
        normalizedLabel
        === normalizedQuery
    ) {
        return 0;
    }

    if (
        normalizedLabel.startsWith(
            normalizedQuery
        )
    ) {
        return 1;
    }

    const words = normalizedLabel.split(
        /[\s/(),.-]+/
    );

    if (
        words.some(
            word => word.startsWith(
                normalizedQuery
            )
        )
    ) {
        return 2;
    }

    if (
        normalizedLabel.includes(
            normalizedQuery
        )
    ) {
        return 3;
    }

    return null;
}


function filterSuggestionItems(
    items,
    query,
    labelGetter,
    maximumResults
) {
    const normalizedQuery = (
        normalizeSearchText(query)
    );

    if (!normalizedQuery) {
        return items.slice(
            0,
            maximumResults
        );
    }

    return items
        .map(
            (
                item,
                originalIndex
            ) => ({
                item,
                originalIndex,
                score: getSuggestionScore(
                    labelGetter(item),
                    query
                ),
            })
        )
        .filter(
            result => (
                result.score !== null
            )
        )
        .sort(
            (
                firstResult,
                secondResult
            ) => (
                firstResult.score
                - secondResult.score
                || naturalCompare(
                    labelGetter(
                        firstResult.item
                    ),
                    labelGetter(
                        secondResult.item
                    )
                )
                || (
                    firstResult.originalIndex
                    - secondResult.originalIndex
                )
            )
        )
        .slice(
            0,
            maximumResults
        )
        .map(
            result => result.item
        );
}


function createAutocomplete({
    input,
    hiddenInput,
    suggestionList,
    getItems,
    getItemId,
    getItemLabel,
    getItemMeta,
    emptyMessage,
    maximumResults = 12,
    onSelection,
    onClear,
}) {
    let visibleItems = [];
    let activeIndex = -1;


    function closeSuggestions() {
        activeIndex = -1;
        visibleItems = [];

        suggestionList.replaceChildren();
        hide(suggestionList);
    }


    function updateActiveItem() {
        const buttons = (
            suggestionList.querySelectorAll(
                ".suggestion-item"
            )
        );

        buttons.forEach(
            (
                button,
                index
            ) => {
                const isActive = (
                    index === activeIndex
                );

                button.classList.toggle(
                    "active",
                    isActive
                );

                button.setAttribute(
                    "aria-selected",
                    String(isActive)
                );
            }
        );

        if (
            activeIndex >= 0
            && buttons[activeIndex]
        ) {
            buttons[activeIndex]
                .scrollIntoView({
                    block: "nearest",
                });
        }
    }


    function selectItem(item) {
        const itemId = normalizeText(
            getItemId(item)
        );

        const itemLabel = normalizeText(
            getItemLabel(item)
        );

        input.value = itemLabel;
        hiddenInput.value = itemId;

        input.dataset.selected = "true";
        input.classList.add(
            "station-selected"
        );

        closeSuggestions();

        if (onSelection) {
            onSelection(item);
        }
    }


    function renderSuggestions() {
        const sourceItems = (
            getItems() ?? []
        );

        visibleItems = (
            filterSuggestionItems(
                sourceItems,
                input.value,
                getItemLabel,
                maximumResults
            )
        );

        activeIndex = -1;
        suggestionList.replaceChildren();

        if (
            visibleItems.length === 0
        ) {
            const emptyItem = (
                document.createElement(
                    "div"
                )
            );

            emptyItem.className = (
                "suggestion-empty"
            );

            emptyItem.textContent = (
                emptyMessage
            );

            suggestionList.append(
                emptyItem
            );

            show(suggestionList);
            return;
        }

        visibleItems.forEach(
            (
                item,
                index
            ) => {
                const button = (
                    document.createElement(
                        "button"
                    )
                );

                button.type = "button";
                button.className = (
                    "suggestion-item"
                );

                button.setAttribute(
                    "role",
                    "option"
                );

                button.setAttribute(
                    "aria-selected",
                    "false"
                );

                button.dataset.index = (
                    String(index)
                );

                const nameElement = (
                    document.createElement(
                        "span"
                    )
                );

                nameElement.className = (
                    "suggestion-name"
                );

                nameElement.textContent = (
                    getItemLabel(item)
                );

                button.append(
                    nameElement
                );

                const metadata = (
                    normalizeText(
                        getItemMeta?.(item)
                    )
                );

                if (metadata) {
                    const metaElement = (
                        document.createElement(
                            "span"
                        )
                    );

                    metaElement.className = (
                        "suggestion-meta"
                    );

                    metaElement.textContent = (
                        metadata
                    );

                    button.append(
                        metaElement
                    );
                }

                button.addEventListener(
                    "click",
                    () => {
                        selectItem(item);
                    }
                );

                suggestionList.append(
                    button
                );
            }
        );

        show(suggestionList);
    }


    function clearSelection({
        keepText = false,
    } = {}) {
        hiddenInput.value = "";

        input.dataset.selected = "false";
        input.classList.remove(
            "station-selected"
        );

        if (!keepText) {
            input.value = "";
        }

        closeSuggestions();

        if (onClear) {
            onClear();
        }
    }


    input.addEventListener(
        "input",
        () => {
            hiddenInput.value = "";

            input.dataset.selected = "false";
            input.classList.remove(
                "station-selected"
            );

            if (onClear) {
                onClear();
            }

            renderSuggestions();
        }
    );


    input.addEventListener(
        "focus",
        () => {
            renderSuggestions();
        }
    );


    input.addEventListener(
        "keydown",
        event => {
            if (
                suggestionList.classList
                    .contains("hidden")
            ) {
                if (
                    event.key
                    === "ArrowDown"
                ) {
                    renderSuggestions();
                }

                return;
            }

            if (
                event.key === "ArrowDown"
            ) {
                event.preventDefault();

                activeIndex = Math.min(
                    activeIndex + 1,
                    visibleItems.length - 1
                );

                updateActiveItem();
                return;
            }

            if (
                event.key === "ArrowUp"
            ) {
                event.preventDefault();

                activeIndex = Math.max(
                    activeIndex - 1,
                    0
                );

                updateActiveItem();
                return;
            }

            if (
                event.key === "Enter"
                && activeIndex >= 0
                && visibleItems[activeIndex]
            ) {
                event.preventDefault();

                selectItem(
                    visibleItems[activeIndex]
                );

                return;
            }

            if (
                event.key === "Escape"
            ) {
                closeSuggestions();
            }
        }
    );


    document.addEventListener(
        "click",
        event => {
            if (
                event.target !== input
                && !suggestionList.contains(
                    event.target
                )
            ) {
                closeSuggestions();
            }
        }
    );


    return {
        close: closeSuggestions,

        clear: clearSelection,

        refresh: renderSuggestions,

        setSelection(item) {
            selectItem(item);
        },
    };
}


/* -------------------------------------------------------------------------- */
/* Setup                                                                      */
/* -------------------------------------------------------------------------- */


function setSetupMessage(
    message,
    type = ""
) {
    dom.setupMessage.textContent = (
        message
    );

    dom.setupMessage.classList.remove(
        "error",
        "success"
    );

    if (type) {
        dom.setupMessage.classList.add(
            type
        );
    }
}


function updateStartButtonState() {
    const startId = normalizeText(
        dom.startStationId.value
    );

    const targetId = normalizeText(
        dom.targetStationId.value
    );

    const bothSelected = (
        Boolean(startId)
        && Boolean(targetId)
    );

    const sameStation = (
        bothSelected
        && startId === targetId
    );

    dom.startGameButton.disabled = (
        !bothSelected
        || sameStation
    );

    if (sameStation) {
        setSetupMessage(
            "Start und Ziel müssen unterschiedlich sein.",
            "error"
        );

        return;
    }

    if (bothSelected) {
        setSetupMessage(
            "Start und Ziel sind ausgewählt.",
            "success"
        );

        return;
    }

    setSetupMessage("");
}


function swapSelectedStations() {
    const startValue = (
        dom.startInput.value
    );

    const startId = (
        dom.startStationId.value
    );

    const startSelected = (
        dom.startInput.dataset.selected
    );

    dom.startInput.value = (
        dom.targetInput.value
    );

    dom.startStationId.value = (
        dom.targetStationId.value
    );

    dom.startInput.dataset.selected = (
        dom.targetInput.dataset.selected
        ?? "false"
    );

    dom.targetInput.value = (
        startValue
    );

    dom.targetStationId.value = (
        startId
    );

    dom.targetInput.dataset.selected = (
        startSelected
        ?? "false"
    );

    dom.startInput.classList.toggle(
        "station-selected",
        Boolean(
            dom.startStationId.value
        )
    );

    dom.targetInput.classList.toggle(
        "station-selected",
        Boolean(
            dom.targetStationId.value
        )
    );

    startAutocomplete.close();
    targetAutocomplete.close();

    updateStartButtonState();
}


/* -------------------------------------------------------------------------- */
/* Gewichteter Dijkstra                                                       */
/* -------------------------------------------------------------------------- */


function findBestRoute(
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

    let insertionOrder = 0;

    queue.push({
        stationId: startStationId,
        serviceKey: initialService,
        stateKey: startStateKey,
        cost: startCost,
        order: insertionOrder,
    });

    const bestCosts = new Map([
        [
            startStateKey,
            startCost,
        ],
    ]);

    while (queue.size > 0) {
        const currentItem = queue.pop();

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
                normalizeText(edge.to)
            );

            if (!nextStationId) {
                continue;
            }

            const edgeType = (
                normalizeText(edge.type)
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
                    makeRideServiceKey(edge)
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

            const addedActualTime = (
                edgeTimeSeconds
                + sameStationTransferSeconds
            );

            const addedGeneralizedTime = (
                addedActualTime
                + transferPenaltySeconds
            );

            const newCost = [
                currentItem.cost[0]
                + addedGeneralizedTime,

                currentItem.cost[1]
                + transferIncrement,

                currentItem.cost[2]
                + addedActualTime,

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

            insertionOrder += 1;

            queue.push({
                stationId: nextStationId,
                serviceKey: nextService,
                stateKey: nextStateKey,
                cost: newCost,
                order: insertionOrder,
            });
        }
    }

    return null;
}


/* -------------------------------------------------------------------------- */
/* Legale Linienoptionen                                                      */
/* -------------------------------------------------------------------------- */


function buildServiceOptions(
    currentStationId
) {
    const options = [];
    const seenOptions = new Set();


    function addServices(
        boardingStationId,
        transferEdge
    ) {
        const services = (
            travelData.stationMoves[
                boardingStationId
            ]
            ?? []
        );

        for (
            const service of services
        ) {
            const serviceKey = (
                normalizeText(
                    service.serviceKey
                )
            );

            if (!serviceKey) {
                continue;
            }

            const deduplicationKey = (
                `${boardingStationId}`
                + `\u0001${serviceKey}`
            );

            if (
                seenOptions.has(
                    deduplicationKey
                )
            ) {
                continue;
            }

            seenOptions.add(
                deduplicationKey
            );

            options.push({
                boardingStationId,
                transferEdge,
                service,
            });
        }
    }


    addServices(
        currentStationId,
        null
    );

    const outgoingEdges = (
        travelData.adjacency[
            currentStationId
        ]
        ?? []
    );

    for (
        const edge of outgoingEdges
    ) {
        if (
            edge.type !== "transfer"
        ) {
            continue;
        }

        const boardingStationId = (
            normalizeText(edge.to)
        );

        if (!boardingStationId) {
            continue;
        }

        addServices(
            boardingStationId,
            edge
        );
    }

    options.sort(
        (
            firstOption,
            secondOption
        ) => {
            const firstLine = (
                firstOption.service.line
                || firstOption.service.routeId
            );

            const secondLine = (
                secondOption.service.line
                || secondOption.service.routeId
            );

            return (
                naturalCompare(
                    firstLine,
                    secondLine
                )
                || naturalCompare(
                    firstOption.service.directionId,
                    secondOption.service.directionId
                )
                || naturalCompare(
                    firstOption.boardingStationId,
                    secondOption.boardingStationId
                )
            );
        }
    );

    return options;
}


/* -------------------------------------------------------------------------- */
/* Spielzug-Bewertung                                                         */
/* -------------------------------------------------------------------------- */


function classifyMove(
    optimalSeconds,
    projectedSeconds
) {
    if (
        projectedSeconds === null
    ) {
        return {
            rating: "red",
            extraSeconds: null,
            extraRatio: null,
        };
    }

    const extraSeconds = Math.max(
        0,
        projectedSeconds
        - optimalSeconds
    );

    const extraRatio = (
        optimalSeconds > 0
            ? (
                extraSeconds
                / optimalSeconds
            )
            : 0
    );

    if (
        extraSeconds <= 60
        || extraRatio <= 0.05
    ) {
        return {
            rating: "green",
            extraSeconds,
            extraRatio,
        };
    }

    if (
        extraSeconds <= 180
        || extraRatio <= 0.12
    ) {
        return {
            rating: "yellow",
            extraSeconds,
            extraRatio,
        };
    }

    if (
        extraSeconds <= 480
        || extraRatio <= 0.30
    ) {
        return {
            rating: "orange",
            extraSeconds,
            extraRatio,
        };
    }

    return {
        rating: "red",
        extraSeconds,
        extraRatio,
    };
}


function evaluateSelectedMove(
    option,
    destination
) {
    const baseline = findBestRoute(
        gameState.currentStationId,
        gameState.targetStationId,
        gameState.currentService
    );

    if (!baseline) {
        throw new Error(
            "Vom aktuellen Standort wurde keine Route zum Ziel gefunden."
        );
    }

    const service = option.service;

    const nextService = (
        normalizeText(
            service.serviceKey
        )
    );

    const nextStationId = (
        normalizeText(
            destination.stationId
        )
    );

    const rideTimeSeconds = (
        parseSeconds(
            destination.time,
            DEFAULT_RIDE_TIME_SECONDS
        )
    );

    let moveActualTimeSeconds = (
        rideTimeSeconds
    );

    let moveGeneralizedTimeSeconds = (
        rideTimeSeconds
    );

    let moveTransfers = 0;

    let accessTransferTimeSeconds = 0;
    let sameStationTransferTimeSeconds = 0;

    if (option.transferEdge) {
        accessTransferTimeSeconds = (
            parseSeconds(
                option.transferEdge.time,
                DEFAULT_TRANSFER_TIME_SECONDS
            )
        );

        moveActualTimeSeconds += (
            accessTransferTimeSeconds
        );

        moveGeneralizedTimeSeconds += (
            accessTransferTimeSeconds
        );

        if (
            ![
                START_SERVICE,
                WALK_SERVICE,
            ].includes(
                gameState.currentService
            )
        ) {
            moveTransfers += 1;

            moveGeneralizedTimeSeconds += (
                TRANSFER_PENALTY_SECONDS
            );
        }
    } else if (
        ![
            START_SERVICE,
            WALK_SERVICE,
        ].includes(
            gameState.currentService
        )
        && gameState.currentService
        !== nextService
    ) {
        moveTransfers += 1;

        sameStationTransferTimeSeconds = (
            SAME_STATION_TRANSFER_TIME_SECONDS
        );

        moveActualTimeSeconds += (
            sameStationTransferTimeSeconds
        );

        moveGeneralizedTimeSeconds += (
            sameStationTransferTimeSeconds
            + TRANSFER_PENALTY_SECONDS
        );
    }

    let remainingRoute = null;

    if (
        nextStationId
        === gameState.targetStationId
    ) {
        remainingRoute = {
            generalizedTimeSeconds: 0,
            transfers: 0,
            actualTimeSeconds: 0,
            rideStops: 0,
        };
    } else {
        remainingRoute = findBestRoute(
            nextStationId,
            gameState.targetStationId,
            nextService
        );
    }

    let projectedGeneralizedTimeSeconds = null;
    let projectedActualTimeSeconds = null;

    if (remainingRoute) {
        projectedGeneralizedTimeSeconds = (
            moveGeneralizedTimeSeconds
            + remainingRoute
                .generalizedTimeSeconds
        );

        projectedActualTimeSeconds = (
            moveActualTimeSeconds
            + remainingRoute
                .actualTimeSeconds
        );
    }

    const classification = classifyMove(
        baseline.generalizedTimeSeconds,
        projectedGeneralizedTimeSeconds
    );

    return {
        baseline,
        remainingRoute,
        classification,

        nextStationId,
        nextService,

        rideTimeSeconds,
        accessTransferTimeSeconds,
        sameStationTransferTimeSeconds,

        moveActualTimeSeconds,
        moveGeneralizedTimeSeconds,
        moveTransfers,

        projectedGeneralizedTimeSeconds,
        projectedActualTimeSeconds,
    };
}


/* -------------------------------------------------------------------------- */
/* Darstellung der Spielschritte                                              */
/* -------------------------------------------------------------------------- */


function createLineBadge(lineName) {
    const badge = document.createElement(
        "span"
    );

    badge.className = "line-badge";

    badge.textContent = (
        lineName || "?"
    );

    return badge;
}


function renderServiceOptions() {
    dom.serviceOptions.replaceChildren();

    const options = (
        gameState.currentOptions
    );

    if (options.length === 0) {
        const emptyMessage = (
            document.createElement(
                "div"
            )
        );

        emptyMessage.className = (
            "empty-options"
        );

        emptyMessage.textContent = (
            "An dieser Station wurden keine möglichen Fahrtoptionen gefunden."
        );

        dom.serviceOptions.append(
            emptyMessage
        );

        return;
    }

    options.forEach(
        option => {
            const service = option.service;

            const lineName = (
                normalizeText(
                    service.line
                )
                || normalizeText(
                    service.routeId
                )
                || "?"
            );

            const headsignText = (
                service.headsigns
                    ?.slice(0, 3)
                    .join(", ")
                || "ohne Zielangabe"
            );

            const card = (
                document.createElement(
                    "button"
                )
            );

            card.type = "button";
            card.className = (
                "service-card"
            );

            card.append(
                createLineBadge(
                    lineName
                )
            );

            const content = (
                document.createElement(
                    "span"
                )
            );

            content.className = (
                "service-content"
            );

            const direction = (
                document.createElement(
                    "span"
                )
            );

            direction.className = (
                "service-direction"
            );

            direction.textContent = (
                `Richtung ${headsignText}`
            );

            content.append(
                direction
            );

            const destinationExamples = (
                service.destinations
                    ?.slice(0, 4)
                    .map(
                        destination => (
                            getStationName(
                                destination.stationId
                            )
                        )
                    )
                    .join(", ")
            );

            if (destinationExamples) {
                const examples = (
                    document.createElement(
                        "span"
                    )
                );

                examples.className = (
                    "service-examples"
                );

                examples.textContent = (
                    `Ausstiege z. B.: ${destinationExamples}`
                );

                content.append(
                    examples
                );
            }

            if (option.transferEdge) {
                const access = (
                    document.createElement(
                        "span"
                    )
                );

                access.className = (
                    "service-access"
                );

                const transferTime = (
                    parseSeconds(
                        option.transferEdge.time,
                        DEFAULT_TRANSFER_TIME_SECONDS
                    )
                );

                const boardingName = (
                    getStationName(
                        option.boardingStationId
                    )
                );

                access.textContent = (
                    `${formatMinutes(transferTime)} Fußweg `
                    + `zu ${boardingName}`
                );

                content.append(
                    access
                );
            }

            card.append(
                content
            );

            card.addEventListener(
                "click",
                () => {
                    chooseServiceOption(
                        option
                    );
                }
            );

            dom.serviceOptions.append(
                card
            );
        }
    );
}


function renderSelectedService(option) {
    dom.selectedServiceSummary
        .replaceChildren();

    const service = option.service;

    const lineName = (
        normalizeText(
            service.line
        )
        || normalizeText(
            service.routeId
        )
        || "?"
    );

    const headsignText = (
        service.headsigns
            ?.slice(0, 3)
            .join(", ")
        || "ohne Zielangabe"
    );

    dom.selectedServiceSummary.append(
        createLineBadge(
            lineName
        )
    );

    const textContainer = (
        document.createElement(
            "div"
        )
    );

    textContainer.className = (
        "selected-service-text"
    );

    const title = (
        document.createElement(
            "strong"
        )
    );

    title.textContent = (
        `${lineName} Richtung ${headsignText}`
    );

    textContainer.append(
        title
    );

    const detail = (
        document.createElement(
            "span"
        )
    );

    if (option.transferEdge) {
        const transferTime = (
            parseSeconds(
                option.transferEdge.time,
                DEFAULT_TRANSFER_TIME_SECONDS
            )
        );

        detail.textContent = (
            `${formatMinutes(transferTime)} Fußweg `
            + `zum Einstieg an `
            + getStationName(
                option.boardingStationId
            )
        );
    } else {
        detail.textContent = (
            `Einstieg an `
            + getStationName(
                option.boardingStationId
            )
        );
    }

    textContainer.append(
        detail
    );

    dom.selectedServiceSummary.append(
        textContainer
    );
}


function chooseServiceOption(option) {
    gameState.selectedOption = option;
    gameState.selectedDestination = null;

    destinationAutocomplete.clear();

    renderSelectedService(
        option
    );

    hide(dom.serviceStep);
    hide(dom.feedbackPanel);

    show(dom.destinationStep);

    dom.destinationInput.focus();

    scrollToElement(
        dom.destinationStep
    );
}


function backToServiceSelection() {
    gameState.selectedOption = null;
    gameState.selectedDestination = null;

    destinationAutocomplete.clear();

    hide(dom.destinationStep);
    show(dom.serviceStep);

    scrollToElement(
        dom.serviceStep
    );
}


function renderCurrentTurn() {
    if (
        gameState.currentStationId
        === gameState.targetStationId
    ) {
        finishGame(true);
        return;
    }

    if (
        gameState.moveNumber
        >= MAX_MOVES
    ) {
        finishGame(false);
        return;
    }

    gameState.selectedOption = null;
    gameState.selectedDestination = null;
    gameState.pendingEvaluation = null;

    destinationAutocomplete.clear();

    dom.currentStationName.textContent = (
        getStationName(
            gameState.currentStationId
        )
    );

    dom.targetStationName.textContent = (
        getStationName(
            gameState.targetStationId
        )
    );

    dom.moveCounter.textContent = (
        `${gameState.moveNumber + 1} `
        + `/ ${MAX_MOVES}`
    );

    gameState.currentOptions = (
        buildServiceOptions(
            gameState.currentStationId
        )
    );

    renderServiceOptions();

    hide(dom.destinationStep);
    hide(dom.feedbackPanel);
    hide(dom.finishedPanel);

    show(dom.serviceStep);

    scrollToElement(
        dom.gamePanel
    );
}


/* -------------------------------------------------------------------------- */
/* Feedback                                                                   */
/* -------------------------------------------------------------------------- */


function showMoveFeedback(
    evaluation
) {
    const option = (
        gameState.selectedOption
    );

    const destination = (
        gameState.selectedDestination
    );

    const service = option.service;

    const lineName = (
        normalizeText(
            service.line
        )
        || normalizeText(
            service.routeId
        )
        || "?"
    );

    const destinationName = (
        getStationName(
            destination.stationId
        )
    );

    const ratingName = (
        evaluation
            .classification
            .rating
    );

    const ratingInformation = (
        RATING_INFO[ratingName]
    );

    dom.feedbackPanel.classList.remove(
        "rating-green",
        "rating-yellow",
        "rating-orange",
        "rating-red",
        "rating-gray"
    );

    dom.feedbackPanel.classList.add(
        `rating-${ratingName}`
    );

    dom.feedbackPanel.dataset.rating = (
        ratingName
    );

    dom.feedbackSymbol.textContent = (
        ratingInformation.symbol
    );

    dom.feedbackTitle.textContent = (
        ratingInformation.label
    );

    const descriptionParts = [];

    if (
        evaluation
            .accessTransferTimeSeconds
        > 0
    ) {
        descriptionParts.push(
            `${formatMinutes(
                evaluation
                    .accessTransferTimeSeconds
            )} Fußweg zum Einstieg`
        );
    }

    if (
        evaluation
            .sameStationTransferTimeSeconds
        > 0
    ) {
        descriptionParts.push(
            `${formatMinutes(
                evaluation
                    .sameStationTransferTimeSeconds
            )} geschätzte Umstiegszeit`
        );
    }

    if (
        evaluation
            .projectedActualTimeSeconds
        !== null
    ) {
        descriptionParts.push(
            "Dieser Zug und der beste verbleibende Weg "
            + `benötigen voraussichtlich `
            + formatMinutes(
                evaluation
                    .projectedActualTimeSeconds
            )
        );
    } else {
        descriptionParts.push(
            "Vom neuen Standort konnte derzeit "
            + "keine weitere Route zum Ziel berechnet werden"
        );
    }

    dom.feedbackDescription.textContent = (
        `${descriptionParts.join(". ")}. `
        + "Der Spielzug bleibt gültig und die Reise geht weiter."
    );

    dom.feedbackMove.textContent = (
        `${lineName} → ${destinationName}`
    );

    dom.feedbackMoveTime.textContent = (
        formatMinutes(
            evaluation
                .moveActualTimeSeconds
        )
    );

    const extraSeconds = (
        evaluation
            .classification
            .extraSeconds
    );

    if (extraSeconds === null) {
        dom.feedbackDifference.textContent = (
            "nicht berechenbar"
        );
    } else if (extraSeconds <= 0) {
        dom.feedbackDifference.textContent = (
            "optimal"
        );
    } else {
        dom.feedbackDifference.textContent = (
            `+${formatMinutes(
                extraSeconds
            )}`
        );
    }

    dom.continueButton.textContent = (
        evaluation.nextStationId
        === gameState.targetStationId
            ? "Ziel auswerten"
            : "Weiterreisen"
    );

    hide(dom.destinationStep);
    hide(dom.serviceStep);

    show(dom.feedbackPanel);

    scrollToElement(
        dom.feedbackPanel
    );
}


function confirmSelectedMove() {
    if (
        !gameState.selectedOption
        || !gameState.selectedDestination
    ) {
        return;
    }

    const previousButtonText = (
        dom.confirmMoveButton.textContent
    );

    dom.confirmMoveButton.disabled = true;

    dom.confirmMoveButton.textContent = (
        "Wird bewertet …"
    );

    try {
        const evaluation = (
            evaluateSelectedMove(
                gameState.selectedOption,
                gameState.selectedDestination
            )
        );

        gameState.pendingEvaluation = (
            evaluation
        );

        showMoveFeedback(
            evaluation
        );
    } catch (error) {
        console.error(error);

        window.alert(
            "Der Spielzug konnte nicht bewertet werden: "
            + error.message
        );
    } finally {
        dom.confirmMoveButton.textContent = (
            previousButtonText
        );

        dom.confirmMoveButton.disabled = (
            !gameState.selectedDestination
        );
    }
}


function continueAfterFeedback() {
    const evaluation = (
        gameState.pendingEvaluation
    );

    if (!evaluation) {
        return;
    }

    gameState.currentStationId = (
        evaluation.nextStationId
    );

    gameState.currentService = (
        evaluation.nextService
    );

    gameState.totalActualSeconds += (
        evaluation.moveActualTimeSeconds
    );

    gameState.totalTransfers += (
        evaluation.moveTransfers
    );

    gameState.moveNumber += 1;

    gameState.pendingEvaluation = null;

    if (
        gameState.currentStationId
        === gameState.targetStationId
    ) {
        finishGame(true);
        return;
    }

    if (
        gameState.moveNumber
        >= MAX_MOVES
    ) {
        finishGame(false);
        return;
    }

    renderCurrentTurn();
}


/* -------------------------------------------------------------------------- */
/* Spielende                                                                  */
/* -------------------------------------------------------------------------- */


function finishGame(success) {
    hide(dom.serviceStep);
    hide(dom.destinationStep);
    hide(dom.feedbackPanel);

    show(dom.finishedPanel);

    const initialTravelTime = (
        gameState.initialBest
            ?.actualTimeSeconds
        ?? 0
    );

    const difference = (
        gameState.totalActualSeconds
        - initialTravelTime
    );

    if (success) {
        dom.finishSymbol.textContent = (
            "🎉"
        );

        dom.finishedTitle.textContent = (
            `${getStationName(
                gameState.targetStationId
            )} erreicht`
        );

        dom.finishedDescription.textContent = (
            "Du hast dein Ziel erreicht. "
            + "Auch weniger optimale Spielzüge durften "
            + "Teil deiner Route bleiben."
        );
    } else {
        dom.finishSymbol.textContent = (
            "⏱️"
        );

        dom.finishedTitle.textContent = (
            "Spielzuglimit erreicht"
        );

        dom.finishedDescription.textContent = (
            `Nach ${MAX_MOVES} Spielzügen wurde die Reise beendet. `
            + `Deine letzte Station ist `
            + getStationName(
                gameState.currentStationId
            )
            + "."
        );
    }

    dom.finishedMoves.textContent = (
        String(
            gameState.moveNumber
        )
    );

    dom.finishedTime.textContent = (
        formatMinutes(
            gameState.totalActualSeconds
        )
    );

    if (difference > 0) {
        dom.finishedDifference.textContent = (
            `+${formatMinutes(
                difference
            )}`
        );
    } else {
        dom.finishedDifference.textContent = (
            "optimal"
        );
    }

    scrollToElement(
        dom.finishedPanel
    );
}


/* -------------------------------------------------------------------------- */
/* Spielstart und Reset                                                       */
/* -------------------------------------------------------------------------- */


function startGame() {
    const startStationId = (
        normalizeText(
            dom.startStationId.value
        )
    );

    const targetStationId = (
        normalizeText(
            dom.targetStationId.value
        )
    );

    if (
        !startStationId
        || !targetStationId
    ) {
        setSetupMessage(
            "Bitte Start und Ziel aus den Vorschlägen auswählen.",
            "error"
        );

        return;
    }

    if (
        startStationId
        === targetStationId
    ) {
        setSetupMessage(
            "Start und Ziel müssen unterschiedlich sein.",
            "error"
        );

        return;
    }

    const oldButtonText = (
        dom.startGameButton.textContent
    );

    dom.startGameButton.disabled = true;

    dom.startGameButton.textContent = (
        "Route wird vorbereitet …"
    );

    try {
        const initialBest = (
            findBestRoute(
                startStationId,
                targetStationId,
                START_SERVICE
            )
        );

        if (!initialBest) {
            setSetupMessage(
                "Zwischen diesen Stationen wurde keine Route gefunden.",
                "error"
            );

            return;
        }

        gameState.active = true;

        gameState.startStationId = (
            startStationId
        );

        gameState.targetStationId = (
            targetStationId
        );

        gameState.currentStationId = (
            startStationId
        );

        gameState.currentService = (
            START_SERVICE
        );

        gameState.selectedOption = null;
        gameState.selectedDestination = null;
        gameState.pendingEvaluation = null;

        gameState.moveNumber = 0;
        gameState.totalActualSeconds = 0;
        gameState.totalTransfers = 0;

        gameState.initialBest = (
            initialBest
        );

        hide(dom.setupPanel);
        show(dom.gamePanel);

        renderCurrentTurn();
    } finally {
        dom.startGameButton.textContent = (
            oldButtonText
        );

        updateStartButtonState();
    }
}


function resetGame({
    clearStations = true,
} = {}) {
    gameState.active = false;

    gameState.startStationId = "";
    gameState.targetStationId = "";

    gameState.currentStationId = "";
    gameState.currentService = (
        START_SERVICE
    );

    gameState.selectedOption = null;
    gameState.selectedDestination = null;
    gameState.pendingEvaluation = null;

    gameState.currentOptions = [];

    gameState.moveNumber = 0;
    gameState.totalActualSeconds = 0;
    gameState.totalTransfers = 0;

    gameState.initialBest = null;

    destinationAutocomplete.clear();

    if (clearStations) {
        startAutocomplete.clear();
        targetAutocomplete.clear();
    }

    hide(dom.gamePanel);

    show(dom.setupPanel);

    updateStartButtonState();

    scrollToElement(
        dom.setupPanel
    );
}


function cancelCurrentGame() {
    if (!gameState.active) {
        resetGame();
        return;
    }

    const shouldCancel = window.confirm(
        "Möchtest du die aktuelle Reise wirklich abbrechen?"
    );

    if (shouldCancel) {
        resetGame();
    }
}


/* -------------------------------------------------------------------------- */
/* Autocomplete-Daten                                                         */
/* -------------------------------------------------------------------------- */


function getDestinationItems() {
    const destinations = (
        gameState.selectedOption
            ?.service
            ?.destinations
        ?? []
    );

    return destinations.map(
        destination => ({
            id: destination.stationId,

            name: getStationName(
                destination.stationId
            ),

            metadata: (
                `${formatMinutes(
                    destination.time
                )} · `
                + `${destination.stops} Halte`
            ),

            destination,
        })
    );
}


function initializeAutocompletes() {
    startAutocomplete = (
        createAutocomplete({
            input: dom.startInput,
            hiddenInput: dom.startStationId,
            suggestionList: dom.startSuggestions,

            getItems: () => (
                travelData.stationList
            ),

            getItemId: station => (
                station.id
            ),

            getItemLabel: station => (
                station.name
            ),

            getItemMeta: () => "",

            emptyMessage: (
                "Keine passende Station gefunden."
            ),

            onSelection: (
                updateStartButtonState
            ),

            onClear: (
                updateStartButtonState
            ),
        })
    );

    targetAutocomplete = (
        createAutocomplete({
            input: dom.targetInput,
            hiddenInput: dom.targetStationId,
            suggestionList: dom.targetSuggestions,

            getItems: () => (
                travelData.stationList
            ),

            getItemId: station => (
                station.id
            ),

            getItemLabel: station => (
                station.name
            ),

            getItemMeta: () => "",

            emptyMessage: (
                "Keine passende Station gefunden."
            ),

            onSelection: (
                updateStartButtonState
            ),

            onClear: (
                updateStartButtonState
            ),
        })
    );

    destinationAutocomplete = (
        createAutocomplete({
            input: dom.destinationInput,
            hiddenInput: (
                dom.destinationStationId
            ),

            suggestionList: (
                dom.destinationSuggestions
            ),

            getItems: (
                getDestinationItems
            ),

            getItemId: item => (
                item.id
            ),

            getItemLabel: item => (
                item.name
            ),

            getItemMeta: item => (
                item.metadata
            ),

            emptyMessage: (
                "Diese Station liegt nicht auf der gewählten Fahrt."
            ),

            maximumResults: 15,

            onSelection: item => {
                gameState.selectedDestination = (
                    item.destination
                );

                dom.confirmMoveButton.disabled = (
                    false
                );
            },

            onClear: () => {
                gameState.selectedDestination = (
                    null
                );

                dom.confirmMoveButton.disabled = (
                    true
                );
            },
        })
    );
}


/* -------------------------------------------------------------------------- */
/* Events                                                                     */
/* -------------------------------------------------------------------------- */


function bindEvents() {
    dom.swapStationsButton.addEventListener(
        "click",
        swapSelectedStations
    );

    dom.startGameButton.addEventListener(
        "click",
        startGame
    );

    dom.backToServicesButton.addEventListener(
        "click",
        backToServiceSelection
    );

    dom.confirmMoveButton.addEventListener(
        "click",
        confirmSelectedMove
    );

    dom.continueButton.addEventListener(
        "click",
        continueAfterFeedback
    );

    dom.newGameButton.addEventListener(
        "click",
        () => {
            resetGame();
        }
    );

    dom.cancelGameButton.addEventListener(
        "click",
        cancelCurrentGame
    );
}


/* -------------------------------------------------------------------------- */
/* Initialisierung                                                            */
/* -------------------------------------------------------------------------- */


function showLoadingError(error) {
    console.error(error);

    hide(dom.loadingScreen);
    hide(dom.travelApp);

    let errorText = (
        error?.message
        || "Unbekannter Fehler"
    );

    if (
        window.location.protocol
        === "file:"
    ) {
        errorText += (
            " Die Seite wurde direkt als Datei geöffnet. "
            + "Starte bitte einen lokalen Webserver."
        );
    }

    dom.errorMessage.textContent = (
        errorText
    );

    show(dom.errorPanel);
}


async function initializeTravelMode() {
    cacheDomElements();
    bindEvents();

    try {
        await loadTravelData();

        initializeAutocompletes();

        hide(dom.loadingScreen);
        hide(dom.errorPanel);

        show(dom.travelApp);

        updateStartButtonState();
    } catch (error) {
        showLoadingError(error);
    }
}


document.addEventListener(
    "DOMContentLoaded",
    initializeTravelMode
);
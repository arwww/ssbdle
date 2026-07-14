"use strict";

const MAX_ATTEMPTS = 6;
const DEFAULT_GAME_MODE = "global";
const GAME_MODE_STORAGE_KEY = "ssbdle_game_mode";

let stations = [];
let gameModes = {};
let answerIds = [];
let targetStation = null;
let attempts = 0;
let gameFinished = false;
let selectedStationId = null;

let currentGameMode =
  localStorage.getItem(GAME_MODE_STORAGE_KEY) ||
  DEFAULT_GAME_MODE;

let showSearchHints =
  localStorage.getItem(
    "ssbdle_show_search_hints"
  ) !== "false";

let currentTheme =
  localStorage.getItem("ssbdle_theme") ||
  (
    window.matchMedia(
      "(prefers-color-scheme: dark)"
    ).matches
      ? "dark"
      : "light"
  );

const guessedStationIds = new Set();
const stationById = new Map();
const stationByLabel = new Map();

const guessForm =
  document.querySelector("#guess-form");

const stationInput =
  document.querySelector("#station-input");

const searchDock =
  document.querySelector("#search-dock");

const searchResults =
  document.querySelector("#search-results");

const clearSearchButton =
  document.querySelector("#clear-search");

const toggleHintsButton =
  document.querySelector(
    "#toggle-hints-button"
  );

const toggleHintsLabel =
  document.querySelector(
    "#toggle-hints-label"
  );

const searchModeNote =
  document.querySelector("#search-mode-note");

const themeToggle =
  document.querySelector("#theme-toggle");

const themeIcon =
  document.querySelector("#theme-icon");

const themeLabel =
  document.querySelector("#theme-label");

const guessButton =
  document.querySelector("#guess-button");

const attemptCounter =
  document.querySelector("#attempt-counter");

const statusMessage =
  document.querySelector("#status-message");

const resultsBody =
  document.querySelector("#results-body");

const emptyState =
  document.querySelector("#empty-state");

const endMessage =
  document.querySelector("#end-message");

const endTitle =
  document.querySelector("#end-title");

const endText =
  document.querySelector("#end-text");

const restartButton =
  document.querySelector("#restart-button");

const ledInputScreen =
  document.querySelector("#led-input-screen");

const ledInputCanvas =
  document.querySelector("#led-input-canvas");

const ledFallbackText =
  document.querySelector("#led-fallback-text");

const gameModeButton =
  document.querySelector("#game-mode-button");

const gameModeLabel =
  document.querySelector("#game-mode-label");

const gameModeModal =
  document.querySelector("#game-mode-modal");

const gameModeBackdrop =
  document.querySelector(
    "#game-mode-backdrop"
  );

const closeGameModeModalButton =
  document.querySelector(
    "#close-game-mode-modal"
  );

const gameModeGrid =
  document.querySelector("#game-mode-grid");


function normalizeText(value) {
  return String(value ?? "")
    .trim()
    .toLocaleLowerCase("de-DE")
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "");
}


function prepareLedText(value) {
  return String(value ?? "")
    .replaceAll("Ä", "ä")
    .replaceAll("Ö", "ö")
    .replaceAll("Ü", "ü");
}


function setEquals(
  firstValues,
  secondValues
) {
  const firstSet =
    new Set(firstValues);

  const secondSet =
    new Set(secondValues);

  return (
    firstSet.size ===
      secondSet.size &&
    [...firstSet].every(
      (value) =>
        secondSet.has(value)
    )
  );
}


function getIntersection(
  firstValues,
  secondValues
) {
  const secondSet =
    new Set(secondValues);

  return [
    ...new Set(firstValues),
  ].filter(
    (value) =>
      secondSet.has(value)
  );
}


async function loadJson(path) {
  const response =
    await fetch(path);

  if (!response.ok) {
    throw new Error(
      `Datei konnte nicht geladen werden: ${path}`
    );
  }

  return response.json();
}


function getGameMode(modeId) {
  const mode =
    gameModes?.[modeId];

  if (
    !mode ||
    mode.enabled === false ||
    !Array.isArray(mode.answer_ids)
  ) {
    return null;
  }

  return mode;
}


function getCurrentGameMode() {
  return getGameMode(
    currentGameMode
  );
}


function getCurrentGameModeName() {
  return (
    getCurrentGameMode()?.name ||
    "Gesamtes Netz"
  );
}


function updateGameModeUi() {
  const activeMode =
    getCurrentGameMode();

  if (gameModeLabel) {
    gameModeLabel.textContent =
      activeMode?.name ||
      "Gesamtes Netz";
  }

  if (!gameModeGrid) {
    return;
  }

  const cards =
    gameModeGrid.querySelectorAll(
      ".mode-card"
    );

  for (const card of cards) {
    const modeId =
      card.dataset.mode;

    const mode =
      getGameMode(modeId);

    const unavailable =
      card.classList.contains(
        "coming-soon"
      ) ||
      card.getAttribute(
        "aria-disabled"
      ) === "true" ||
      !mode;

    const isActive =
      !unavailable &&
      modeId === currentGameMode;

    card.classList.toggle(
      "active",
      isActive
    );

    card.setAttribute(
      "aria-pressed",
      String(isActive)
    );

    if (!mode) {
      continue;
    }

    const nameElement =
      card.querySelector(
        ".mode-card-name"
      );

    const metaElement =
      card.querySelector(
        ".mode-card-meta"
      );

    const imageElement =
      card.querySelector("img");

    if (nameElement) {
      nameElement.textContent =
        mode.name;
    }

    if (metaElement) {
      const count =
        Number(
          mode.answer_count
        ) ||
        mode.answer_ids.length;

      metaElement.textContent =
        `${count.toLocaleString(
          "de-DE"
        )} Haltestellen`;
    }

    if (
      imageElement &&
      mode.image
    ) {
      imageElement.src =
        mode.image;
    }

    if (mode.description) {
      card.title =
        mode.description;
    }
  }
}


function openGameModeModal() {
  if (!gameModeModal) {
    return;
  }

  updateGameModeUi();

  gameModeModal.classList.remove(
    "hidden"
  );

  document.body.classList.add(
    "mode-modal-open"
  );

  gameModeButton?.setAttribute(
    "aria-expanded",
    "true"
  );

  const activeCard =
    gameModeGrid?.querySelector(
      ".mode-card.active"
    );

  requestAnimationFrame(() => {
    (
      activeCard ||
      closeGameModeModalButton
    )?.focus();
  });
}


function closeGameModeModal(
  restoreFocus = true
) {
  if (!gameModeModal) {
    return;
  }

  gameModeModal.classList.add(
    "hidden"
  );

  document.body.classList.remove(
    "mode-modal-open"
  );

  gameModeButton?.setAttribute(
    "aria-expanded",
    "false"
  );

  if (restoreFocus) {
    gameModeButton?.focus();
  }
}


function activateGameMode(modeId) {
  const mode =
    getGameMode(modeId);

  if (!mode) {
    return false;
  }

  const validAnswerIds =
    mode.answer_ids
      .map(
        (stationId) =>
          String(stationId)
      )
      .filter(
        (stationId) =>
          stationById.has(
            stationId
          )
      );

  if (
    validAnswerIds.length === 0
  ) {
    console.error(
      `Der Spielmodus "${modeId}" enthält keine gültigen Lösungen.`
    );

    return false;
  }

  if (
    validAnswerIds.length !==
    mode.answer_ids.length
  ) {
    console.warn(
      `Im Spielmodus "${modeId}" wurden ` +
      `${
        mode.answer_ids.length -
        validAnswerIds.length
      } unbekannte Lösungs-IDs ignoriert.`
    );
  }

  currentGameMode =
    modeId;

  answerIds =
    validAnswerIds;

  localStorage.setItem(
    GAME_MODE_STORAGE_KEY,
    currentGameMode
  );

  updateGameModeUi();

  return true;
}


function selectGameMode(modeId) {
  const mode =
    getGameMode(modeId);

  if (!mode) {
    statusMessage.textContent =
      "Dieser Spielmodus ist noch nicht verfügbar.";

    return;
  }

  if (
    modeId ===
    currentGameMode
  ) {
    closeGameModeModal();
    return;
  }

  if (
    !activateGameMode(modeId)
  ) {
    statusMessage.textContent =
      "Der Spielmodus konnte nicht geladen werden.";

    return;
  }

  startNewRound();

  statusMessage.textContent =
    `Spielmodus „${mode.name}“ aktiviert. ` +
    "Wähle eine Haltestelle aus.";

  closeGameModeModal();
}


function applyTheme() {
  document.documentElement.dataset.theme =
    currentTheme;

  const darkMode =
    currentTheme === "dark";

  themeIcon.textContent =
    darkMode
      ? "☀"
      : "◐";

  themeLabel.textContent =
    darkMode
      ? "Light Mode"
      : "Dark Mode";

  localStorage.setItem(
    "ssbdle_theme",
    currentTheme
  );

  renderLedInput();
}


function updateSearchHintMode() {
  searchResults.classList.toggle(
    "hard-mode",
    !showSearchHints
  );

  toggleHintsButton.classList.toggle(
    "hard-mode",
    !showSearchHints
  );

  toggleHintsLabel.textContent =
    showSearchHints
      ? "Suchhilfen an"
      : "Suchhilfen aus";

  searchModeNote.textContent =
    showSearchHints
      ? "Ort und Linien werden angezeigt"
      : "Nur Haltestellennamen werden angezeigt";

  toggleHintsButton.setAttribute(
    "aria-pressed",
    String(!showSearchHints)
  );

  localStorage.setItem(
    "ssbdle_show_search_hints",
    String(showSearchHints)
  );
}


function renderLedInput() {
  const value =
    stationInput.value.trim();

  const visibleText =
    value ||
    "Haltestelle suchen";

  ledFallbackText.textContent =
    visibleText;

  const ledRendererAvailable =
    typeof draw5x7 === "function" &&
    typeof measure5x7 === "function";

  if (!ledRendererAvailable) {
    ledFallbackText.classList.remove(
      "canvas-active"
    );

    return;
  }

  ledFallbackText.classList.add(
    "canvas-active"
  );

  requestAnimationFrame(() => {
    const width =
      Math.max(
        160,
        Math.floor(
          ledInputScreen.clientWidth
        )
      );

    const height =
      Math.max(
        60,
        Math.floor(
          ledInputScreen.clientHeight
        )
      );

    const pixelRatio =
      Math.max(
        1,
        window.devicePixelRatio || 1
      );

    ledInputCanvas.style.width =
      `${width}px`;

    ledInputCanvas.style.height =
      `${height}px`;

    ledInputCanvas.width =
      Math.round(
        width * pixelRatio
      );

    ledInputCanvas.height =
      Math.round(
        height * pixelRatio
      );

    const context =
      ledInputCanvas.getContext(
        "2d"
      );

    context.setTransform(
      pixelRatio,
      0,
      0,
      pixelRatio,
      0,
      0
    );

    context.clearRect(
      0,
      0,
      width,
      height
    );

    let displayText =
      prepareLedText(
        visibleText
      );

    const availableWidth =
      Math.max(
        80,
        width - 93
      );

    const maximumPitch = 8;
    const minimumPitch = 3.2;

    let pitch =
      availableWidth /
      Math.max(
        1,
        displayText.length * 6
      );

    pitch =
      Math.max(
        minimumPitch,
        Math.min(
          maximumPitch,
          pitch
        )
      );

    const maximumCharacters =
      Math.max(
        8,
        Math.floor(
          availableWidth /
          (
            6 *
            minimumPitch
          )
        )
      );

    if (
      displayText.length >
      maximumCharacters
    ) {
      displayText =
        displayText.slice(
          displayText.length -
          maximumCharacters
        );
    }

    const textHeight =
      7 * pitch;

    const startX = 21;

    const startY =
      Math.max(
        pitch,
        (
          height -
          textHeight
        ) / 2
      );

    const color =
      value
        ? "#ff8a00"
        : "#a65a12";

    const dotSize =
      Math.max(
        1.5,
        pitch * 0.34
      );

    draw5x7(
      context,
      displayText,
      startX,
      startY,
      pitch,
      dotSize,
      color
    );
  });
}


async function initializeGame() {
  try {
    statusMessage.textContent =
      "Haltestellendaten und Spielmodi werden geladen …";

    stationInput.disabled =
      true;

    guessButton.disabled =
      true;

    if (gameModeButton) {
      gameModeButton.disabled =
        true;
    }

    [
      stations,
      gameModes,
    ] = await Promise.all([
      loadJson(
        "./data/stations_game_modes.json"
      ),
      loadJson(
        "./data/game_modes.json"
      ),
    ]);

    if (
      !Array.isArray(stations)
    ) {
      throw new Error(
        "stations_game_modes.json enthält keine Liste."
      );
    }

    if (
      !gameModes ||
      typeof gameModes !==
        "object" ||
      Array.isArray(gameModes)
    ) {
      throw new Error(
        "game_modes.json enthält kein gültiges Objekt."
      );
    }

    buildStationMaps();

    if (
      !getGameMode(
        currentGameMode
      )
    ) {
      currentGameMode =
        getGameMode(
          DEFAULT_GAME_MODE
        )
          ? DEFAULT_GAME_MODE
          : Object.keys(
              gameModes
            ).find(
              (modeId) =>
                Boolean(
                  getGameMode(
                    modeId
                  )
                )
            );
    }

    if (
      !currentGameMode ||
      !activateGameMode(
        currentGameMode
      )
    ) {
      throw new Error(
        "Es konnte kein gültiger Spielmodus aktiviert werden."
      );
    }

    startNewRound();

    stationInput.disabled =
      false;

    guessButton.disabled =
      false;

    if (gameModeButton) {
      gameModeButton.disabled =
        false;
    }

    statusMessage.textContent =
      `${stations.length.toLocaleString(
        "de-DE"
      )} Haltestellen geladen. ` +
      `Spielmodus: ${getCurrentGameModeName()}.`;

    renderLedInput();
  } catch (error) {
    console.error(error);

    statusMessage.textContent =
      "Die Haltestellendaten oder Spielmodi konnten nicht geladen werden.";

    stationInput.disabled =
      true;

    guessButton.disabled =
      true;

    if (gameModeButton) {
      gameModeButton.disabled =
        true;
    }
  }
}


function buildStationMaps() {
  stationById.clear();
  stationByLabel.clear();

  for (
    const station
    of stations
  ) {
    station.id =
      String(station.id);

    stationById.set(
      station.id,
      station
    );

    stationByLabel.set(
      normalizeText(
        station.label
      ),
      station
    );
  }
}


function levenshteinDistance(
  firstText,
  secondText
) {
  const first =
    normalizeText(firstText);

  const second =
    normalizeText(secondText);

  const rows =
    first.length + 1;

  const columns =
    second.length + 1;

  const matrix =
    Array.from(
      {
        length: rows,
      },
      () =>
        Array(
          columns
        ).fill(0)
    );

  for (
    let row = 0;
    row < rows;
    row += 1
  ) {
    matrix[row][0] =
      row;
  }

  for (
    let column = 0;
    column < columns;
    column += 1
  ) {
    matrix[0][column] =
      column;
  }

  for (
    let row = 1;
    row < rows;
    row += 1
  ) {
    for (
      let column = 1;
      column < columns;
      column += 1
    ) {
      const substitutionCost =
        first[row - 1] ===
        second[column - 1]
          ? 0
          : 1;

      matrix[row][column] =
        Math.min(
          matrix[row - 1][column] + 1,
          matrix[row][column - 1] + 1,
          matrix[row - 1][column - 1] +
            substitutionCost
        );
    }
  }

  return matrix[
    rows - 1
  ][
    columns - 1
  ];
}


function getFuzzyScore(
  candidate,
  query
) {
  if (
    query.length < 4
  ) {
    return 0;
  }

  const maximumDistance =
    query.length >= 10
      ? 3
      : 2;

  const candidateStart =
    candidate.slice(
      0,
      query.length + 2
    );

  const fullDistance =
    Math.abs(
      candidate.length -
      query.length
    ) <= maximumDistance
      ? levenshteinDistance(
          candidate,
          query
        )
      : Number
          .POSITIVE_INFINITY;

  const prefixDistance =
    levenshteinDistance(
      candidateStart,
      query
    );

  const bestDistance =
    Math.min(
      fullDistance,
      prefixDistance
    );

  return (
    bestDistance <=
    maximumDistance
      ? 600 -
        bestDistance * 50
      : 0
  );
}


function getSearchScore(
  station,
  rawQuery
) {
  const query =
    normalizeText(rawQuery);

  if (!query) {
    return 1;
  }

  const name =
    normalizeText(
      station.name
    );

  const label =
    normalizeText(
      station.label
    );

  const municipality =
    normalizeText(
      station.municipality
    );

  const locality =
    normalizeText(
      station.locality
    );

  if (
    name === query ||
    label === query
  ) {
    return 1000;
  }

  if (
    name.startsWith(query)
  ) {
    return 900;
  }

  if (
    label.startsWith(query)
  ) {
    return 850;
  }

  const nameWords =
    name.split(/\s+/);

  if (
    nameWords.some(
      (word) =>
        word.startsWith(
          query
        )
    )
  ) {
    return 800;
  }

  if (
    name.includes(query)
  ) {
    return 750;
  }

  if (
    label.includes(query)
  ) {
    return 700;
  }

  if (
    municipality.startsWith(
      query
    ) ||
    locality.startsWith(
      query
    )
  ) {
    return 500;
  }

  return Math.max(
    ...[
      name,
      label,
      ...nameWords,
    ].map(
      (candidate) =>
        getFuzzyScore(
          candidate,
          query
        )
    )
  );
}


function getSearchMatches(query) {
  return stations
    .map(
      (station) => ({
        station,
        score:
          getSearchScore(
            station,
            query
          ),
      })
    )
    .filter(
      (entry) =>
        entry.score > 0
    )
    .sort(
      (
        firstEntry,
        secondEntry
      ) => {
        if (
          secondEntry.score !==
          firstEntry.score
        ) {
          return (
            secondEntry.score -
            firstEntry.score
          );
        }

        return (
          firstEntry
            .station
            .label
            .localeCompare(
              secondEntry
                .station
                .label,
              "de"
            )
        );
      }
    )
    .map(
      (entry) =>
        entry.station
    );
}


function closeSearchResults() {
  searchResults.classList.add(
    "hidden"
  );

  stationInput.setAttribute(
    "aria-expanded",
    "false"
  );
}


function createSearchResult(
  station
) {
  const button =
    document.createElement(
      "button"
    );

  button.type =
    "button";

  button.className =
    "search-result";

  button.dataset.stationId =
    station.id;

  button.setAttribute(
    "role",
    "option"
  );

  const mainArea =
    document.createElement(
      "span"
    );

  mainArea.className =
    "result-main";

  const name =
    document.createElement(
      "span"
    );

  name.className =
    "result-name";

  name.textContent =
    station.name;

  const location =
    document.createElement(
      "span"
    );

  location.className =
    "result-location";

  const locationParts = [
    station.municipality,
    station.locality,
  ]
    .filter(Boolean)
    .filter(
      (
        value,
        index,
        values
      ) =>
        values.indexOf(
          value
        ) === index
    );

  location.textContent =
    locationParts.join(
      " · "
    ) ||
    "Ort nicht angegeben";

  mainArea.append(
    name,
    location
  );

  const lines =
    document.createElement(
      "span"
    );

  lines.className =
    "result-lines";

  const stationLines =
    station.lines ?? [];

  const linePreview =
    stationLines
      .slice(0, 4)
      .join(", ");

  const remainingLineCount =
    stationLines.length - 4;

  if (!linePreview) {
    lines.textContent =
      "Keine Linienangabe";
  } else if (
    remainingLineCount > 0
  ) {
    lines.textContent =
      `${linePreview} ` +
      `+${remainingLineCount}`;
  } else {
    lines.textContent =
      linePreview;
  }

  button.append(
    mainArea,
    lines
  );

  return button;
}


function renderSearchResults(
  query = ""
) {
  const matches =
    getSearchMatches(query);

  searchResults.innerHTML =
    "";

  if (
    matches.length === 0
  ) {
    const noResults =
      document.createElement(
        "div"
      );

    noResults.className =
      "no-search-results";

    noResults.textContent =
      "Keine passende Haltestelle gefunden.";

    searchResults.append(
      noResults
    );
  } else {
    for (
      const station
      of matches
    ) {
      searchResults.append(
        createSearchResult(
          station
        )
      );
    }
  }

  searchResults.classList.remove(
    "hidden"
  );

  stationInput.setAttribute(
    "aria-expanded",
    "true"
  );
}


function selectSearchStation(
  station
) {
  selectedStationId =
    station.id;

  stationInput.value =
    station.label;

  clearSearchButton.classList.remove(
    "hidden"
  );

  closeSearchResults();
  renderLedInput();
}


function chooseRandomTarget() {
  if (
    answerIds.length === 0
  ) {
    throw new Error(
      "Der aktive Spielmodus enthält keine Lösungsstationen."
    );
  }

  const randomIndex =
    Math.floor(
      Math.random() *
      answerIds.length
    );

  const targetId =
    answerIds[randomIndex];

  const station =
    stationById.get(targetId);

  if (!station) {
    throw new Error(
      `Lösungsstation nicht gefunden: ${targetId}`
    );
  }

  return station;
}


function startNewRound() {
  targetStation =
    chooseRandomTarget();

  attempts = 0;
  gameFinished = false;
  selectedStationId = null;

  guessedStationIds.clear();

  resultsBody.innerHTML =
    "";

  stationInput.value =
    "";

  stationInput.disabled =
    false;

  guessButton.disabled =
    false;

  clearSearchButton.classList.add(
    "hidden"
  );

  closeSearchResults();

  emptyState.classList.remove(
    "hidden"
  );

  endMessage.classList.add(
    "hidden"
  );

  updateAttemptCounter();

  statusMessage.textContent =
    "Wähle eine Haltestelle aus.";

  renderLedInput();

  console.info(
    `Entwicklungsmodus (${getCurrentGameModeName()}) – gesuchte Station:`,
    targetStation.label
  );
}


function updateAttemptCounter() {
  attemptCounter.textContent =
    `${attempts} / ${MAX_ATTEMPTS}`;
}


function findStationFromInput() {
  if (selectedStationId) {
    return (
      stationById.get(
        selectedStationId
      ) ?? null
    );
  }

  return (
    stationByLabel.get(
      normalizeText(
        stationInput.value
      )
    ) ?? null
  );
}


function compareModes(
  guess,
  target
) {
  const guessModes =
    guess.modes ?? [];

  const targetModes =
    target.modes ?? [];

  if (
    setEquals(
      guessModes,
      targetModes
    )
  ) {
    return {
      cssClass:
        "correct",
      text:
        guessModes.join(
          ", "
        ) ||
        "Keine Angabe",
    };
  }

  const commonModes =
    getIntersection(
      guessModes,
      targetModes
    );

  if (
    commonModes.length > 0
  ) {
    return {
      cssClass:
        "partial",
      text:
        `${guessModes.join(", ")} ` +
        `(${commonModes.length} gemeinsam)`,
    };
  }

  return {
    cssClass:
      "wrong",
    text:
      guessModes.join(
        ", "
      ) ||
      "Keine Angabe",
  };
}


function compareLocality(
  guess,
  target
) {
  const guessLocality =
    guess.locality ||
    guess.municipality ||
    "Unbekannt";

  const targetLocality =
    target.locality ||
    target.municipality ||
    "Unbekannt";

  if (
    normalizeText(
      guessLocality
    ) ===
    normalizeText(
      targetLocality
    )
  ) {
    return {
      cssClass:
        "correct",
      text:
        guessLocality,
    };
  }

  if (
    normalizeText(
      guess.municipality
    ) ===
    normalizeText(
      target.municipality
    )
  ) {
    return {
      cssClass:
        "partial",
      text:
        guessLocality,
    };
  }

  return {
    cssClass:
      "wrong",
    text:
      guessLocality,
  };
}


function compareLineCount(
  guess,
  target
) {
  const guessCount =
    Number(
      guess.line_count
    ) || 0;

  const targetCount =
    Number(
      target.line_count
    ) || 0;

  if (
    guessCount ===
    targetCount
  ) {
    return {
      cssClass:
        "correct",
      text:
        `${guessCount}`,
    };
  }

  return {
    cssClass:
      "partial",
    text:
      guessCount <
      targetCount
        ? `${guessCount} ↑`
        : `${guessCount} ↓`,
  };
}


function compareLines(
  guess,
  target
) {
  const guessLines =
    guess.lines ?? [];

  const targetLines =
    target.lines ?? [];

  const commonLines =
    getIntersection(
      guessLines,
      targetLines
    );

  if (
    setEquals(
      guessLines,
      targetLines
    )
  ) {
    return {
      cssClass:
        "correct",
      text:
        commonLines.join(
          ", "
        ) ||
        "Keine",
    };
  }

  if (
    commonLines.length > 0
  ) {
    return {
      cssClass:
        "partial",
      text:
        commonLines.join(
          ", "
        ),
    };
  }

  return {
    cssClass:
      "wrong",
    text:
      "Keine",
  };
}


function toRadians(degrees) {
  return (
    degrees *
    (
      Math.PI /
      180
    )
  );
}


function calculateDistanceKm(
  firstStation,
  secondStation
) {
  const earthRadiusKm =
    6371;

  const firstLatitude =
    Number(
      firstStation.latitude
    );

  const firstLongitude =
    Number(
      firstStation.longitude
    );

  const secondLatitude =
    Number(
      secondStation.latitude
    );

  const secondLongitude =
    Number(
      secondStation.longitude
    );

  const latitudeDifference =
    toRadians(
      secondLatitude -
      firstLatitude
    );

  const longitudeDifference =
    toRadians(
      secondLongitude -
      firstLongitude
    );

  const firstLatitudeRadians =
    toRadians(
      firstLatitude
    );

  const secondLatitudeRadians =
    toRadians(
      secondLatitude
    );

  const a =
    Math.sin(
      latitudeDifference / 2
    ) ** 2 +
    Math.cos(
      firstLatitudeRadians
    ) *
      Math.cos(
        secondLatitudeRadians
      ) *
      Math.sin(
        longitudeDifference / 2
      ) ** 2;

  const c =
    2 *
    Math.atan2(
      Math.sqrt(a),
      Math.sqrt(1 - a)
    );

  return (
    earthRadiusKm * c
  );
}


function calculateBearing(
  firstStation,
  secondStation
) {
  const firstLatitude =
    toRadians(
      Number(
        firstStation.latitude
      )
    );

  const secondLatitude =
    toRadians(
      Number(
        secondStation.latitude
      )
    );

  const longitudeDifference =
    toRadians(
      Number(
        secondStation.longitude
      ) -
      Number(
        firstStation.longitude
      )
    );

  const y =
    Math.sin(
      longitudeDifference
    ) *
    Math.cos(
      secondLatitude
    );

  const x =
    Math.cos(
      firstLatitude
    ) *
      Math.sin(
        secondLatitude
      ) -
    Math.sin(
      firstLatitude
    ) *
      Math.cos(
        secondLatitude
      ) *
      Math.cos(
        longitudeDifference
      );

  return (
    (
      Math.atan2(
        y,
        x
      ) *
      (
        180 /
        Math.PI
      )
    ) +
    360
  ) % 360;
}


function getDirection(bearing) {
  const directions = [
    {
      text:
        "Norden",
      arrow:
        "↑",
    },
    {
      text:
        "Nordosten",
      arrow:
        "↗",
    },
    {
      text:
        "Osten",
      arrow:
        "→",
    },
    {
      text:
        "Südosten",
      arrow:
        "↘",
    },
    {
      text:
        "Süden",
      arrow:
        "↓",
    },
    {
      text:
        "Südwesten",
      arrow:
        "↙",
    },
    {
      text:
        "Westen",
      arrow:
        "←",
    },
    {
      text:
        "Nordwesten",
      arrow:
        "↖",
    },
  ];

  return directions[
    Math.round(
      bearing / 45
    ) % 8
  ];
}


function compareDistance(
  guess,
  target
) {
  if (
    guess.id ===
    target.id
  ) {
    return {
      cssClass:
        "correct",
      text:
        "0 km",
    };
  }

  const distance =
    calculateDistanceKm(
      guess,
      target
    );

  const direction =
    getDirection(
      calculateBearing(
        guess,
        target
      )
    );

  const cssClass =
    distance <= 5
      ? "partial"
      : "wrong";

  const formattedDistance =
    distance.toLocaleString(
      "de-DE",
      {
        minimumFractionDigits:
          1,
        maximumFractionDigits:
          1,
      }
    );

  return {
    cssClass,
    text:
      `${formattedDistance} km ` +
      `${direction.arrow} ` +
      `${direction.text}`,
  };
}


function createCell(
  text,
  cssClass
) {
  const cell =
    document.createElement(
      "td"
    );

  cell.textContent =
    text;

  cell.classList.add(
    cssClass
  );

  return cell;
}


function displayGuess(guess) {
  emptyState.classList.add(
    "hidden"
  );

  const row =
    document.createElement(
      "tr"
    );

  const stationClass =
    guess.id ===
    targetStation.id
      ? "correct"
      : "wrong";

  const modesResult =
    compareModes(
      guess,
      targetStation
    );

  const localityResult =
    compareLocality(
      guess,
      targetStation
    );

  const lineCountResult =
    compareLineCount(
      guess,
      targetStation
    );

  const linesResult =
    compareLines(
      guess,
      targetStation
    );

  const distanceResult =
    compareDistance(
      guess,
      targetStation
    );

  row.append(
    createCell(
      guess.label,
      stationClass
    ),
    createCell(
      modesResult.text,
      modesResult.cssClass
    ),
    createCell(
      localityResult.text,
      localityResult.cssClass
    ),
    createCell(
      lineCountResult.text,
      lineCountResult.cssClass
    ),
    createCell(
      linesResult.text,
      linesResult.cssClass
    ),
    createCell(
      distanceResult.text,
      distanceResult.cssClass
    )
  );

  resultsBody.append(row);
}


function finishGame(won) {
  gameFinished =
    true;

  stationInput.disabled =
    true;

  guessButton.disabled =
    true;

  closeSearchResults();

  endMessage.classList.remove(
    "hidden"
  );

  if (won) {
    endTitle.textContent =
      "Richtig!";

    endText.textContent =
      `Die gesuchte Station war ${targetStation.label}. ` +
      `Du hast ${attempts} ` +
      `Versuch${
        attempts === 1
          ? ""
          : "e"
      } gebraucht.`;

    return;
  }

  endTitle.textContent =
    "Leider nicht geschafft";

  endText.textContent =
    `Die gesuchte Station war ${targetStation.label}.`;
}


function handleGuess(event) {
  event.preventDefault();

  if (gameFinished) {
    return;
  }

  const guessedStation =
    findStationFromInput();

  if (!guessedStation) {
    statusMessage.textContent =
      "Bitte wähle eine Haltestelle aus der Ergebnisliste.";

    stationInput.focus();

    renderSearchResults(
      stationInput.value
    );

    return;
  }

  if (
    guessedStationIds.has(
      guessedStation.id
    )
  ) {
    statusMessage.textContent =
      "Diese Haltestelle hast du bereits verwendet.";

    return;
  }

  guessedStationIds.add(
    guessedStation.id
  );

  attempts += 1;

  displayGuess(
    guessedStation
  );

  updateAttemptCounter();

  stationInput.value =
    "";

  selectedStationId =
    null;

  clearSearchButton.classList.add(
    "hidden"
  );

  closeSearchResults();
  renderLedInput();

  const won =
    guessedStation.id ===
    targetStation.id;

  if (won) {
    statusMessage.textContent =
      "Die Station wurde richtig erraten.";

    finishGame(true);
    return;
  }

  if (
    attempts >=
    MAX_ATTEMPTS
  ) {
    statusMessage.textContent =
      "Alle sechs Versuche wurden verwendet.";

    finishGame(false);
    return;
  }

  const remainingAttempts =
    MAX_ATTEMPTS -
    attempts;

  statusMessage.textContent =
    `Noch ${remainingAttempts} ` +
    `Versuch${
      remainingAttempts === 1
        ? ""
        : "e"
    }.`;
}


stationInput.addEventListener(
  "focus",
  () => {
    if (!gameFinished) {
      renderSearchResults(
        stationInput.value
      );
    }
  }
);


stationInput.addEventListener(
  "input",
  () => {
    selectedStationId =
      null;

    clearSearchButton.classList.toggle(
      "hidden",
      stationInput.value.length === 0
    );

    renderLedInput();

    renderSearchResults(
      stationInput.value
    );
  }
);


searchResults.addEventListener(
  "mousedown",
  (event) => {
    event.preventDefault();
  }
);


searchResults.addEventListener(
  "click",
  (event) => {
    const resultButton =
      event.target.closest(
        ".search-result"
      );

    if (!resultButton) {
      return;
    }

    const station =
      stationById.get(
        resultButton.dataset.stationId
      );

    if (!station) {
      return;
    }

    selectSearchStation(
      station
    );

    stationInput.focus();
  }
);


clearSearchButton.addEventListener(
  "click",
  () => {
    stationInput.value =
      "";

    selectedStationId =
      null;

    clearSearchButton.classList.add(
      "hidden"
    );

    renderLedInput();
    stationInput.focus();
    renderSearchResults("");
  }
);


toggleHintsButton.addEventListener(
  "click",
  () => {
    showSearchHints =
      !showSearchHints;

    updateSearchHintMode();

    if (
      !searchResults.classList.contains(
        "hidden"
      )
    ) {
      renderSearchResults(
        stationInput.value
      );
    }
  }
);


themeToggle.addEventListener(
  "click",
  () => {
    currentTheme =
      currentTheme === "dark"
        ? "light"
        : "dark";

    applyTheme();
  }
);


gameModeButton?.addEventListener(
  "click",
  openGameModeModal
);


gameModeBackdrop?.addEventListener(
  "click",
  () => {
    closeGameModeModal();
  }
);


closeGameModeModalButton
  ?.addEventListener(
    "click",
    () => {
      closeGameModeModal();
    }
  );


gameModeGrid?.addEventListener(
  "click",
  (event) => {
    const modeCard =
      event.target.closest(
        ".mode-card"
      );

    if (!modeCard) {
      return;
    }

    if (
      modeCard.classList.contains(
        "coming-soon"
      ) ||
      modeCard.getAttribute(
        "aria-disabled"
      ) === "true"
    ) {
      statusMessage.textContent =
        "Dieser Spielmodus folgt in einer späteren Version.";

      return;
    }

    selectGameMode(
      modeCard.dataset.mode
    );
  }
);


document.addEventListener(
  "keydown",
  (event) => {
    if (
      event.key === "Escape" &&
      !gameModeModal?.classList.contains(
        "hidden"
      )
    ) {
      closeGameModeModal();
    }
  }
);


document.addEventListener(
  "click",
  (event) => {
    const clickedInsideSearch =
      event.target.closest(
        "#search-dock"
      );

    const clickedHintsButton =
      event.target.closest(
        "#toggle-hints-button"
      );

    if (
      !clickedInsideSearch &&
      !clickedHintsButton
    ) {
      closeSearchResults();
    }
  }
);


guessForm.addEventListener(
  "submit",
  handleGuess
);


restartButton.addEventListener(
  "click",
  () => {
    startNewRound();

    searchDock.scrollIntoView({
      behavior:
        "smooth",
      block:
        "end",
    });

    stationInput.focus();
  }
);


window.addEventListener(
  "resize",
  renderLedInput
);


if (
  typeof ResizeObserver !==
  "undefined"
) {
  const resizeObserver =
    new ResizeObserver(
      renderLedInput
    );

  resizeObserver.observe(
    ledInputScreen
  );
}


applyTheme();
updateSearchHintMode();
renderLedInput();
initializeGame();
// WebSocket connection handler
let ws = null;
let gameState = null;
let selectedCardIndex = null;
let selectedTarget = null;
let lang = "Ru";


// Helper to send logs to server (+ server.py needs LOG_HANDLER)
function logToServer(message) {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
            type: 'client_log', // Corresponds to websocket_handler's 'client_log' processing
            message: message
        }));
    }
}

// Main WebSocket handler
function connectWebSocket(nickname) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
    
    ws.onopen = () => {
        logToServer('WebSocket connection established');
        ws.send(JSON.stringify({ 
            type: 'login', // Corresponds to websocket_handler's 'login' processing
            nickname: nickname 
        }));
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'state_update') {
                gameState = data.state;
                renderGame(gameState, data.hand, data.name);
            }
        } catch (e) {
            logToServer('Error processing message: ' + e);
        }
    };

    ws.onerror = (error) => {
        logToServer('WebSocket error: ' + JSON.stringify(error));
    };

    ws.onclose = () => {
        logToServer('WebSocket connection closed');
    };
}

// Game rendering core
function renderGame(state, hand, nickname) {
    if (!state) return;
    
    // const gridOverlay = document.createElement('div');
    // gridOverlay.className = 'grid-overlay';
    // document.body.appendChild(gridOverlay);

    document.getElementById('deck-count').textContent = state.deck_size || 0;
    // document.getElementById('discard-last').textContent = getDiscardText(state);
    document.getElementById('discard-last').innerHTML = getDiscardText(state);
    
    // Update direction arrow
    updateDirectionArrow(state);

    
    // Clear existing player elements
    document.querySelectorAll('.player-area').forEach(el => el.remove());
    
    // Create player elements

    var selected_target = "";
    var self_name = "";
    state.players.forEach((player, index) => {
        is_self = player.nickname === nickname;
        if(is_self){ selected_target = nickname in state.cs.pl_pl ? state.cs.pl_pl[nickname] : "";}
        if(is_self){ self_name = nickname; }
    });
    state.players.forEach((player, index) => {

        is_self = player.nickname === nickname;
        createPlayerElement(state, player, index, state.current_player, hand, is_self, self_name, selected_target);
    });
    
    // Update hints
    document.getElementById('hints').textContent = getHintText(state);
}

function getDiscardText(state) {
    if (!state.discard_top) return 'None';

    // logToServer('getDiscardText discard_top.discard_face_down: ' + state.discard_top.discard_face_down);

    if (state.discard_top.discard_face_down) {
        // Current player's hand
        return ` <div class="card face-down"></div> `

    } else {
        discard_text_ex = state.discard_comment ? `${state.discard_comment[0]} -> ${state.discard_comment[1]}` : "";
        return `<div class="card"><div class="card" style="background-image:url(static/${state.discard_top.image}); background-size: cover;">
                </div><div class="card-name">${state.discard_top.name_displayed}</div><div class="card-name">${discard_text_ex}</div></div>`
    }

    // return state.discard_top.face_down ? 'Face down' : state.discard_top.name_displayed;
}

function updateDirectionArrow(state) {
    const arrow = document.getElementById('direction-arrow');
    if (arrow) {
        // arrow.innerText = "⟳";
        arrow.innerText = state.direction === 1 ? "↻" : "↺";
    }
}

function createPlayerElement(state, player, index, currentPlayerIndex, hand, is_self, self_name, selected_target) {
    const playerEl = document.createElement('div');
    playerEl.className = `player-area ${index === currentPlayerIndex ? 'active' : ''} ${player.is_active ? '' : 'frozen'}`;
    playerEl.id = `player-${index}`;
    var is_current = index === currentPlayerIndex;
    var is_targeted = player.is_targeted;
    
    // Position player around the table (8 positions)
    const positions = [
        { top: '10%', left: '50%' },   // Top
        { top: '30%', left: '85%' },    // Top-Right
        { top: '50%', left: '90%' },    // Right
        { top: '70%', left: '85%' },    // Bottom-Right
        { top: '90%', left: '50%' },    // Bottom
        { top: '70%', left: '15%' },    // Bottom-Left
        { top: '50%', left: '10%' },    // Left
        { top: '30%', left: '15%' }     // Top-Left
    ];
    Object.assign(playerEl.style, positions[index % 8]);
    
    // Player content

    // player_class = player.is_targeted? `player-name ${gameState.exchange_comment.includes(player.nickname)? " player-name-exchange" : ""} ${gameState.discard_comment.includes(player.nickname) ? " player-name-action" : ""} ${is_current ? " player-name-active" : ""}` : "player-name-target";
    player_class = `player-name ${gameState.exchange_comment.includes(player.nickname)? " player-name-exchange" : ""} ${gameState.discard_comment.includes(player.nickname) ? " player-name-action" : ""} ${is_current ? " player-name-active" : ""}`;
    // logToServer(player_class);
    playerEl.innerHTML = `
    <div class="player-content" ${selected_target === player.nickname ? 'style="background-color:#6683D9;"' : ''} ${is_self && player.is_infected ? 'style="background-color:#0BD9C4;"' : ''} ${is_self && player.is_thing ? 'style="background-color:#134254;"' : ''}>
        <div class="${player_class}">
        ${player.is_dead ? player.nickname + ' is Dead' : player.nickname}
        ${player.lock_exchange ? ' +++' : ''}
        ${(is_self || (gameState.phase === "human-win"  || gameState.phase === "thing-win")) && player.is_infected   ? ' Infected' : ''}
        ${(is_self || (gameState.phase === "human-win"  || gameState.phase === "thing-win")) && player.is_thing || (gameState.phase === "human-win"  || gameState.phase === "thing-win")? ' Thing' : ''}
        ${player.is_tranquilised>0? ` Tied up ${player.is_tranquilised}` : ''}
        ${player.is_reanimated>0? ` Reanimated ${player.is_reanimated-1}` : ''}
        </div>
        <div class="hand">${renderPlayerHand(state, player, index, hand, is_self, self_name)}</div>
        ${is_self ? renderActionButtons(is_self, is_current, is_targeted, player.is_dead, player.is_tranquilised, player.is_forced_discards) : ''}
    </div>
`;

    // logToServer(player.nickname);
    // logToServer(player.hand);
    if(is_self && (player.nickname in state.cs.pl_cd) && (typeof hand[state.cs.pl_cd[player.nickname]] !== 'undefined')){
        document.getElementById('extended-description').textContent = hand[state.cs.pl_cd[player.nickname]].description;}


    

    if (!is_self && gameState.phase === 'action') { // Only non-current players in action phase
        playerEl.classList.add('clickable');
        playerEl.onclick = () => handlePlayerClick(index);
    }
    
    document.querySelector('.game-table').appendChild(playerEl);
}

function renderPlayerHand(state, player, index, hand, is_self, self_name) {
    if (is_self) {
        // Current player's hand
        // player lock_exchan
        var selected_card = state.cs.pl_cd[player.nickname];
        return hand.map((card, idx) => `
        <div class="card">
            <div class="card ${idx === selected_card ? 'selected' : ''}" 
                 data-idx="${idx}"
                 onclick="handleCardClick(${idx})"
                 style="background-image:url(static/${card.image}); background-size: cover;"
                 ${gameState.phase === 'exchange' && card.is_exchangable && idx === selected_card && !player.lock_exchange ? 'style="border-color:blue;border-width:thick;"' : ''}
                 ${gameState.phase === 'exchange' && card.is_exchangable && idx === selected_card && player.lock_exchange ? 'style="border-color:green;border-width:thick;"' : ''}
                 ${gameState.phase === 'exchange' && !card.is_exchangable && idx === selected_card && !player.lock_exchange ? 'style="border-color:red;border-width:thick;"' : ''}
                 ${gameState.phase === 'exchange' && !card.is_exchangable && idx === selected_card && player.lock_exchange ? 'style="border-color:purple;border-width:thick;"' : ''}

                 ${gameState.phase === 'action' && card.require_player_lock && idx === selected_card && player.nickname in state.cs.pl_pl ? 'style="border-color:green;border-width:thick;"' : ''}
                 ${gameState.phase === 'action' && card.require_player_lock && idx === selected_card && !player.nickname in state.cs.pl_pl ? 'style="border-color:red;border-width:thick;"' : ''}
                 ${gameState.phase === 'action' && !card.require_player_lock && idx === selected_card ? 'style="border-color:green;border-width:thick;"' : ''}

                 ${(gameState.phase === 'post-action') && !card.is_reactable && idx === selected_card ? 'style="border-color:red;border-width:thick;"' : ''}
                 ${(gameState.phase === 'post-action') && card.is_reactable && idx === selected_card ? 'style="border-color:green;border-width:thick;"' : ''}

                 >
                
            </div><div class="card-name">${card.name_displayed}</div></div>
        `).join('');
    } else {
        // logToServer(hand);
        return player.hand.map((card, idx) => `
            <div class="card ${card.show_to.includes(self_name) || card.show_to.includes('all') || gameState.phase === "human-win"  || gameState.phase === "thing-win" ? '' : 'face-down'}">
                ${card.show_to.includes(self_name) || card.show_to.includes('all') || gameState.phase === "human-win"  || gameState.phase === "thing-win" ? `<div class="card" style="background-image:url(static/${card.image}); background-size: cover;"></div><div class="card-name">${card.name_displayed}</div>
                `: ''}
            </div>
    `).join('');

  

    }
}


const translations = {
    "Ru": {
        'Confirm': 'Подтвердить',
        'Draw Card': 'Взять карту',
        'Play Selected':'Сыграть карту',
        'Discard Selected':'Сбросить карту',
        'React with selected':'Отреагировать картой',
        'Shuffle hand' : 'Перемешать карты',
        'Avoid exchange' : 'Избежать обмена',
        'should draw a card' : 'должен взять карту',
        'You are dead': 'Вас убили',
        'Exchange Selected': 'Обменять карту',
        'select card to play or discard': 'сыграйте или сбросьте карту',
        'select card to exchange': 'выберите карту для обмена'
    },
    // Add more languages as needed
};

function localise(message) {
    logToServer(message);

    // Get the translations for the current language
    const langTranslations = translations[lang] || {};

    // Return the translated message or the original if not found
    return langTranslations[message] || message;
}


function renderActionButtons(is_self, is_current, is_targeted, is_dead, is_tranquilised, is_forced_discards) {
    if(is_dead){
        return `<div>${localise('You are dead')}</div>`;
    }
    else if (is_self){
    return `
        <div class="action-buttons">
        ${gameState.phase === 'draw' && is_current ?
        `<button onclick="handleAction('draw')" >${localise('Draw Card')}</button>` : ''}
        
        ${gameState.phase === 'post-action' && is_targeted && ! is_current ?
            `<button onclick="handleAction('confirm')" >${localise('Confirm')}</button>` : ''}

        ${gameState.phase === 'post-action' && is_targeted && ! is_current ?
            `<button onclick="handleAction('react')" >${localise('React with selected')}</button>` : ''}            

        ${gameState.phase === 'action' && is_current && is_tranquilised <=0 && !is_forced_discards?
        `<button onclick="handleAction('play')" >${localise('Play Selected')}</button>` : ''}
        
        ${gameState.phase === 'action' && is_current ?
        `<button onclick="handleAction('discard')">${localise('Discard Selected')}</button>` : ''}
        
        ${gameState.phase === 'exchange' && (is_targeted || is_current) ? `
            <button onclick="handleAction('exchange')">${localise('Exchange Selected')}</button>
            ` : ''}
        
        ${gameState.phase === 'exchange' && (is_targeted) ? `
            <button onclick="handleAction('react')">${localise('Avoid exchange')}</button>
            ` : ''}
        
        
            ${gameState.phase != 'waiting' && gameState.phase != 'post-action'?
        `<button onclick="handleAction('shuffle')" >${localise('Shuffle hand')}</button>`:''}
        </div>
    `;
            }
    else{
    return '<div>---</div>';} 
}

function getHintText(state) {
    if (!state || !state.players) return '';
    const currentPlayer = state.players[state.current_player];
    
    switch(state.phase) {
        case 'draw':
            return `${currentPlayer.nickname} ${localise('should draw a card')}` + `${state.is_crashed? " Also someone just throwed exception!!!1!111" : ""}`;
        case 'action':
            return `${currentPlayer.nickname} - ${localise('select card to play or discard')}` + `${state.is_crashed? " Also someone just throwed exception!!!1!111" : ""}`;
        case 'exchange':
            return `${state.exchange_comment[0]} x ${state.exchange_comment[1]} - ${localise('select card to exchange')}` + `${state.is_crashed? " Also someone just throwed exception!!!1!111" : ""}`;
        case 'thing-win':
            return 'Game ended, all humans was either infected or killed' + `${state.is_crashed? " Also someone just throwed exception!!!1!111" : ""}`;
        case 'human-win':
            return 'The thing was killed, humans win. (There are still could be someone infected among you).' + `${state.is_crashed? " Also someone just throwed exception!!!1!111" : ""}`
        case 'post-action':
            return `${currentPlayer.nickname} - confirming played action, targeted player could react` + `${state.is_crashed? " Also someone just throwed exception!!!1!111" : ""}`
        default:
            return 'Waiting for players...';handlePlayerClick
    }
}

// User interaction handlers
function handleCardClick(index) {
    selectedCardIndex = index;
    document.querySelectorAll('.card').forEach(c => c.classList.remove('selected'));
    event.target.classList.add('selected');
    //""
    handleAction("card_selection");
    // logToServer(`Selected card index: ${index}`);
}

// Handle player selection
function handlePlayerClick(playerIndex) {
    selectedTarget = playerIndex;
    // logToServer(`Selected player: ${playerIndex}`);
    // Send selection to server (add new message type)
    ws.send(JSON.stringify({
        type: 'action',
        action: 'select_target',
        source: gameState.currentPlayer,
        target: playerIndex
    }));
}


function handleAction(actionType) {
    if ((gameState.phase === 'exchange' || gameState.phase == "action" || actionType === "card_selection") && selectedCardIndex === null) {
        return;
    }

    // Corresponds to websocket_handler's 'action' processing
    ws.send(JSON.stringify({
        type: 'action',
        action: actionType,
        card_idx: selectedCardIndex
    }));
    
    if(!actionType==="card_selection"){
    selectedCardIndex = null;};
}

// Auto-login if URL has name parameter
const urlParams = new URLSearchParams(window.location.search);
const nameParam = urlParams.get('name');
if (nameParam) {
    connectWebSocket(nameParam);
} else {
    document.getElementById('login').style.display = 'block';
}

function login() {
    const nickname = document.getElementById('nickname').value;
    if (nickname) {
        connectWebSocket(nickname);
        document.getElementById('login').style.display = 'none';
    }
}
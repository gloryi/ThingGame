// WebSocket connection handler
let ws = null;
let gameState = null;
let selectedCardIndex = null;
let selectedTarget = null;

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
        return `<div class="card" style="background-image:url(static/${state.discard_top.image}); background-size: cover;">
                <div class="card-name">${state.discard_top.name_displayed}</div></div>`
    }

    // return state.discard_top.face_down ? 'Face down' : state.discard_top.name_displayed;
}

function updateDirectionArrow(state) {
    const arrow = document.getElementById('direction-arrow');
    if (arrow) {
        const rotation = state.direction === 1 ? -1 : 180;
        arrow.style.transform = `translate(-50%, -50%) rotate(${rotation}deg)`;
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
    playerEl.innerHTML = `
    <div class="player-content" ${selected_target === player.nickname ? 'style="background-color:red;"' : ''} ${is_self && player.is_infected ? 'style="background-color:purple;"' : ''} ${is_self && player.is_thing ? 'style="background-color:black;"' : ''}>
        <div class=${player.is_targeted? "player-name" : "player-name-target"}>
        ${player.is_dead ? player.nickname + ' is Dead' : player.nickname}
        ${is_self && player.is_infected ? ' Infected' : ''}
        ${is_self && player.is_thing ? ' Thing' : ''}
        ${player.is_tranquilised>0? ' Tied up' : ''}</div>
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
                <div class="card-name">${card.name_displayed}</div>
            </div>
        `).join('');
    } else {
        // logToServer(hand);
        return player.hand.map((card, idx) => `
            <div class="card ${card.show_to.includes(self_name) || card.show_to.includes('all') ? '' : 'face-down'}">
                ${card.show_to.includes(self_name) || card.show_to.includes('all') ? `<div class="card" style="background-image:url(static/${card.image}); background-size: cover;"></div><div class="card-name">${card.name_displayed}</div>
                `: ''}
            </div>
    `).join('');

  

    }
}

function renderActionButtons(is_self, is_current, is_targeted, is_dead, is_tranquilised, is_forced_discards) {
    if(is_dead){
        return '<div>---</div>';
    }
    else if (is_self){
    return `
        <div class="action-buttons">
        ${gameState.phase === 'draw' && is_current ?
        `<button onclick="handleAction('draw')" >Draw Card</button>` : ''}
        
        ${gameState.phase === 'post-action' && is_targeted && ! is_current ?
            `<button onclick="handleAction('confirm')" >Confirm</button>` : ''}

        ${gameState.phase === 'post-action' && is_targeted && ! is_current ?
            `<button onclick="handleAction('react')" >React with selected</button>` : ''}            

        ${gameState.phase === 'action' && is_current && is_tranquilised <=0 && !is_forced_discards?
        `<button onclick="handleAction('play')" > Play Selected</button>` : ''}
        
        ${gameState.phase === 'action' && is_current ?
        `<button onclick="handleAction('discard')"> Discard Selected</button>` : ''}
        
        ${gameState.phase === 'exchange' && (is_targeted || is_current) ? `
            <button onclick="handleAction('exchange')">Exchange Selected</button>
            ` : ''}
        
        ${gameState.phase === 'exchange' && (is_targeted) ? `
            <button onclick="handleAction('react')">Avoid exchange</button>
            ` : ''}
        
        
            ${gameState.phase != 'waiting' && gameState.phase != 'post-action'?
        `<button onclick="handleAction('shuffle')" >Shuffle hand</button>`:''}
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
            return `${currentPlayer.nickname} should draw a card`;
        case 'action':
            return `${currentPlayer.nickname} - select card to play or discard`;
        case 'exchange':
            return `${currentPlayer.nickname} - select card to exchange`;
        case 'thing-win':
            return 'Game ended, all humans was either infected or killed';
        case 'human-win':
            return 'The thing was killed, humans win. (There are still could be someone infected among you).'
        case 'post-action':
            return `${currentPlayer.nickname} - confirming played action, targeted player could react`
        default:
            return 'Waiting for players...';
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
        logToServer('No card selected for action');
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
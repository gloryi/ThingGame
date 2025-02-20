import aiohttp
from aiohttp import web
import asyncio
import json
import random
import logging
import os

logging.basicConfig(level=logging.INFO)

# TODO hint in central area
# TODO highligt player selection
# TODO sniper rifle and bullet
# TODO bag - exchange buttons for not active player
# TODO gaslighting - покажите соседнему игроку две настоящие и две ненастоящие карты с вашей руки
# TODO слежка - поменяйте цвет рубашки карты, которой обменяетесь. Измененный цвет сохранится до конца игры.
# TODO cancer - занимает слот, не может быть выкинут, может быть обменян, избавиться можно сыграв хирургию.


# Card Class Hierarchy
class Card:
    def __init__(self, card_id, name, description):
        self.id = card_id
        self.name = name
        self.description = description
        self.discard_face_down = True
        print(f"Card {self.id} created")

    def play(self, game, player):
        """To be overridden by subclasses"""
        return ""

    def can_exchange(self, game, player):
        """To be overridden by subclasses"""
        return True


class BasicCard(Card):
    def __init__(self, card_id, name, description, card_def):
        super().__init__(card_id, name, description)

        self.is_exchangable = (
            card_def["is_exchangable"] if "is_exchangable" in card_def else True
        )
        self.is_playable = (
            card_def["is_playable"] if "is_playable" in card_def else False
        )
        self.is_discardable = (
            card_def["is_discardable"] if "is_discardable" in card_def else True
        )
        self.require_player_lock = (
            card_def["require_player_lock"]
            if "require_player_lock" in card_def
            else False
        )
        self.is_reactable = (
            card_def["is_reactable"] if "is_reactable" in card_def else False
        )
        self.neighbours_only = (
            card_def["neighbours_only"] if "neighbours_only" in card_def else False
        )
        self.name_displayed = (
            card_def["name_displayed"] if "name_displayed" in card_def else ""
        )
        self.image = card_def["image"] if "image" in card_def else "default.png"
        self.show_to = []

    def to_dict(self):
        data = {
            "name": self.name,
            "name_displayed": self.name_displayed,
            "description": self.description,
            "id": self.id,
            "image": self.image,
            "discard_face_down": self.discard_face_down,
            "is_exchangable": self.is_exchangable,
            "is_playable": self.is_playable,
            "require_player_lock": self.require_player_lock,
            "neighbours_only": self.neighbours_only,
            "is_discardable": self.is_discardable,
            "is_reactable": self.is_reactable,
            "show_to": self.show_to,
        }
        return data

    def toJSON(self):
        return self.id + " " + self.name + " " + self.description


class Player:
    def __init__(self, nickname, ws):
        self.nickname = nickname
        self.ws = ws
        self.hand = []
        self.is_active = True
        self.is_targeted = False
        self.__selected_card = None
        self.preferred_target = ""  # For future targeting
        self.lock_exchange = False
        self.lock_player = False
        self.is_dead = False
        self.is_tranquilised = 0
        self.is_thing = False
        self.is_infected = False
        self.is_forced_discards = False
        print(f"Player {self.nickname} created")

    def to_dict(self, include_hand=False):
        data = {
            "nickname": self.nickname,
            "hand_size": len(self.hand),
            "is_active": self.is_active,
            "lock_exchange": self.lock_exchange,
            "lock_player": self.lock_player,
            "is_targeted": self.is_targeted,
            "hand": [
                {
                    "name": c.name,
                    "name_displayed": c.name_displayed,
                    "image": c.image,
                    "show_to": c.show_to,
                }
                for c in self.hand
            ],
            "is_dead": self.is_dead,
            "is_active": self.is_active,
            "is_tranquilised": self.is_tranquilised,
            "is_thing": self.is_thing,
            "is_infected": self.is_infected,
            "is_forced_discards": self.is_forced_discards,
        }
        if include_hand:
            data["hand"] = [
                {
                    "name": c.name,
                    "name_displayed": c.name_displayed,
                    "image": c.image,
                    "show_to": c.show_to,
                }
                for c in self.hand
            ]
        return data

    def end_turn_clean(self, soft=True):
        self.lock_exchange = False
        self.lock_player = False
        self.is_targeted = False

    def append_card(self, card, from_deck=True):

        print(f"{self.nickname} appending card {card.name} hand: {len(self.hand)}")

        self.hand.append(card)
        if card.name == "The thing":
            self.is_thing = True
        if card.name == "Infection" and not from_deck and not self.is_thing:
            self.is_infected = True

    def process_turn_effects(self):
        if self.is_tranquilised:
            self.is_tranquilised -= 1

    def could_exchange(self):
        if self.is_tranquilised:
            return False
        return True

    def reveal_cards(self, index=None, target=None):
        logging.info(f"{self.nickname} Revealing cards")
        if index is None and target is None:
            for c in self.hand:
                c.show_to = ["all"]
        elif index is None:
            for c in self.hand:
                c.show_to.append(target)
        else:
            self.hand[index].show_to.append(target)

    # def get_selected_card(self):
    #     if self.__selected_card is None:
    #         self.__selected_card = 0
    #     return self.hand[self.__selected_card]

    def get_hand_card(self, index):
        return self.hand[index]

    def extract_selected_card(self, idx=None):
        if not idx is None:
            return self.hand.pop(idx)
        else:
            return self.hand.pop(self.__selected_card)

    def shuffle_hand(self):
        random.shuffle(self.hand)
        self.end_turn_clean()

    def check_forced_discards(self):
        if len(self.hand) > 4:
            return False
        self.is_forced_discards = False
        return True


class CrossRelations:
    def __init__(self, num_players):
        self.pl_pl_relations = {}
        self.pl_cd_relations = {}

    def add_relation_pl_pl(self, player_1, player_3, is_reflective=False, is_free_selection = True):
        player_1_name = player_1.nickname
        player_2_name = (
            self.pl_pl_relations[player_1_name]
            if player_1_name in self.pl_pl_relations
            else ""
        )
        player_3_name = player_3.nickname

        if not is_free_selection:
            if player_1_name in self.pl_pl_relations and player_3_name in self.pl_pl_relations:
                return

        # p1-# => p2 is None. if p3-* => p3-#; p1->p3 p3->p1,
        # p1-p2. p2-p1. p1-# p2-#. if p3-* p3-#. p1-p3 p3-p1
        # p3==p1 return +
        # p3==p2

        if player_1:
            player_1.is_targeted = False
        if player_3:
            player_3.is_targeted = False

        if player_1_name == player_3_name:
            return

        if player_2_name == player_3_name:
            if player_1_name in self.pl_pl_relations:
                del self.pl_pl_relations[player_1_name]
            if player_3_name in self.pl_pl_relations:
                del self.pl_pl_relations[player_3_name]
            return

        if not player_1_name in self.pl_pl_relations:
            # p2 is None
            if player_3_name in self.pl_pl_relations:
                del self.pl_pl_relations[player_3_name]

        else:
            del self.pl_pl_relations[player_1_name]
            del self.pl_pl_relations[player_2_name]
            if player_3_name in self.pl_pl_relations:
                del self.pl_pl_relations[player_3_name]

        self.pl_pl_relations[player_1_name] = player_3_name
        self.pl_pl_relations[player_3_name] = player_1_name
        player_3.is_targeted = True
        player_1.is_targeted = True
        # player_1.preferred_target = player_3_name

        return

    def get_target(self, player_1):
        player_1_name = player_1.nickname
        if player_1_name in self.pl_pl_relations:
            return self.pl_pl_relations[player_1_name]
        return None

        # TODO OTHER CLICKED WHILE SHOULD NOT, MESSING INITIAL'S SELECTION

    def add_relation_pl_cd(self, player_1, card_index):
        player_1_name = player_1.nickname

        if player_1_name in self.pl_cd_relations:
            del self.pl_cd_relations[player_1_name]

        self.pl_cd_relations[player_1_name] = card_index

    def get_selected_card(self, player_1):
        player_1_name = player_1.nickname

        if player_1_name in self.pl_cd_relations:
            return player_1.get_hand_card(self.pl_cd_relations[player_1_name])
        else:
            self.add_relation_pl_cd(player_1, 0)
            return player_1.get_hand_card(0)

    def exchange_cards(self, player_1, player_2):
        # TODO FOR NOW COUNTING THAT ALLOWED AND CARDS SELECTION CHECKED
        player_1_name = player_1.nickname
        player_2_name = player_2.nickname
        player_1_cd = self.get_selected_card(player_1)
        player_2_cd = self.get_selected_card(player_2)
        player_1_cidx = self.pl_cd_relations[
            player_1_name
        ]  # self.get_selected_card(player_1)
        player_2_cidx = self.pl_cd_relations[
            player_2_name
        ]  # self.get_selected_card(player_2)
        card1, card2 = player_1.extract_selected_card(
            player_1_cidx
        ), player_2.extract_selected_card(player_2_cidx)
        player_1.append_card(card2, from_deck = False)
        player_2.append_card(card1, from_deck = False)

    def extract_selected_card(self, player_1):
        player_1_name = player_1.nickname
        player_1_cd = self.get_selected_card(player_1)
        player_1_cidx = self.pl_cd_relations[player_1_name]  #
        return player_1.extract_selected_card(player_1_cidx)

    def end_turn_clean(self, soft=True):
        if soft:
            self.pl_cd_relations = {}
        self.pl_pl_relations = {}

    def to_dict(self):
        data = {"pl_pl": self.pl_pl_relations, "pl_cd": self.pl_cd_relations}
        return data


class Game:
    def __init__(self, config):
        self.config = config
        self.players = []
        self.deck = []
        self.discard_pile = []
        self.cross = CrossRelations(config["players_per_game"])
        self.post_action_stack = []
        self.current_player_index = 0
        self.direction = 1  # Clockwise
        self.phase = "waiting"
        self.initialize_deck()
        print("Game initialised")

    def initialize_deck(self):
        self.deck = []
        card_id = 0
        for card_def in self.config["cards"]:
            # HARDCODE - changed mind on cards inheritance
            card_class = BasicCard
            # card_class = globals()[card_def['type']]
            for _ in range(card_def["count"]):

                self.deck.append(
                    card_class(
                        f"{card_def['name']}_{card_id}",
                        card_def["name"],
                        card_def["description"],
                        card_def,
                    )
                )
                card_id += 1
        random.shuffle(self.deck)

    def reshuffle_deck(self):
        self.deck = self.discard_pile.copy()
        self.discard_pile = []
        random.shuffle(self.deck)

    def add_player(self, player):
        for p in self.players:
            if p.nickname == player.nickname:
                if not p.is_active:
                    p.is_active = True
                    p.ws = player.ws
                    return True
                return False
        if len(self.players) < self.config["players_per_game"]:
            self.players.append(player)
            print(self.players)
            return True
        return False

    def start_game(self):
        if len(self.players) != self.config["players_per_game"]:
            return False
        for _ in range(4):
            for player in self.players:
                if not self.deck:
                    self.reshuffle_deck()
                if self.config["test_granted"]:
                    granted = self.config["test_granted"].pop()
                    granted_in_deck = [_ for _ in self.deck if _.name == granted]
                    if granted_in_deck:
                        player.append_card(self.deck.pop(self.deck.index(granted_in_deck[0])))
                    else:
                        player.append_card(self.deck.pop())
                else:
                    player.append_card(self.deck.pop())

        self.current_player_index = random.randint(0, len(self.players) - 1)
        self.phase = "draw"
        return True

    def get_next_player_index(self, current_player_index, direction):
        shift = direction
        for i in range(1, len(self.players)):
            shift = direction * i
            index = (self.current_player_index + shift) % len(self.players)
            player = self.players[index]
            if player.is_dead:
                continue
            return index

    def get_by_nickname(self, search_name):
        for player in self.players:
            if player.nickname == search_name:
                return player

    def get_next_player(self, current_player_index, direction):
        next_player_index = self.get_next_player_index(current_player_index, direction)
        # TODO dead players
        current = self.players[current_player_index]
        selected = self.players[next_player_index]
        if current.preferred_target:
            return self.get_by_nickname(current.preferred_target)
        return selected

    # play/discard/react/select_player/select card type
    def is_reaction_valid(self, player, action_type):

        # Probably auto-dismiss incorrect
        if action_type in ["select_target", "card_selection", "confirm", "shuffle"]:
            logging.info(f"{player.nickname} Confirm select target click")
            return True

        if action_type != "react":
            logging.info(f"{player.nickname} Reacting with unkown action")
            return False

        if not self.post_action_stack:
            logging.info("No target for reaction, empty reaction stack")
            return False

        # GET+FIX
        self.cross.get_selected_card(player)

        next_player = self.get_next_player(self.current_player_index, self.direction)
        prev_player = self.get_next_player(
            self.current_player_index, -1 * self.direction
        )
        target_player = self.get_by_nickname(self.cross.get_target(player))

        logging.info("Processing default react option")
        if not self.cross.get_selected_card(player).is_reactable:
            logging.info("Card not reactable")
            logging.info(f"{self.cross.get_selected_card(player).name}")
            logging.info(f"{self.cross.get_selected_card(player).is_playable}")
            return False

        if (
            self.cross.get_selected_card(player).require_player_lock
            and not target_player
        ):
            logging.info(f"{player.nickname} cannot react card - no target is selected")
            return False

        if self.cross.get_selected_card(player).neighbours_only:
            if not target_player.nickname in [
                next_player.nickname,
                prev_player.nickname,
            ]:
                logging.info(f"{player.nickname} cannot react card - neighbours only")
                f"Unknown action {action[action_type]}"
                return False

        return True

    # play/discard/react/select_player/select card type
    def is_action_valid(self, player, action_type):

        if action_type not in ["play", "discard", "select_target", "card_selection"]:
            logging.info("Action type are wrong/unkown")
            return False

        # Probably auto-dismiss incorrect
        if action_type in ["select_target", "card_selection"]:
            logging.info(f"{player.nickname} Confirm select target click")
            return True

        # GET+FIX
        self.cross.get_selected_card(player)

        next_player = self.get_next_player(self.current_player_index, self.direction)
        prev_player = self.get_next_player(
            self.current_player_index, -1 * self.direction
        )
        target_player = self.get_by_nickname(self.cross.get_target(player))

        if action_type == "play":
            logging.info("Processing play option")
            if not self.cross.get_selected_card(player).is_playable:
                logging.info("Card not playable")
                logging.info(f"{self.cross.get_selected_card(player).name}")
                logging.info(f"{self.cross.get_selected_card(player).is_playable}")
                return False

            if (
                self.cross.get_selected_card(player).require_player_lock
                and not target_player
            ):
                logging.info(
                    f"{player.nickname} cannot play card - no target is selected"
                )
                return False

            if self.cross.get_selected_card(player).neighbours_only:
                if not target_player.nickname in [
                    next_player.nickname,
                    prev_player.nickname,
                ]:
                    self.end_turn_error(
                        player, f"{player.nickname} cannot play card - neighbours only"
                    )
                    return False

        if (
            action_type == "discard"
            and not self.cross.get_selected_card(player).is_discardable
        ):
            logging.info("Card not discardable")
            return False

        return True

    def is_game_ended(self):
        # possible end-game processing

        for player in self.players:
            if player.is_thing and player.is_dead:
                return True, "human-win"

        all_infected = True
        for player in self.players:
            if player.is_dead:
                continue
            if player.is_thing:
                continue
            if not player.is_infected:
                all_infected = False

        if all_infected:
            return True, "thing-win"

        return False, "continue"

    def is_basic_exchange_possible(self, player, current_player, next_player):
        # Meaning both players confirming exchange and next for current have current as prev
        player_1, player_2 = current_player, next_player
        if player.nickname == next_player.nickname:
            player_1, player_2 = next_player, current_player

        selected_card = self.cross.get_selected_card(player)

        if (
            selected_card.is_exchangable
            or (selected_card.name == "Infection" and player_1.is_thing)
            or (
                selected_card.name == "Infection"
                and player_1.is_infected
                and player_2.is_thing
            )
        ):
            return True

        else:
            player.lock_exchange = False
            logging.info("Card cannot be exchanged")
            return False

    def set_exchange_phase(self):
        self.phase = "exchange"
        logging.info("Exchange phase initiated")
        self.cross.end_turn_clean(soft=True)
        for p in self.players:
            p.end_turn_clean()

        current_player = self.players[self.current_player_index]
        next_player = self.get_next_player(self.current_player_index, self.direction)

        self.cross.add_relation_pl_pl(current_player, next_player)

        # TODO: ???
        # logging.info(f"Exchange pair {current_player.nickname} x {self.cross.pl_pl_relations[current_player.nickname]}")
        
        
        if (
            not next_player.could_exchange()
            or not current_player.could_exchange()
            ):
            self.current_player_index = self.get_next_player_index(
                self.current_player_index, self.direction
            )
            self.phase = "draw"
            self.end_turn_clean()
            self.post_action_stack = []

    def end_turn_clean(self):
        self.cross.end_turn_clean(soft=False)
        for p in self.players:
            p.end_turn_clean()
            p.preferred_target = ""

    def end_turn_error(self, player, error_msg):
        logging.info(f"[{self.phase}]" + "[" + player.nickname + "]" + error_msg)
        self.cross.end_turn_clean(soft=True)

    async def process_action(self, player, action):

        #No point in calculating anything if it's already ended
        game_ended, end_type = self.is_game_ended()
        if game_ended:
            self.phase = end_type
            return


        current_player = self.players[self.current_player_index]
        next_player = self.get_next_player(self.current_player_index, self.direction)

        if self.phase == "exchange":
            self.cross.add_relation_pl_pl(current_player, next_player, is_free_selection = False)
        prev_player = self.get_next_player(
            self.current_player_index, -1 * self.direction
        )
        is_turn_ended = False

        if self.phase == "post-action":
            if not self.is_reaction_valid(player, action.get("action")):
                self.end_turn_error(player, f"Reaction are not valid")
                return
                # logging.info("Reaction invalid")
                # return

        # Simple, nothing to add
        if action.get("action") == "shuffle":
            player.shuffle_hand()
            return

        if action.get("action") == "select_target":
            target_player = self.players[action.get("target")]
            self.cross.add_relation_pl_pl(player, target_player)
            return

        # Rules of playing the card
        if self.phase == "action":
            if not self.is_action_valid(player, action.get("action")):
                self.end_turn_error(player, "Action are not valid")
                return

        # Probably redundant
        # pl_cd somehow to dict on sending to front
        if action.get("action") == "card_selection":
            self.cross.add_relation_pl_cd(player, action.get("card_idx"))
            player.lock_exchange = False
            return
            # TODO important moment for working for now both versions
            # if player.lock_exchange:
            # player.lock_exchange = False
            # return

        # TODO Add indication || Rules of possibility or disability to exchange
        if self.phase == "exchange" and action.get("action") in ["exchange", "react"]:
            self.cross.add_relation_pl_pl(current_player, next_player, is_free_selection = False)
            # For basic exchange only
            pass

        # MAIN PROCESSING CYCLE
        if self.phase == "draw":
            self.end_turn_clean()
            if player != current_player:
                return

            while(len(current_player.hand)) < 5:
                
                if not self.deck:
                    self.reshuffle_deck()
                current_player.append_card(self.deck.pop())

            current_player.process_turn_effects()
            self.phase = "action"
            return

        elif self.phase == "action":  ########################################### ACTION
            action_type = action["action"]
            print(f"Server {player.nickname} action: {action_type}")
            if player != current_player:
                return

            card_idx = action.get("card_idx")
            if card_idx is None or card_idx >= len(player.hand):
                return

            card = player.hand.pop(card_idx)

            if action["action"] == "play":
                card.discard_face_down = False
                card.show_to = []
                self.discard_pile.append(card)

                # hardcoded
                if card.name == "Signal rocket":
                    self.direction = self.direction * -1
                    self.set_exchange_phase()
                    return

                elif card.name == "Signs":
                    target_player = self.get_by_nickname(self.cross.get_target(player))
                    if (
                        current_player.could_exchange()
                        and target_player.could_exchange()
                    ):
                        current_player.preferred_target = target_player.nickname
                        self.set_exchange_phase()
                        return
                    logging.info(
                        f"Player {current_player.nickname} cannot select exchange with {target_player.nickname}"
                    )
                    return

                elif card.name == "Delirium":
                    player.reveal_cards()
                    # TODO POSSIBLE ERROR
                    # self.phase = 'post-action'
                    self.set_exchange_phase()
                    return

                elif card.name in ["Flamethrower", "Sniper rifle"]:
                    target_player = self.get_by_nickname(self.cross.get_target(player))
                    # TODO allow to use armor
                    self.post_action_stack = [
                        card.name,
                        current_player.nickname,
                        target_player,
                    ]
                    # target_player.is_dead = True
                    self.phase = "post-action"
                    return

                elif card.name == "Blood Sample":
                    target_player = self.get_by_nickname(self.cross.get_target(player))
                    self.post_action_stack = [
                        card.name,
                        current_player.nickname,
                        target_player,
                    ]
                    self.phase = "post-action"
                    return
                elif card.name == "Spying":
                    target_player = self.get_by_nickname(self.cross.get_target(player))
                    self.post_action_stack = [
                        card.name,
                        current_player.nickname,
                        target_player,
                    ]
                    self.phase = "post-action"
                    return

                elif card.name == "Bondage":
                    target_player = self.get_by_nickname(self.cross.get_target(player))
                    # target_player.is_tranquilised = 3
                    self.post_action_stack = [card.name, target_player, 3]
                    self.phase = "post-action"
                    return

                elif card.name == "Oil":
                    if current_player.is_tranquilised > 0:
                        current_player.is_tranquilised = 0
                        self.set_exchange_phase()
                        return

                    # target_player = self.get_by_nickname(self.cross.get_target(player))
                    # target_player.is_tranquilised = 3
                    # self.post_action_stack = [card.name, target_player, 3]
                    # self.phase = 'post-action'
                    logging.info("Cannot play oil not being bondaged")
                    return

                elif card.name == "Swap" or card.name == "Violence":
                    target_player = self.get_by_nickname(self.cross.get_target(player))
                    target_index = self.players.index(target_player)
                    index_1, index_2 = self.current_player_index, target_index
                    self.post_action_stack = [
                        card.name,
                        target_player,
                        target_index,
                        index_1,
                        index_2,
                    ]
                    # self.players[index_1], self.players[index_2] = self.players[index_2], self.players[index_1]
                    # self.current_player_index = index_2
                    self.phase = "post-action"
                    return

                elif card.name == "Last stand":
                    for i in range(3):
                        if not self.deck:
                            self.reshuffle_deck()
                        current_player.append_card(self.deck.pop())
                    current_player.is_forced_discards = True
                    # it's still play phase exchange later
                    return

            elif action["action"] == "discard":

                if player.is_tranquilised > 0 and card.name in [
                    "Oil",
                    "Necronomadd_relation_pl_plicon",
                ]:
                    player.is_tranquilised = 0
                    card.discard_face_down = False
                    card.show_to = []
                    self.discard_pile.append(card)
                    self.cross.end_turn_clean(soft=False)
                    self.set_exchange_phase()
                    return

                else:

                    card.discard_face_down = True
                    card.show_to = []
                    self.discard_pile.append(card)
                    if player.check_forced_discards():
                        self.set_exchange_phase()
                    return

            # elif action['action'] == 'react':
            #     #TODO reactions on played cards
            #     pass
            #     return

            else:
                action_type = action["action"]
                self.end_turn_error(player, f"Unknown action {action[action_type]}")
                return

        elif (
            self.phase == "post-action"
        ):  ########################################### POST_ACTION
            source_card_name = self.post_action_stack[0]
            if action["action"] == "react":

                current_card = self.cross.get_selected_card(player)

                card_idx = action.get("card_idx")
                if card_idx is None or card_idx >= len(player.hand):
                    return

                card = player.hand[card_idx]

                if source_card_name in ["Flamethrower", "Sniper rifle"]:
                    if (
                        source_card_name == "Flamethrower"
                        and current_card.name not in ["Necronomicon", "Armor"]
                    ):
                        self.end_turn_error(
                            player,
                            "Cannot dodge with current card, need necronomicon, armor",
                        )
                        return
                    elif (
                        source_card_name == "Sniper rifle"
                        and current_card.name not in ["Necronomicon", "Armor", "Oil"]
                    ):
                        self.end_turn_error(
                            player,
                            "Cannot dodge with current card, need necronomicon, armor, oil",
                        )
                        return
                    logging.info("Player saved from flamethrower")
                elif source_card_name == "Blood Sample":
                    if current_card.name not in ["Necronomicon"]:
                        self.end_turn_error(
                            player, "Cannot dodge with current card, need necronomicon"
                        )
                        return
                    logging.info("Player saved from blood sample")
                elif source_card_name == "Spying":
                    if current_card.name not in ["Necronomicon"]:
                        self.end_turn_error(
                            player, "Cannot dodge with current card, need necronomicon"
                        )
                        return
                    logging.info("Player saved from blood sample")
                elif source_card_name == "Bondage":
                    if current_card.name not in ["Necronomicon", "Oil"]:
                        self.end_turn_error(
                            player,
                            "Cannot dodge with current card, need necronomicon, armor, oil",
                        )
                        return
                    logging.info("Player saved from bondage")
                elif source_card_name in ["Swap", "Violence"]:
                    if current_card.name not in ["Necronomicon", "Fuck You"]:
                        self.end_turn_error(
                            player,
                            "Cannot dodge with current card, need necronomicon, fuck you",
                        )
                        return
                    logging.info("Player saved from changing places")
                else:
                    self.end_turn_error(
                        player, f"Unkown source for reaction {source_card_name}"
                    )
                    return

                card = self.cross.extract_selected_card(player)
                card.discard_face_down = False
                card.show_to = []
                self.discard_pile.append(card)
                if not self.deck:
                    self.reshuffle_deck()
                player.append_card(self.deck.pop())

                self.set_exchange_phase()
                return
            elif action.get("action") == "confirm":

                if source_card_name in ["Flamethrower", "Sniper rifle"]:
                    # self.post_action_stack = [card.name,current_player.nickname,target_player]
                    # self.post_action_stack = [card.name, target_player]
                    self.post_action_stack[2].is_dead = True
                elif source_card_name == "Bondage":
                    # self.post_action_stack = [card.name, target_player, 3]
                    self.post_action_stack[1].is_tranquilised = 3
                elif source_card_name == "Swap":
                    # self.post_action_stack = [card.name, target_player, target_index, index1, index_2]
                    (
                        self.players[self.post_action_stack[3]],
                        self.players[self.post_action_stack[4]],
                    ) = (
                        self.players[self.post_action_stack[4]],
                        self.players[self.post_action_stack[3]],
                    )
                    self.current_player_index = self.post_action_stack[4]
                elif source_card_name == "Violence":
                    # self.post_action_stack = [card.name, target_player, target_index, index1, index_2]
                    (
                        self.players[self.post_action_stack[3]],
                        self.players[self.post_action_stack[4]],
                    ) = (
                        self.players[self.post_action_stack[4]],
                        self.players[self.post_action_stack[3]],
                    )
                    self.current_player_index = self.post_action_stack[4]
                elif source_card_name == "Blood Sample":
                    # self.post_action_stack = [card.name, current_player.nickname, target_player]
                    for c in self.post_action_stack[2].hand:
                        c.show_to.append(self.post_action_stack[1])
                elif source_card_name == "Spying":
                    # self.post_action_stack = [card.name, current_player.nickname, target_player]
                    self.post_action_stack[2].hand[
                        random.randint(0, len(self.post_action_stack[2].hand) - 1)
                    ].show_to.append(self.post_action_stack[1])
                else:
                    self.end_turn_error(
                        player, f"Unkown source for confirm {source_card_name}"
                    )
                    return

                game_ended, end_type = self.is_game_ended()
                if game_ended:
                    self.phase = end_type
                    return

                logging.info(f"Player {player.nickname} confirmed action agaist it")

                self.post_action_stack = []
                self.set_exchange_phase()
                return
            else:
                action_type = action["action"]
                self.end_turn_error(
                    player, f"Unknown reaction event {action[action_type]}"
                )
                return

        elif self.phase == "exchange": ########################################### EXCHANGE

            if action["action"] == "react":

                card = self.cross.get_selected_card(player)
                if not card.is_reactable:
                    self.end_turn_error(player, f"Card {card.name} is not reactable")
                    return

                if not card.name in ["Fear", "Talk Out", "Necronomicon"]:
                    # TODO Talk Out revealing proposed card
                    self.end_turn_error(
                        player,
                        f"Card {card.name} could be dodged only with fear, talk out, necronomicon",
                    )
                    return

                if card.name == "Talk Out":
                    logging.info(f"{player.nickname} used Talk out")
                    print(self.cross.pl_pl_relations)
                    # if player.nickname in self.cross.pl_pl_relations:
                    if player.nickname in [next_player.nickname, prev_player.nickname]:
                        # paired_player = self.get_by_nickname(self.cross.pl_pl_relations[player.nickname])
                        paired_player = (
                            next_player if player == current_player else current_player
                        )
                        logging.info(f"Counterpart {paired_player.nickname}")
                        next_card = self.cross.get_selected_card(paired_player)
                        if next_card:
                            logging.info(f"Display next {next_card.name}")
                            next_card.show_to.append(player.nickname)

                card = self.cross.extract_selected_card(player)
                card.discard_face_down = False
                card.show_to = []
                self.discard_pile.append(card)
                if not self.deck:
                    self.reshuffle_deck()
                player.append_card(self.deck.pop())

                is_turn_ended = True

            elif action["action"] == "exchange":
                if not player.nickname in [
                    current_player.nickname,
                    next_player.nickname,
                    ]:
                    return
                # if player.preferred_target:
                #     self.cross.add_relation_pl_pl(player, next_player)
                if player.lock_exchange:
                    player.lock_exchange = False
                else:
                    player.lock_exchange = True


                if not self.is_basic_exchange_possible(
                    player, current_player, next_player
                    ):
                    self.end_turn_error(player, "Exchange conditions are not met")
                    return

                    # print(current_player.to_dict)
                    # print(next_player.to_dict())

                current_card, next_card = self.cross.get_selected_card(
                    current_player
                    ), self.cross.get_selected_card(next_player)
                if not current_card is None and not next_card is None:
                    if current_player.lock_exchange and next_player.lock_exchange:
                        self.cross.exchange_cards(current_player, next_player)
                        # a, b = current_player.hand.pop(current_card), next_player.hand.pop(next_card)
                        is_turn_ended = True

            else:
                action_type = action["action"]
                self.end_turn_error(player, f"Unknown action {action[action_type]}")
                return

        if is_turn_ended:
            self.current_player_index = self.get_next_player_index(
                self.current_player_index, self.direction
            )
            self.phase = "draw"
            self.end_turn_clean()
            self.post_action_stack = []


async def broadcast_game_state(game):
    state = {
        "players": [p.to_dict() for p in game.players],
        "current_player": game.current_player_index,
        "deck_size": len(game.deck),
        "discard_top": game.discard_pile[-1].to_dict() if game.discard_pile else None,
        "phase": game.phase,
        "direction": game.direction,
        "cs": game.cross.to_dict(),
    }

    for player in game.players:
        # Use explicit protocol state check instead of truthy websocket check
        if (
            player.is_active
            and hasattr(player, "ws")
            and isinstance(player.ws, web.WebSocketResponse)
            and not player.ws.closed
        ):
            try:
                await player.ws.send_json(
                    {
                        "type": "state_update",
                        "state": state,
                        "hand": [c.to_dict() for c in player.hand],
                        "name": player.nickname,
                    }
                )
            except ConnectionResetError:
                player.is_active = False
                logging.error(f"Connection reset for {player.nickname}")
            except Exception as e:
                logging.error(f"Error sending to {player.nickname}: {str(e)}")


async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    request.app["connections"].add(ws)
    game = request.app["game"] #???
    player = None

    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                data = json.loads(msg.data)
                if data["type"] == "login":
                    nickname = data["nickname"]
                    existing = next(
                        (p for p in game.players if p.nickname == nickname), None
                    )
                    if existing:
                        if existing.is_active:
                            if not existing.ws.closed:
                                await ws.send_json(
                                    {"type": "error", "message": "Name taken"}
                                )
                                continue
                        else:
                            existing.ws = ws
                            existing.is_active = True
                            player = existing
                    else:
                        player = Player(nickname, ws)
                        if not game.add_player(player):
                            await ws.send_json({"type": "error", "message": "Game full"})
                            continue
                    await broadcast_game_state(game)
                    if (
                        len(game.players) == game.config["players_per_game"]
                        and game.phase == "waiting"
                    ):
                        print("Starting game. Players connected.")
                        game.start_game()
                        await broadcast_game_state(game)
                        print(f"Phase: {game.phase}")
                elif data["type"] == "action":
                    await game.process_action(player, data)
                    await broadcast_game_state(game)
                elif data["type"] == "client_log":  # Add this handler
                    logging.info(f"CLIENT LOG: {data['message']}")
    except Exception as e:
        print(f"Crash: {e}")
        await request.app.restart_game()
    finally:
        request.app["connections"].discard(ws)
    return ws        

    if player:
        player.is_active = False
        await broadcast_game_state(game)
    return ws

async def restart_handler(request):
    await request.app.restart_game()
    return web.Response(text="Game restarted!")

async def update_config_handler(request):
    if request.method == "POST":
        data = await request.post()
        new_config_file = data["config_file"].file.read()
        try:
            new_config = json.loads(new_config_file)
            request.app["config"] = new_config
            await request.app.restart_game()
            return web.Response(text="Config updated!")
        except json.JSONDecodeError:
            return web.Response(text="Invalid JSON!", status=400)
    html = """
    <form method="post" enctype="multipart/form-data">
      <input type="file" name="config_file">
      <button>Update Config</button>
    </form>
    """
    return web.Response(text=html, content_type="text/html")


# Add this handler before static routes
async def index_handler(request):
    return web.FileResponse("./static/index.html")

async def restart_game(app):
    for ws in set(app["connections"]):
        await ws.close(code=1001, message=b"Restarting")
    app["connections"].clear()
    app["game"] = Game(app["config"])


async def control_panel_page(request):
    """Regular HTTP handler to serve the control panel HTML"""
    return web.Response(
        text=control_panel_html,
        content_type="text/html"
    )

async def control_panel_ws(request):
    """WebSocket handler for actual communication"""
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    
    async for msg in ws:
        if msg.type == web.WSMsgType.TEXT:
            try:
                data = json.loads(msg.data)
                app = request.app
                
                if data['command'] == 'restart':
                    await app.restart_game()
                    await ws.send_json({"message": "Game restarted!"})
                    
                elif data['command'] == 'upload_config':
                    new_config = json.loads(data['config'])
                    app["config"] = {**app["config"], **new_config}
                    await app.restart_game()
                    await ws.send_json({"message": "Config updated & restarted!"})
                    
                elif data['command'] == 'set_players':
                    count = int(data['count'])
                    if count >= 2:
                        app["config"]["players_per_game"] = count
                        await app.restart_game()
                        await ws.send_json({
                            "message": f"Set to {count} players & restarted!"
                        })
                        
            except Exception as e:
                await ws.send_json({"message": f"Error: {str(e)}"})
    
    return ws

# Updated HTML template with correct WebSocket URL
control_panel_html = """ <html>
    <style>
        body { font-family: sans-serif; margin: 20px; }
        .panel { display: grid; gap: 10px; max-width: 400px; }
        button, input { padding: 8px; }
        #status { color: #666; margin-top: 10px; }
    </style>
    <div class="panel">
        <button onclick="sendCommand('restart')">Restart Game</button>
        
        <div>
            <input type="file" id="configFile" hidden 
                   onchange="readConfig(this)">
            <button onclick="document.getElementById('configFile').click()">
                Upload Config
            </button>
        </div>
        
        <div>
            <label>Players per game: </label>
            <input type="number" id="playersInput" value="2" min="2">
            <button onclick="updatePlayers()">Apply</button>
        </div>
        
        <div id="status"></div>
    </div>
    <script>
        const ws = new WebSocket(`ws://${window.location.host}/control_panel_ws`);
        
        function sendCommand(cmd, data={}) {
            ws.send(JSON.stringify({command: cmd, ...data}));
        }
        
        function readConfig(input) {
            const file = input.files[0];
            const reader = new FileReader();
            reader.onload = () => {
                sendCommand('upload_config', {config: reader.result});
            };
            reader.readAsText(file);
        }
        
        function updatePlayers() {
            const value = parseInt(document.getElementById('playersInput').value);
            if (value >= 2) {
                sendCommand('set_players', {count: value});
            }
        }
        
        ws.onmessage = (event) => {
            const response = JSON.parse(event.data);
            document.getElementById('status').innerHTML = response.message;
        };
    </script>
    </html>
    """



def load_config():
    try:
        with open("config.json", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {"default": "config"}

def main():
    

    if not os.path.exists("static"):
        os.makedirs("static")

    app = web.Application()
    app["connections"] = set()
    app["config"] = load_config()
    app["game"] = Game(app["config"])
    app.restart_game = lambda: restart_game(app)

    # Add explicit index handler
    app.router.add_get("/", index_handler)
    app.router.add_get("/ws", websocket_handler)
    app.router.add_get("/control_panel", control_panel_page)  # Regular HTTP
    app.router.add_get("/control_panel_ws", control_panel_ws)  # WebSocket
    app.router.add_get("/restart", restart_handler)
    app.router.add_route("*", "/update_config", update_config_handler)
    app.router.add_static("/static/", "static")


    web.run_app(app, port=8080)


if __name__ == "__main__":
    main()


#Could become less than 2 cards on hand, somehow agility - exchange selected
#Thing player play button missing +++
#necronomicon not avoiding exchanges
#human player cannot give infection +++
#confirm flamethrower server fault +++


#  File "/opt/render/project/src/.venv/lib/python3.11/site-packages/aiohttp/web_app.py", line 567, in _handle
#     return await handler(request)
#            ^^^^^^^^^^^^^^^^^^^^^^
#   File "/opt/render/project/src/server.py", line 1101, in websocket_handler
#     await game.process_action(player, data)
#   File "/opt/render/project/src/server.py", line 879, in process_action
#     self.post_action_stack[1].is_dead = True
#     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# AttributeError: 'str' object has no attribute 'is_dead' +++++++
"""
Path    addons/source-python/plugins/leetcoin/leetcoin.py
Name    leetcoin
Version 1.0
Author  leetcoin
"""

# ==================================================  ===========================
# >> Imports
# ==================================================  ===========================
import time
import math
import datetime
import threading
from urllib.parse import urlencode
from collections import OrderedDict

try: import re
except ImportError: print ("re Import Error")

try: import hmac
except ImportError: print ("hmac Import Error")

try: import hashlib
except ImportError: print ("hashlib Import Error")

try: import http.client
except ImportError: print ("http.client Import Error")

# We import something called a decorator here which we can use to let Source.Python know that we want to listen to the event
from events import Event
from entities.entity import BaseEntity
from entities.helpers import create_entity
from entities.helpers import spawn_entity

# CEngineServer is used to kick players
from engines.server import engine_server

engine = engine_server

try: import json
except ImportError: print ("Json Import Error")

from listeners.tick import TickRepeat, tick_delays

from messages import SayText2,KeyHintText,HintText

# Import our helper functions
from players.helpers import playerinfo_from_userid, edict_from_userid, index_from_userid, index_from_playerinfo, userid_from_playerinfo
from players.entity import PlayerEntity

from commands.client import ClientCommand, client_command_manager
from commands.say import SayCommand

# Import api client
from .leetcoin_api_client import * 

from colors import RED

from filters.players import PlayerIter

import pprint

# Steam Base ID for Conversion
steamIDBase = 76561197960265728

# instanciate API client
leetcoin_client = LeetCoinAPIClient(url, api_key, shared_secret)

# players requiring activation
pending_activation_player_list = []

# Spectator Betting
bets = {'ct': {}, 't': {}}

# Bounties
bounties = {}

# Create a callback
def my_repeat_callback():
    print(">>>>>>>>>>>>>>>>>>>>>  Repeat")
    
    pop_list = []
    
    for index, pending_activation_player_userid in enumerate(pending_activation_player_list):
        playerinfo = playerinfo_from_userid(pending_activation_player_userid)
        print("my_repeat_callback playerinfo: %s" % playerinfo)
    
        if not playerinfo.get_edict().is_valid():
            print("my_repeat_callback playerinfo edict invalid")
        else:
            steamid = playerinfo.get_networkid_string()
            print("my_repeat_callback player steamid: %s" % steamid)
            
            if not steamid == "BOT":
                print("REAL PLAYER FOUND!")
                steam64 = convertSteamIDToCommunityID(steamid)
                print("steam64: %s" % steam64)
                authorized_active_player = leetcoin_client.authorizeActivatePlayer(steam64, pending_activation_player_userid)
                
            pop_list.append(index)
        
    pop_list.reverse()
    for index_to_remove in pop_list:
        pending_activation_player_list.pop(index_to_remove)
    pass

def submiter_callback():
    print(">>>>>>>>>>>>>>>>>>>>> Repeat Submitter")
    leetcoin_client.repeatingServerUpdate()

# Get the instance of Repeat
my_repeat = TickRepeat(my_repeat_callback)
submit_repeat = TickRepeat(submiter_callback)

# Start the repeat
my_repeat.start(10, 0)
submit_repeat.start(60, 0)

@Event
def game_init(game_event):
    print(">>>>>>>>>>>>>>>>>>>>>  game_init")
    pass
    

@Event
def round_announce_match_start(game_event):
    print(">>>>>>>>>>>>>>>>>>>>>  round_announce_match_start")
    pass   

@Event
def round_start(game_event):
    print("Round Start")

    players = PlayerIter('human')
    for player in players:
        SayText2(message="Commands: bet, bounty").send(player)
    pass
 
@Event
def round_end(game_event):
    print(">>>>>>>>>>>>>>>>>>>  Round End")
    # award winners
    global bets
    winner = game_event.get_int("winner")

    # Check both teams have bets
    if not bets['ct'] or not bets['t']:
        # Refund bets
        for userid, amount in bets['ct'].items():
            SayText2(message="REFUND - " + str(amount) + " SAT - NOT ENOUGH BETS").send(index_from_userid(userid))
            leetcoin_client.requestAward(amount, "REFUND - " + str(amount) + " SAT - NOT ENOUGH BETS", userid)
        for userid, amount in bets['t'].items():
            SayText2(message="REFUND - " + str(amount) + " SAT - NOT ENOUGH BETS").send(index_from_userid(userid))
            leetcoin_client.requestAward(amount, "REFUND - " + str(amount) + " SAT - NOT ENOUGH BETS", userid)
        pass
    else:
        # Calculate pool
        pool_ct = 0
        pool_t = 0
        for userid, amount in bets['ct'].items():
            pool_ct += amount
        for userid, amount in bets['t'].items():
            pool_t += amount
        pool = pool_ct + pool_t

        # 10% for players
        player_cut = pool * 0.1
        remaining = pool - player_cut

        if winner == 2:
            print("T Wins!")
            for userid, amount in bets['t'].items():
                award = remaining / (amount / pool_t)
                leetcoin_client.requestAward(award, "Won bet on T", userid)
                playerinfo = playerinfo_from_userid(userid)
                SayText2(message="You won " + str(award) + " Satoshi").send(index_from_playerinfo(playerinfo))

            if not bets['t']:
                pass
            else:
                # Pay players
                players = PlayerIter('t', 'bot', 'userid')
                for player in players:
                    kickback = player_cut / len(players)
                    leetcoin_client.requestAward(math.ceil(kickback), "Player on winning team", player)
        if winner == 3:
            print("CT Wins!")
            # Pay winners
            for userid, amount in bets['ct'].items():
                award = remaining / (amount / pool_ct)
                leetcoin_client.requestAward(award, "Won bet on CT", userid)
                playerinfo = playerinfo_from_userid(userid)
                SayText2(message="You won " + str(award) + "Satoshi").send(index_from_playerinfo(playerinfo))

            if not bets['ct']:
                pass
            else:
                # Pay players
                players = PlayerIter('ct', 'bot', 'userid')
                for player in players:
                    kickback = player_cut / len(players)
                    leetcoin_client.requestAward(math.ceil(kickback), "Player on winning team", player)
                
    leetcoin_client.repeatingServerUpdate()
    bets = {'ct': {}, 't': {}}
    pass   


@Event
def player_activate(game_event):
    """ this includes bots apparently """
    print("Player Connect")
    userid = game_event.get_int('userid')
    print("userid: %s" % userid)
    
    playerinfo = playerinfo_from_userid(userid)
    print("playerinfo: %s" % playerinfo)
    print("playerinfo userid: %s" % playerinfo.get_userid())
    steam64 = convertSteamIDToCommunityID(playerinfo.get_networkid_string())
    print("playerinfo steamid: %s" % steam64)    
    if steam64:
        leetcoin_client.authorizeActivatePlayer(steam64, userid)

@Event
def player_disconnect(game_event):
    """ this includes bots apparently """
    print("Player Disconnect")
    userid = game_event.get_int('userid')
    print("userid: %s" % userid)
    playerinfo = playerinfo_from_userid(userid)
    print("playerinfo: %s" % playerinfo)
    steamid = playerinfo.get_networkid_string()
    print("player steamid: %s" % steamid)
    
    if not steamid == "BOT":
        print("REAL PLAYER FOUND!")
        steam64 = convertSteamIDToCommunityID(steamid)
        print("steam64: %s" % steam64)
        
        deactivated_result = leetcoin_client.deactivatePlayer(steam64)

    
@Event
def player_death(game_event):
    """ this includes bots apparently """
    print("Player Death")
    # Get the userid from the event
    victim = game_event.get_int('userid')
    attacker = game_event.get_int('attacker')
    print("victim: %s" % victim)
    print("attacker: %s" % attacker)
    
    #victim_edict = edict_from_userid(victim)
    #attacker_edict = edict_from_userid(attacker)
    #print("victim_edict: %s" % victim_edict)
    #print("attacker_edict: %s" % attacker_edict)
    
    # Get the CPlayerInfo instance from the userid
    victimplayerinfo = playerinfo_from_userid(victim)
    attackerplayerinfo = playerinfo_from_userid(attacker)
    print("victimplayerinfo: %s" % victimplayerinfo)
    print("attackerplayerinfo: %s" % attackerplayerinfo)
    # And finally get the player's name 
    victimname = victimplayerinfo.get_name()
    attackername = attackerplayerinfo.get_name()
    print("victimname: %s" % victimname)
    print("attackername: %s" % attackername)
    
    # Get the index of the player
    victimindex = index_from_userid(victim)
    attackerindex = index_from_userid(attacker)
    print("victimindex: %s" % victimindex)
    print("attackerindex: %s" % attackerindex)
    
    print("victim_is_fake_client: %s" % victimplayerinfo.is_fake_client())
    print("attacker_is_fake_client: %s" % attackerplayerinfo.is_fake_client())
    
    victim_steamid = victimplayerinfo.get_networkid_string()
    attacker_steamid = attackerplayerinfo.get_networkid_string()
    
    if not victimplayerinfo.is_fake_client() and not attackerplayerinfo.is_fake_client():
        
        print("victim_steamid: %s" % victim_steamid)
        print("attacker_steamid: %s" % attacker_steamid)
    
        victim_64 = convertSteamIDToCommunityID(victim_steamid)
        attacker_64 = convertSteamIDToCommunityID(attacker_steamid)
        
        kick_player, v_balance, a_balance = leetcoin_client.recordKill(victim_64, attacker_64)
        if v_balance == "noreg":
            SayText2(message="Unregistered kill/death. Win free bitcoin by registering at leetcoin.com! (if you haven't already)").send(victimindex)
            SayText2(message="Unregistered kill/death. Win free bitcoin by registering at leetcoin.com! (if you haven't already)").send(attackerindex)
        vbalance = leetcoin_client.getPlayerBalance(convertSteamIDToCommunityID(victimplayerinfo.get_networkid_string()))
        SayText2(message="Updated " + vbalance + "").send(victimindex)
        if victim_steamid != attacker_steamid:
            # award bounty
            if victimindex in bounties:
                leetcoin_client.requestAward(bounties[victimindex], "BOUNTY", attackerindex)
                SayText2(message="BOUNTY COLLECTED - " + str(bounties[victimindex]) + " SAT").send(attackerindex)
                del bounties[victimindex]
            abalance = leetcoin_client.getPlayerBalance(convertSteamIDToCommunityID(attackerplayerinfo.get_networkid_string()))
            SayText2(message="Updated " + abalance + "").send(attackerindex)    	

    return
  


# Covnert Steam ID to Steam64
def convertSteamIDToCommunityID(steamID):
    print("[1337] convertSteamIDToCommunityID")
    print("steamID: %s" %steamID)
    if steamID == "BOT":
        return False
    steamIDParts = re.split(":", steamID)
    print("steamIDParts: %s" %steamIDParts)
    communityID = int(steamIDParts[2]) * 2
    if steamIDParts[1] == "1":
        communityID += 1
    communityID += steamIDBase
    return communityID
    
                
def doKick(userid, message):
    try:
        print("[1337] [doKick] player: %s" %userid)
    except:
        print("[1337] PLAYER NOT FOUND")
    
    try:
        engine.server_command('kickid %s %s;' % (int(userid), message))
    except:
        print("[1337] KICK FAILURE for user: %s" %userid)
        
def calculate_elo_rank(player_a_rank=1600, player_b_rank=1600, penalize_loser=True):
    winner_rank, loser_rank = player_a_rank, player_b_rank
    rank_diff = winner_rank - loser_rank
    exp = (rank_diff * -1) / 400
    odds = 1 / (1 + math.pow(10, exp))
    if winner_rank < 2100:
        k = 32
    elif winner_rank >= 2100 and winner_rank < 2400:
        k = 24
    else:
        k = 16
    new_winner_rank = round(winner_rank + (k * (1 - odds)))
    if penalize_loser:
        new_rank_diff = new_winner_rank - winner_rank
        new_loser_rank = loser_rank - new_rank_diff
    else:
        new_loser_rank = loser_rank
    if new_loser_rank < 1:
        new_loser_rank = 1
    return (new_winner_rank, new_loser_rank)
    
def tell_all_players(message):
    """ tell all players the message """
    print("tell_all_players - disabled")
    #player_obj_list = leetcoin_client.getPlayerObjList()
    #for player_obj in player_obj_list:
    #    #print("player_obj key: %s" player_obj.get_key())
    #    print(player_obj.get_userid())
    #    
    #    playerinfo = playerinfo_from_userid(player_obj.get_userid())
    #    
    #    i = index_from_playerinfo(playerinfo)
    #    m = HintText(index=i, chat=1, message=message)
    #    m.send(i)

@Event
def other_death(game_event):
    """Fired when a non-player entity is dying."""

    # Make sure the entity was a chicken...
    if game_event.get_string('othertype') != 'chicken':
        return
    print("CHICKEN DIED")
    # Get the attacker's userid...
    userid = game_event.get_int('attacker')
    
    # Make sure the attacker was a player...
    if not userid:
        return
    
# disable chicken award
    # Ask for reward 
#    award = leetcoin_client.requestAward(100, "Chicken killa", userid)
    # Get a PlayerEntity instance of the attacker...
#    attacker = PlayerEntity(index_from_userid(game_event.get_int('attacker')))
    # Display a message...
#    SayText2(message='{0} killed a chicken and had a chance to earn 100 satoshi!'.format(
#        attacker.name)).send()
    

@Event
def player_say(game_event):
    """Fired every time a player is typing something."""
    # Make sure the typed text was "/chicken"...
    if game_event.get_string('text') != '/chicken':
        return

    # Create a chicken entity...
    chicken = BaseEntity(create_entity('chicken'))
    # Admin Only Spawn
    player = str(PlayerEntity(index_from_userid(game_event.get_int('userid'))).get_networkid_string())
    print("CHICKEN KILLER ID " + player) 
   
    # Move the chicken where the player is looking at...
    chicken.origin = PlayerEntity(index_from_userid(game_event.get_int(
        'userid'))).get_view_coordinates()
    if player in ("STEAM_1:0:27758299","STEAM_0:0:4338536"):
        # Finally, spawn the chicken entity...
        spawn_entity(chicken.index)


@SayCommand("balance")
def saycommand_test(playerinfo, teamonly, command):
    #SayText2(message="balance").send(index_from_playerinfo(playerinfo))
    balance = leetcoin_client.getPlayerBalance(convertSteamIDToCommunityID(playerinfo.get_networkid_string()))
    SayText2(message="" + balance + "").send(index_from_playerinfo(playerinfo))

@SayCommand("bet")
def saycommand_bet(playerinfo, teamonly, command):
    global bets
    player = PlayerEntity(index_from_playerinfo(playerinfo))

    params = str(command[1]).split(" ")

    if len(params) == 3:
        team = params[1]
        amount = params[2]

        team_number = player.team
#        team_number = 1 # For Testing

        # Check if player is spectator
        if team_number == 1:

            if int(amount) >= 100:
                if team == "t":
                    SayText2(message="PAYOUT - " + amount + " SAT - T WIN").send(index_from_playerinfo(playerinfo))
                    leetcoin_client.requestAward(-int(amount), "PAYOUT - " + amount + " SAT - T WIN", userid_from_playerinfo(playerinfo))
                    bets['t'][userid_from_playerinfo(playerinfo)] = int(amount)
                if team == "ct":
                    SayText2(message="PAYOUT - " + amount + " SAT - CT WIN").send(index_from_playerinfo(playerinfo))
                    leetcoin_client.requestAward(-int(amount), "PAYOUT - " + amount + " SAT - CT WIN", userid_from_playerinfo(playerinfo))
                    bets['ct'][userid_from_playerinfo(playerinfo)] = int(amount)
            else:
                SayText2(message="Minimum bet is 100 SAT").send(index_from_playerinfo(playerinfo))
        else:
            SayText2(message="Only spectators can bet").send(index_from_playerinfo(playerinfo))
    else:
        SayText2(message="Type: bet <team> <amount>").send(index_from_playerinfo(playerinfo))

@SayCommand("bounty")
def saycommand_bounty(playerinfo, teamonly, command):
    # bounty <player> <amount>
    params = str(command[1]).split(" ")

    if len(params) == 3:
        playername = params[1]
        amount = int(params[2])

        if amount > 0:
            # Lookup player name
            humans = PlayerIter('human', return_types=['name', 'userid'])
            playerFound = False
            for name, userid in humans:
                if name == playername:
                    playerFound = True
                    target = userid

            if playerFound:
                leetcoin_client.requestAward(-int(amount), "BOUNTY", userid_from_playerinfo(playerinfo))
                if userid in bounties:
                    bounties[userid] += amount
                else:
                    bounties[userid] = amount
                SayText2(message="BOUNTY PLACED ON " + playername).send(index_from_playerinfo(playerinfo))
            else:
                SayText2(message="Player not found").send(index_from_playerinfo(playerinfo))
    else:
        SayText2(message="Type: bounty <player> <amount>").send(index_from_playerinfo(playerinfo))
    pass

@SayCommand("duel")
def saycommand_duel(playerinfo, teamonly, command):
    # duel <player> <amount>
    pass

@SayCommand("parlay")
def saycommand_paylay(playerinfo, teamonly, command):
    # parlay <team> <amount> <rounds>
    pass

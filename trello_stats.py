# -*- coding: utf-8 -*-

# stdlib
import datetime, pytz
import math

# 3p
from trello import TrelloClient
from datadog import initialize,api


##### Mandatory credentials

DD_API_KEY = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
DD_APP_KEY = 'yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy'
TRELLO_API_KEY = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
TRELLO_API_SECRET = 'bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb'

BOARD_NAME = '<NAME OF YOUR BOARD AS SEEN ON TRELLO'
DONE_LIST_NAME = '<NAME OF YOUR DONE LIST AS SEEN ON TRELLO'

##### Additional parameters

STALE_CARDS_THRESHOLD_IN_DAYS = 30
COMPLETION_TIME_CARD_AGE_LIMIT = 30 # only cards finished between now and COMPLETION_TIME_CARD_AGE_LIMIT are used for percentiles calculation

SHOULD_CLEANUP = False # percentile calculation takes more and more time as the number of "finished" cards grows. Optionally switch this to True to have old archived cards removed or moved to a separate board
CLEANUP_CARDS_OLDER_THAN_DAYS = 30
MOVE_ARCHIVED_INSTEAD_OF_DELETE = True # False means removing old archive cards
ARCHIVE_BOARD_NAME = '<NAME OF THE OTHER BOARD AS SEEN ON TRELLO>'
ARCHIVE_LIST_NAME = '<NAME OF THE OTHER LIST AS SEEN ON TRELLO>'


# initialize
def initialize_datadog():
    options = {
    'api_key': DD_API_KEY,
    'app_key': DD_APP_KEY
    }
    initialize(**options)

def initialize_trello():
    client = TrelloClient(
        api_key= TRELLO_API_KEY,
        api_secret= TRELLO_API_SECRET
    )
    return client

def get_board(client, name):
    res = None
    for board in client.list_boards():
        if board.name == name:
            res = board
            break
    return res

def get_list(board, name):
    res = None
    for l in board.list_lists():
        if l.name == name:
            res = l
            break
    return res

##################################
## 2 - cards older than 30 days ##
##################################
TIMEZONE = pytz.timezone("Europe/Paris") # you don't necessarily need to change this parameter
UTC_NOW = pytz.utc.localize(datetime.datetime.utcnow())

def card_created_date(card):
    return(TIMEZONE.localize(card.card_created_date))

def card_age(card):
    now = pytz.utc.localize(datetime.datetime.utcnow())
    return(now - card_created_date(card))

##################################
### 3 - Completion time stats  ###  #from archived cards
##################################


_max_duration_since_completion = datetime.timedelta(days = COMPLETION_TIME_CARD_AGE_LIMIT)

def card_done_date(card):
    lm = card.list_movements() 
    # lm = card.list_movements(filter_by_date_interval=(since,until)) 
    if (
        (lm == []) or
        ((lm[0]['destination']['name']) != DONE_LIST_NAME)
        ):
        return None # this is not a card that was moved to Done
    else:
        return(lm[0]['datetime'])

def is_recently_done_card(card):
    dt = card_done_date(card)
    return (
        (dt is not None) and
        ((UTC_NOW - dt) < _max_duration_since_completion)
    )


def move_to_archive_board(cards, client):
    
    archive_board = get_board(client, ARCHIVE_BOARD_NAME)
    archive_list = get_list(archive_board, ARCHIVE_LIST_NAME)

    for c in cards:
        c.change_board(archive_board.id)
        c.change_list(archive_list.id)

def is_old_done_archived_card(card, now=UTC_NOW, max_duration=_max_duration_since_completion):
    dt = card_done_date(card)
    return (
        (dt is not None) and # card is done
        (card.closed) and # archived
        ((now - dt) > max_duration) # old
    )

def card_creation_to_recent_done(card):
    if is_recently_done_card(card):
        return(card_done_date(card) - card_created_date(card))
    else:
        return None

def percentile(data,percent):
    # data.sort() # date is supposed to be already sorted
    k = (len(data) - 1) * percent / 100
    prev_index = math.floor(k)
    next_index = math.ceil(k)

    if prev_index == next_index:
        return data[prev_index]
    else:
        return (data[prev_index] + data[next_index])/2

##################################
##################################
###############   ################
############### M ################
############### A ################
############### I ################
############### N ################
###############   ################
##################################
##################################

def main():
    client = initialize_trello()
    board = get_board(client, BOARD_NAME)
    
    initialize_datadog()

    #### 1- Backlog metric
    
    cards = board.open_cards()
    api.Metric.send(metric='trello.backlog', points=len(cards), tags=[BOARD_NAME])
    print("Backlog Metric Sent to Datadog.")

    #### 2 - Card older than 30 days
    
    cards = board.open_cards()
    old_cards = list(filter(lambda c: card_age(c).days >= STALE_CARDS_THRESHOLD_IN_DAYS, cards))
    api.Metric.send(metric='trello.backlog_stale', points=len(old_cards), tags=[BOARD_NAME])
    print("Stale card count sent to Datadog")

    #### 3 - Mean completion time, for cards "Done" in the last 30 days

    done_cards = [c for c in board.all_cards() if c.get_list().name == DONE_LIST_NAME]

    recent_done_card_completion_time = [card_creation_to_recent_done(c).days for c in done_cards if is_recently_done_card(c)]

    recent_done_card_completion_time.sort()
    perc_list = [50,75,90]
    for p in perc_list:
        api.Metric.send(
            metric='trello.completion_time.%sp' %p,
            points=percentile(recent_done_card_completion_time,p),
            tags=[BOARD_NAME])
    api.Metric.send(
            metric='trello.completion_time.max',
            points=max(recent_done_card_completion_time),
            tags=[BOARD_NAME])
    api.Metric.send(
            metric='trello.completion_time.count',
            points=len(recent_done_card_completion_time),
            tags=[BOARD_NAME])
    print("Percentiles sent!")

    ### (Optional) Remove cards archived for more than 30 days

    if SHOULD_CLEANUP:
        old_archived_cards = [c for c in done_cards if is_old_done_archived_card(c)]

        if MOVE_ARCHIVED_INSTEAD_OF_DELETE:
            move_to_archive_board(old_archived_cards, client)        
            print("%s old archived done cards have been moved to board %s. \n`Old` is defined currently as %s days" 
                %(len(old_archived_cards), ARCHIVE_BOARD_NAME, COMPLETION_TIME_CARD_AGE_LIMIT))
        else:
            for c in old_archived_cards:
                c.delete()
                print("%s old archived done cards have been permanently removed. `Old` is defined currently as %s days" 
                    %(len(old_archived_cards),COMPLETION_TIME_CARD_AGE_LIMIT))


if __name__ == '__main__':
    main()
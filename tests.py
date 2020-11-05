# -*- coding: utf-8 -*-

# std
import unittest
import time

# project
import trello_stats

# 3p
import datadog


DONE_LIST_ID = '5d32ff606307018132efd181'
INBOX_LIST_ID = '5d32ff5fa20dcc57b65b3574' # any other list than 'Done' will do

BOARD_NAME_EXPECTED_ID = '5d32ff5ed0cba81185e0be9f'

class TestDatadogCredentials(unittest.TestCase):
    
    def test_api_credentials(self):
        trello_stats.initialize_datadog()
        
        res = datadog.api.Dashboard.get_all()

        self.assertIn(
            'dashboards',
            res.keys()
        )

class TestAPITrello(unittest.TestCase):
    @classmethod
    def setUpClass(self):
        self.client = trello_stats.initialize_trello() # no error => good creds
        self.board = trello_stats.get_board(self.client, trello_stats.BOARD_NAME)

        self.done_list_id = DONE_LIST_ID
        self.inbox_list_id = INBOX_LIST_ID
        done_list = self.board.get_list(self.done_list_id)
        inbox_list = self.board.get_list(self.inbox_list_id)
        
        title,descr = 'Delete me', '%s' %UTC_NOW
        self.test_card_only_done = done_list.add_card(title,descr)
        
        self.test_card_inbox_then_done = inbox_list.add_card(title,descr)
        self.test_card_inbox_then_done.change_list(self.done_list_id)

        # BEWARE: there is a ~5 min cache for getting all card actions (method leveraged in list_movement) thus need for separate variables
        self.test_card_inbox_then_done_then_inbox = inbox_list.add_card(title,descr)
        self.test_card_inbox_then_done_then_inbox.change_list(self.done_list_id)
        self.test_card_inbox_then_done_then_inbox.change_list(self.inbox_list_id)

        self.test_card_inbox_then_done_then_inbox_then_done = inbox_list.add_card(title,descr)
        self.test_card_inbox_then_done_then_inbox_then_done.change_list(self.done_list_id)
        self.test_card_inbox_then_done_then_inbox_then_done.change_list(self.inbox_list_id)
        self.test_card_inbox_then_done_then_inbox_then_done.change_list(self.done_list_id)

        title1,title2,descr = 'Delete me - old', 'Delete me - young', '%s' %UTC_NOW
        
        self.test_card_done_old = inbox_list.add_card(title1,descr)
        self.test_card_done_old.change_list(self.done_list_id)
        self.test_card_done_old.set_closed(True)

        self.test_card_done_old_then_moved = inbox_list.add_card(title1,descr)
        self.test_card_done_old_then_moved.change_list(self.done_list_id)
        self.test_card_done_old_then_moved.set_closed(True)
        self.test_card_done_old_then_moved.change_list(self.inbox_list_id)
        time.sleep(5)
        self.test_card_done_young = inbox_list.add_card(title2,descr)
        self.test_card_done_young.change_list(self.done_list_id)
        self.test_card_done_young.set_closed(True)

        title3,descr3 = 'Move_me_to_archive_board', '%s' %UTC_NOW

        if CLEANUP_IS_MOVING_TO_OTHER_BOARD:
            self.test_card_to_move = done_list.add_card(title3,descr3)
            self.test_card_to_move_witness = done_list.add_card(title3 + " witness",descr3)

    @classmethod
    def tearDownClass(self):
        self.test_card_only_done.delete()
        self.test_card_inbox_then_done.delete()
        self.test_card_inbox_then_done_then_inbox.delete()
        self.test_card_inbox_then_done_then_inbox_then_done.delete()
        self.test_card_done_old.delete()
        self.test_card_done_young.delete()
        self.test_card_to_move.delete()
        self.test_card_to_move_witness.delete()
        self.test_list.close()

    def test_move_to_archive_board(self):
        
        if CLEANUP_IS_MOVING_TO_OTHER_BOARD:
            # BEWARE: there is a ~5 min cache for getting all card details
            # After moving cards, the board/list ID of the cards remains the same
            # Hence this comparison instead of comparing card details
            
            archive_board = get_board(self.client, archive_board_name)
            archive_list = get_list(archive_board, archive_list_name)

            trello_stats.move_to_archive_board([self.test_card_to_move], self.client)

            self.assertIn(self.test_card_to_move, archive_list.list_cards())
            self.assertNotIn(self.test_card_to_move_witness, archive_list.list_cards())


    def test_GetBoard(self):
        expected_id = BOARD_NAME_EXPECTED_ID

        board_name = BOARD_NAME
        board = trello_stats.get_board(self.client, board_name)
        self.assertEqual(
            board.id,
            expected_id
        )

    def test_card_created_age(self):
        # card created from checklist
        # there is a warning ... but it actually works fine
        # https://github.com/sarumont/py-trello/blob/master/trello/card.py#L479
        card = self.test_card_done_old
        self.assertIsInstance(card_age(card),datetime.timedelta)

        self.assertEqual(card_age(self.test_card_only_done).days, 0)
        self.assertGreater(card_age(self.test_card_only_done).seconds, -1)
        self.assertLess(card_age(self.test_card_only_done).seconds, 300)

    def test_card_done_date(self):  
        # done but was created in the done col with no movements
        self.assertIsNone(card_done_date(self.test_card_only_done))

        # good
        self.assertIsInstance(card_done_date(self.test_card_inbox_then_done),datetime.datetime)
        time1 = trello_stats.card_done_date(self.test_card_inbox_then_done)
        
        # not good
        self.assertIsNone(card_done_date(self.test_card_inbox_then_done_then_inbox))
        
        # good
        self.assertIsInstance(card_done_date(self.test_card_inbox_then_done_then_inbox_then_done),datetime.datetime)
        time2 = trello_stats.card_done_date(self.test_card_inbox_then_done_then_inbox_then_done)

        # increase
        self.assertGreater(time2,time1)

    def test_is_old_done_archived_card(self):
        
        now = pytz.utc.localize(datetime.datetime.utcnow())
        max_duration = datetime.timedelta(
            days = 0,
            seconds = (now - trello_stats.card_done_date(self.test_card_done_old)).seconds - 1,
            milliseconds = 0
            )

        # print("young card age: %s seconds" % card_age(self.test_card_done_young).seconds)
        # import ipdb; ipdb.set_trace()
        self.assertFalse(trello_stats.is_old_done_archived_card(self.test_card_done_young,now=now,max_duration=max_duration)) #not old enough

        self.assertTrue(trello_stats.is_old_done_archived_card(self.test_card_done_old,now=now,max_duration=max_duration)) 
        self.test_card_done_old.set_closed(False)
        self.assertFalse(trello_stats.is_old_done_archived_card(self.test_card_done_old,now=now,max_duration=max_duration)) #not archived
        self.test_card_done_old.set_closed(True)
        self.assertTrue(trello_stats.is_old_done_archived_card(self.test_card_done_old,now=now,max_duration=max_duration)) 

        self.assertFalse(trello_stats.is_old_done_archived_card(self.test_card_done_old_then_moved,now=now,max_duration=max_duration)) # wrong col

    def test_card_creation_to_recent_done(self):
        # done but was created in the done col with no movements
        self.assertIsNone(trello_stats.card_creation_to_recent_done(self.test_card_only_done))

        # done but too old
        # self.assertIsNone(card_creation_to_recent_done(self.old_done_archived_card))

        # good
        self.assertIsInstance(trello_stats.card_creation_to_recent_done(self.test_card_inbox_then_done),datetime.timedelta)
        completion_time1 = trello_stats.card_creation_to_recent_done(self.test_card_inbox_then_done)

        # not done
        self.assertIsNone(trello_stats.card_creation_to_recent_done(self.test_card_inbox_then_done_then_inbox))

        # good again
        self.assertIsInstance(trello_stats.card_creation_to_recent_done(self.test_card_inbox_then_done_then_inbox_then_done),datetime.timedelta)
        completion_time2 = trello_stats.card_creation_to_recent_done(self.test_card_inbox_then_done_then_inbox_then_done)

        # increase
        self.assertGreater(completion_time2, completion_time1)

        # duration sanity check
        self.assertEqual(completion_time1.days, 0)
        
        self.assertGreater(completion_time1.seconds, -1)
        self.assertLess(completion_time1.seconds, 600) # don't tell me tests are longer than 10 min!!

class TestDuration(unittest.TestCase):
    def test_duration(self):
        start = time.time()
        trello_stats.main()
        stop = time.time()
        duration = stop - start
        print("Duration: %d seconds" %duration)

        self.assertLess(int(duration), 300)


if __name__ == '__main__':
    unittest.main()
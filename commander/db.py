import os
import sys
import time
import sqlite3
import asyncio
import traceback


class CommanderDatabase:
    def __init__(self, resp_wait_window, logger):
        self.logger = logger
        self.base_path = "/opt/commander"
        self.db_path = f"{self.base_path}/db"
        self.db_name = "commander.db"
        self.db_fp = os.path.join(self.db_path, self.db_name)
        self.resp_wait_window = resp_wait_window
        self.bulk_response = []
        self.pending = False
        self.db_init()

    def query_wrapper(self, sql_method, sql_type, query, params=()):
        with sqlite3.connect(self.db_fp) as con:
            cur = con.cursor()
            start = time.time()
            try:
                match sql_method:
                    case "executemany":
                        cur.executemany(query, params)
                    case "execute":
                        cur.execute(query, params)
                    case "executescript":
                        cur.executescript(query)
            except sqlite3.Error as er:
                self.logger.core.error(f"SQLite error: {er.args}")
                self.logger.core.error("SQLite exception class is: ", er.__class__)
                self.logger.core.error('SQLite traceback: ')
                exc_type, exc_value, exc_tb = sys.exc_info()
                self.logger.core.error(traceback.format_exception(exc_type, exc_value, exc_tb))
                cur.close()
                con.commit()
            match sql_type:
                case "INSERT" | "UPDATE" | "DELETE":
                    output = cur.rowcount
                case "SELECT":
                    output = [x[0] for x in cur.fetchall()]
                case "CREATE":
                    output = None
            cur.close()
            con.commit()
        self.logger.core.info(f"Query {query}executed in {time.time() - start} seconds")
        return output

    def db_init(self):
        query = ('''
            CREATE TABLE IF NOT EXISTS BotAgents
            (id TEXT PRIMARY KEY, hostname TEXT, address TEXT, online INTEGER, os TEXT);
            CREATE TABLE IF NOT EXISTS CommandHistory
            (count INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, id TEXT, event TEXT, event_detail TEXT, response TEXT,
             exit_code TEXT, FOREIGN KEY (id) REFERENCES BotAgents (id));
            ''')
        self.query_wrapper("executescript", "CREATE", query)
        self.set_all_agents_offline()

    def set_all_agents_offline(self):
        """
        Purpose of this is to ensure that when Commander starts no agent will be online. In theory no agent can be
        online when commander starts because there is a method called in case of shutdown but if a crash occurs and
        that method doesn't execute completely there is a chance that in DB agents are still online when they shouldn't
        :return: None
        """
        query = "UPDATE BotAgents SET online=0 WHERE online=1"
        return self.query_wrapper("execute", "UPDATE", query)

    def add_agent(self, uuid, hostname, address, online, os_type):
        address_socket = f'{address[0]}:{address[1]}'
        bot_agent = [uuid, hostname, address_socket, online, os_type]
        query = "INSERT INTO BotAgents VALUES(?, ?, ?, ?, ?)"
        return self.query_wrapper("execute", "INSERT", query, params=bot_agent)

    def agent_exists(self, uid):
        query = "SELECT EXISTS(SELECT 1 FROM BotAgents WHERE id=?)"
        result = self.query_wrapper("execute", "SELECT", query, params=[uid])
        return result[0]

    def set_agent_online(self, uuid):
        query = "UPDATE BotAgents SET online=? WHERE id=?"
        return self.query_wrapper("execute", "UPDATE", query, params=['1', uuid])

    def set_agent_offline(self, uuid):
        query = "UPDATE BotAgents SET online=? WHERE id=?"
        return self.query_wrapper("execute", "UPDATE", query, params=['0', uuid])

    def get_ids_of_online_agents(self, cmd_filter=""):
        if cmd_filter:
            query = "SELECT id FROM BotAgents WHERE online=? AND os=?"
            return self.query_wrapper("execute", "SELECT", query, params=['1', cmd_filter])
        else:
            query = "SELECT id FROM BotAgents WHERE online=?"
            return self.query_wrapper("execute", "SELECT", query, params=['1'])

    def add_agent_events(self, uuid_list, event, event_detail):
        data = list(zip([time.time(), ] * len(uuid_list), uuid_list, [event, ] * len(uuid_list), [event_detail, ] * len(uuid_list)))
        query = "INSERT INTO CommandHistory(time, id, event, event_detail) VALUES (?, ?, ?, ?)"
        rows_affected = self.query_wrapper("executemany", "INSERT", query, params=data)
        self.logger.core.debug(f"Events have been added for agents. Rows affected: {rows_affected}")

    def add_event_responses(self):
        query = "WITH Tmp(id, event_detail, response_new, exit_code_new) AS (VALUES(?, ?, ?, ?)) " \
                "UPDATE CommandHistory SET response = (SELECT response_new FROM Tmp WHERE CommandHistory.id = Tmp.id " \
                "AND CommandHistory.event_detail = Tmp.event_detail AND CommandHistory.response is null), " \
                "exit_code = (SELECT exit_code_new FROM Tmp WHERE CommandHistory.id = Tmp.id AND " \
                "CommandHistory.event_detail = Tmp.event_detail AND CommandHistory.response is null )" \
                "WHERE id IN (SELECT id FROM Tmp)"
        rows_affected = self.query_wrapper("executemany", "UPDATE", query, params=self.bulk_response)
        self.logger.core.debug(f"Event responses have been added to DB, number of rows updated: {rows_affected}")
        self.bulk_response = []

    async def check_if_pending(self):
        while True:
            await asyncio.sleep(self.resp_wait_window)
            query = 'SELECT EXISTS(SELECT 1 FROM CommandHistory WHERE response is null)'
            if self.bulk_response and self.query_wrapper("execute", "SELECT", query)[0]:
                self.add_event_responses()

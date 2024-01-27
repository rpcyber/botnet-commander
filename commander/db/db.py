import os
import sys
import time
import sqlite3
import asyncio
import logging
import traceback


class CommanderDatabase:
    def __init__(self, base_path, resp_wait_window):
        self.logger = logging.getLogger(__name__+"."+self.__class__.__name__)
        self.base_path = base_path
        self.db_path = f"{self.base_path}/db"
        self.db_name = "commander.db"
        self.db_fp = os.path.join(self.db_path, self.db_name)
        self.resp_wait_window = resp_wait_window
        self.bulk_response = []
        self.db_init()
        self.db_agents = self.get_existent_agents()

    def _start_check_pending_task(self):
        loop = asyncio.get_running_loop()
        self.check_pending_task = loop.create_task(self.check_if_pending())

    def query_wrapper(self, sql_method, sql_type, query, params=()):
        con = sqlite3.connect(database=self.db_fp)
        cur = con.cursor()
        cur.execute("pragma journal_mode = WAL")
        cur.execute("pragma synchronous = normal")
        cur.execute("pragma temp_store = memory")
        cur.execute("pragma mmap_size = 30000000000")
        self.logger.debug(f"Executing query: {query}")
        try:
            match sql_method:
                case "executemany":
                    cur.executemany(query, params)
                case "execute":
                    cur.execute(query, params)
                case "executescript":
                    cur.executescript(query)
        except sqlite3.Error as er:
            self.logger.error(f"SQLite error: {er.args}")
            self.logger.error("SQLite exception class is: ", er.__class__)
            self.logger.error('SQLite traceback: ')
            exc_type, exc_value, exc_tb = sys.exc_info()
            self.logger.error(traceback.format_exception(exc_type, exc_value, exc_tb))
            cur.close()
            con.commit()
        match sql_type:
            case "INSERT" | "UPDATE" | "DELETE":
                cur.fetchall()
                output = cur.rowcount
            case "SELECT":
                output = cur.fetchall()
            case _:
                output = None
        cur.close()
        con.commit()
        return output

    def db_init(self):
        self.logger.info("Initializing Commander database")
        query = ('''
            CREATE TABLE IF NOT EXISTS BotAgents
            (id TEXT PRIMARY KEY, hostname TEXT, address TEXT, os TEXT);
            CREATE TABLE IF NOT EXISTS CommandHistory
            (count INTEGER PRIMARY KEY, time TEXT, id TEXT, event TEXT, event_detail TEXT, response TEXT,
             exit_code TEXT, FOREIGN KEY (id) REFERENCES BotAgents (id));
            ''')
        self.query_wrapper("executescript", "CREATE", query)

    def count_agents(self, op_sys=""):
        if op_sys:
            query = "SELECT COUNT(*) From BotAgents WHERE os = ?"
            output = self.query_wrapper("execute", "SELECT", query, params=(op_sys,))
        else:
            query = f"SELECT COUNT(*) From BotAgents {op_sys}"
            output = self.query_wrapper("execute", "SELECT", query)
        result = [x[0] for x in output]
        return result[0]

    def list_agents(self, op_sys="", entity=""):
        if entity:
            if op_sys:
                query = "SELECT id, hostname, address, os FROM BotAgents WHERE id = ? AND os = ?"
                params = (op_sys, entity)
            else:
                query = "SELECT id, hostname, address, os FROM BotAgents WHERE id = ?"
                params = (entity,)
        else:
            if op_sys:
                query = "SELECT id, hostname, address, os FROM BotAgents WHERE os = ?"
                params = (op_sys,)
            else:
                query = "SELECT id, hostname, address, os FROM BotAgents"
                params = ()
        output = self.query_wrapper("execute", "SELECT", query, params=params)
        columns = ["id", "hostname", "address", "os"]
        result = [dict(zip(columns, row))
                  for row in output]
        return result

    def agents_history(self, uids, reverse, op_sys=""):
        if isinstance(reverse, bool):
            id_list = list(zip(uids))
            sql_script = """
            DROP TABLE IF EXISTS temp;
            CREATE TABLE temp(id TEXT)"""
            self.query_wrapper("executescript", "CREATE", sql_script)
            query = "INSERT INTO temp(id) VALUES(?)"
            self.query_wrapper("executemany", "INSERT", query, params=id_list)
            if reverse:
                if op_sys:
                    query = ("SELECT c.id, c.event, c.event_detail, c.response, c.exit_code FROM CommandHistory as c "
                             "INNER JOIN BotAgents AS b on c.id = b.id WHERE b.os = ? AND "
                             "NOT EXISTS(SELECT null FROM temp WHERE temp.id = c.id)")
                    params = (op_sys,)
                else:
                    query = ("SELECT c.id, c.event, c.event_detail, c.response, c.exit_code FROM CommandHistory as c "
                             "WHERE NOT EXISTS(SELECT null FROM temp WHERE temp.id = c.id)")
                    params = ()
            else:
                if op_sys:
                    query = ("SELECT c.id ,c.event , c.event_detail, c.response, c.exit_code FROM CommandHistory AS c "
                             "INNER JOIN temp ON temp.id = c.id WHERE b.os = ?")
                    params = (op_sys,)
                else:
                    query = ("SELECT c.id ,c.event , c.event_detail, c.response, c.exit_code FROM CommandHistory AS c "
                             "INNER JOIN temp ON temp.id = c.id")
                    params = ()
        else:
            if op_sys:
                query = ("SELECT c.id, c.event, c.event_detail, c.response, c.exit_code FROM CommandHistory AS c"
                         " INNER JOIN BotAgents AS b ON c.id = b.id WHERE b.os = ?")
                params = (op_sys,)
            else:
                query = "SELECT id, event, event_detail, response, exit_code FROM CommandHistory"
                params = ()
        output = self.query_wrapper("execute", "SELECT", query, params=params)
        columns = ["id", "event", "event_detail", "response", "exit_code"]
        result = [dict(zip(columns, row))
                  for row in output]
        return result

    def agent_history(self, uid, op_sys=""):
        if op_sys:
            query = ("SELECT c.id, c.event, c.event_detail, c.response, c.exit_code FROM CommandHistory AS c"
                     " INNER JOIN BotAgents AS b ON c.id = b.id WHERE c.id = ? AND b.os = ?")
            params = (uid, op_sys)
        else:
            query = "SELECT id, event, event_detail, response, exit_code FROM CommandHistory WHERE id = ?"
            params = (uid,)
        output = self.query_wrapper("execute", "SELECT", query, params)
        return output

    def delete_agents(self, entity, op_sys):
        if entity == "*":
            if op_sys:
                ids_to_delete = "SELECT id FROM BotAgents WHERE os = ?"
                query_agents = "DELETE FROM BotAgents WHERE os = ?"
                params = (op_sys,)
            else:
                ids_to_delete = "SELECT id FROM BotAgents"
                query_agents = "DELETE FROM BotAgents"
                params = ()
        else:
            if op_sys:
                ids_to_delete = "SELECT id FROM BotAgents WHERE os = ? AND id = ?"
                query_agents = "DELETE FROM BotAgents WHERE os = ? AND id = ?"
                params = (op_sys, entity)
            else:
                ids_to_delete = "SELECT id FROM BotAgents WHERE id = ?"
                query_agents = "DELETE FROM BotAgents WHERE id = ?"
                params = (entity,)
        query_history = f"DELETE FROM CommandHistory WHERE id IN ({ids_to_delete})"
        deleted_agents = self.query_wrapper("execute", "SELECT", ids_to_delete, params)
        self.query_wrapper("execute", "DELETE", query_history, params)
        self.query_wrapper("execute", "DELETE", query_agents, params)
        cleanup_rogue_agents = '''
        DELETE FROM CommandHistory WHERE id IN
        (SELECT c.id FROM CommandHistory c FULL JOIN BotAgents b ON b.id != c.id)
        '''
        self.query_wrapper("execute", "DELETE", cleanup_rogue_agents)
        result = [dict.fromkeys(item, "success")
                  for item in deleted_agents]
        return result

    def get_last_row_id(self):
        query = "SELECT count FROM CommandHistory ORDER BY count DESC LIMIT 1"
        output = self.query_wrapper("execute", "SELECT", query)
        result = [x[0] for x in output]
        if result:
            return result[0]
        return 0

    def get_existent_agents(self):
        query = "SELECT * FROM BotAgents"
        output = self.query_wrapper("execute", "SELECT", query)
        d = {}
        for bot_agent in output:
            uuid, hostname, address, op_sys = bot_agent
            d[uuid] = {"hostname": hostname, "os": op_sys, "addr": address}
        self.logger.debug("Finished initializing agents json using existing data from DB")
        return d

    def update_agent_addr_and_hostname(self, hostname, address, uid):
        address_socket = f'{address[0]}:{address[1]}'
        query = "UPDATE BotAgents SET (hostname, address) = (?, ?) WHERE id = ?"
        return self.query_wrapper("execute", "UPDATE", query, params=[hostname, address_socket, uid])

    def add_agent(self, uuid, hostname, address, os_type):
        address_socket = f'{address[0]}:{address[1]}'
        bot_agent = [uuid, hostname, address_socket, os_type]
        query = "INSERT INTO BotAgents VALUES(?, ?, ?, ?)"
        return self.query_wrapper("execute", "INSERT", query, params=bot_agent)

    def add_agent_events(self, uuid_list, event, event_detail):
        data = list(zip([time.time(), ] * len(uuid_list), uuid_list, [event, ] * len(uuid_list), [event_detail, ] * len(uuid_list)))
        query = "INSERT INTO CommandHistory(time, id, event, event_detail) VALUES (?, ?, ?, ?)"
        rows_affected = self.query_wrapper("executemany", "INSERT", query, params=data)
        self.logger.debug(f"Events have been added for agents. Rows affected: {rows_affected}")
        self.logger.info(f"There are {rows_affected} pending responses. Starting check if pending task")
        if self.check_pending_task.cancelled():
            self._start_check_pending_task()

    def add_event_responses(self):
        query = "UPDATE CommandHistory SET (response, exit_code) = (?, ?) WHERE count = ?"
        rows_affected = self.query_wrapper("executemany", "UPDATE", query, params=self.bulk_response)
        self.logger.debug(f"Event responses have been added to DB, number of rows updated: {rows_affected}")
        self.bulk_response = []

    async def check_if_pending(self):
        while True:
            await asyncio.sleep(self.resp_wait_window)
            query = 'SELECT EXISTS(SELECT 1 FROM CommandHistory WHERE response is null)'
            output = self.query_wrapper("execute", "SELECT", query)
            self.logger.info(f"Output of query is {output}")
            result = [x[0] for x in output]
            if self.bulk_response and result[0]:
                self.add_event_responses()
            elif result[0]:
                self.logger.debug("There are pending requests waiting for agents response. Task still running")
            else:
                self.logger.debug("There are no pending requests waiting for agents response. Canceling task")
                self.check_pending_task.cancel()

from contextlib import contextmanager
from enum import Enum
from dataclasses import dataclass
from plpy_wrapper import PLPythonWrapperException, RowException
from typing import Union, Any, List, TypeVar

#: internal types of the plpy library that lives in the postgres runtime
PLyResult = TypeVar("PLyResult")
PLyPlan = TypeVar("PLyPlan")


class Row:
    """wrapper around an individual result from the result set or ``TD['new']`` / ``TD['old']``
    :class:`.ResultSet` contains :class:`.Row` objects are returned
    """

    def __init__(self, row_dict: dict):
        """
        :param row_dict: dict containing keys as column names and corresponding values as column values
        """
        self._row_dict = row_dict
        self._set_result_attributes()

    def _set_result_attributes(self):
        """automatically sets each dict key as an attribute and the value as a property
        You shouldn't need to call this directly
        """
        for key, val in self._row_dict.items():
            setattr(self, key, val)

    def __getattr__(self, item):
        return getattr(self, item.lower())

    def __setattr__(self, key: str, value: Any):
        if key == "_row_dict":
            super().__setattr__(key, value)
        elif key in self._row_dict.keys():
            self._row_dict[key] = value
            super().__setattr__(key, value)
        else:
            raise RowException(
                "You cannot set {k} to {v} since {k} is not a column in this Row. Row columns: {ks}".format(
                    k=key, v=value, ks=self._row_dict.keys()
                )
            )

    @property
    def row_dict(self):
        """Get the row dictionary at its currents state. Modifying this dictionary directly won't do anything.
        Instead of modifying directly, modify the attribute on the object itself, like so

        >>> from plpy_wrapper import PLPYWrapper
        >>> plpy_wrapper = PLPYWrapper(globals())
        >>> row = plpy_wrapper.execute('select id,name from customer.contact LIMIT 1')[0]
        >>> row.name = 'new name'
        """
        # returning a new dict to protect from direct modification
        return dict(self._row_dict)

    def __repr__(self):
        return self._row_dict.__repr__()

    def __eq__(self, other: "Row"):
        if type(other) is not Row:
            raise NotImplementedError
        elif other.row_dict == self.row_dict:
            return True
        else:
            return False


class ResultSet:
    """wrapper around result of query in plpy https://www.postgresql.org/docs/11/plpython-database.html"""

    def __init__(self, result_set: PLyResult):
        """
        :param result_set: the type expected is the output of plpy.execute, plpy being postgres's native python package
        """
        self.result_set = result_set
        # nrows is the number of rows processes, not number of rows returned by query. Therefore we can't use that variable to iterate. Instead we
        # iterate thru PLyResult object to get all rows and store that in the object
        self._result_set_rows = [row for row in self.result_set]
        self._iterindex = 0

    def __len__(self):
        return len(self.result_set)

    def __str__(self):
        return self.result_set.__str__()

    def __getitem__(self, index: int):
        return Row(self.result_set[index])

    def __iter__(self):
        return self

    def __next__(self) -> Row:
        """this method is here for iteration support"""
        if self._iterindex < len(self._result_set_rows):
            return_val = Row(self._result_set_rows[self._iterindex])
            self._iterindex += 1
            return return_val
        # restart index so we can iterate again next time
        self._iterindex = 0
        raise StopIteration()

    def __repr__(self):
        return "ResultSet=" + str([row for row in self])

    @property
    def n_rows(self) -> int:
        """Returns the number of rows processed by the command"""
        return self.result_set.nrows()

    @property
    def status(self) -> int:
        """The ``SPI_execute()`` return value"""
        return self.result_set.status()

    @property
    def colnames(self) -> List[str]:
        """returns a list of column names"""
        return self.result_set.colnames()

    @property
    def coltypes(self) -> List[int]:
        """returns list of column type ``OID`` s"""
        return self.result_set.coltypes()

    @property
    def coltypmods(self) -> List[Union[str, int]]:
        """returns a list of type-specific type modifiers for the columns"""
        return self.result_set.coltypmods()


class PLPYWrapper:
    """much documentation is taken from https://www.postgresql.org/docs/11/
    wrapper around plpython plpy library which is included by default in each plpython language procedure/function"""

    class MessagePriority(Enum):
        """all of the possible message priority levels"""

        #: generates a message with a priority of 'debug'
        debug = "debug"

        #: generates a message with a priority of 'log'
        log = "log"

        #: generates a message with a priority of 'info'
        info = "info"

        #: generates a message with a priority of 'notice'
        notice = "notice"

        #: generates a message with a priority of 'warning'
        warning = "warning"

        error = "error"
        """generates a message with a priority of 'error' and raise an exception.

        .. warning::

         This throws an exception, which, if uncaught, propagates out to the calling query, causing the current transaction or subtransaction to be aborted.
        """
        fatal = "fatal"
        """generates a message with a priority of 'fatal' and raise an exception.
        
        .. warning::

         This throws an exception, which, propagates out to the calling query, causing the current transaction or subtransaction to be aborted.
        """

    @dataclass
    class MessageKWARGS:
        """see https://www.postgresql.org/docs/11/plpython-util.html for more information.
        This class represents the available key word arguments to add to a message for more detailed information
        """

        detail: str = None
        hint: str = None
        sqlstate: str = None
        schema_name: str = None
        table_name: str = None
        column_name: str = None
        datatype_name: str = None
        constraint_name: str = None

    _INIT_ERROR = """plpy-wrapper has been initiated outside of the postgres runtime.\
Ensure that you've tried to init this from within a postgres database function with plpython3u\
installed as a language extension."""

    def __init__(self, postgres_runtime_globals: dict):
        """
        :param postgres_runtime_globals: called from within the postgres plpython runtime by using

        >>> from plpy_wrapper import PLPYWrapper
        >>> plpy_wrapper = PLPYWrapper(globals())
        """
        self._postgres_runtime_globals = postgres_runtime_globals
        required_global_vars = ["plpy", "GD", "SD"]
        missing_required_globla_vars = []
        for var in required_global_vars:
            if var not in postgres_runtime_globals:
                missing_required_globla_vars.append(var)
        if missing_required_globla_vars:
            raise PLPythonWrapperException(
                PLPYWrapper._INIT_ERROR + f"Missing var: {missing_required_globla_vars}"
            )

        self.plpy = postgres_runtime_globals["plpy"]
        self.trigger_data = postgres_runtime_globals.get("TD", None)
        # The global dictionary GD is public data, that is available to all Python functions within a session; use with care
        self.global_data = postgres_runtime_globals["GD"]
        # The global dictionary SD is available to store private data between repeated calls to the same function
        self.shared_data = postgres_runtime_globals["SD"]

    def prepare(self, query: str, argtypes: Union[List[str], None] = None) -> PLyPlan:
        """prepares a query plan

        :param query: the SQL string
        :param argtypes: types of args that will be interpolated into the query upon calling :meth:`.execute_plan`
        """
        if argtypes:
            return self.plpy.prepare(query, argtypes)
        else:
            return self.plpy.prepare(query)

    def execute_plan(self, plan: PLyPlan, args: List[Any], row_limit=None) -> ResultSet:
        """see https://www.postgresql.org/docs/11/plpython-database.html for more information"""
        if row_limit:
            return ResultSet(self.plpy.execute(plan, args, row_limit))
        else:
            return ResultSet(self.plpy.execute(plan, args))

    def execute(self, query: str) -> ResultSet:
        """

        :param query: the SQL string to execute
        :return: a ResultSet
        """
        result = self.plpy.execute(query)
        return ResultSet(result)

    def execute_with_transaction(self, query: str) -> ResultSet:
        """see https://www.postgresql.org/docs/11/plpython-transactions.html
        executes a the given query in a transaction and commits. If an exception is encountered, the transaction is rolled back
        :param query: the SQL to run
        :return: the ResultSets
        :raises ```plpy.SPIError``
        """
        try:
            result_set = self.execute(query)
            self.commit()
            return result_set
        except self.plpy.SPIError as e:
            self.rollback()
            raise e

    def __repr__(self):
        return "PLPYWrapper=" + str(self.__dict__)

    @contextmanager
    def subtransaction(self) -> None:
        """
        ghost wrapper around plpy subtransaction.
        Example usage:

        >>> from plpy_wrapper import PLPYWrapper
        >>> wrapper = PLPYWrapper(globals())
        >>> with wrapper.subtransaction():
        >>>  pass
        >>>  #do subtransaction stuff here

        """
        with self.plpy.subtransaction() as subtransaction:
            yield subtransaction

    def commit(self) -> None:
        """commits the current transaction"""
        self.plpy.commit()

    def rollback(self) -> None:
        """rolls back the current transaction"""
        self.plpy.rollback()

    def publish_message(
        self,
        message_priority: MessagePriority,
        message: str,
        message_kwargs: Union[None, MessageKWARGS] = None,
    ) -> None:
        """ magic function that calls the appropriate plpy function based on the message priority given
        instead of writing

        >>> from plpy_wrapper import PLPYWrapper
        >>> wrapper = PLPYWrapper(globals())
        >>> wrapper.plpy.notice("message here",detail='details here')

        we can do something like this. The advantage is mainly in enforcing the kwargs for all of the message types
        But also enables for dynamic message priority setting

        >>> from plpy_wrapper import PLPYWrapper
        >>> wrapper = PLPYWrapper(globals())
        >>> wrapper.publish_message(PLPYWrapper.MessagePriority.notice,"message here",PLPYWrapper.MessageKWARGS(detail="details here"))

        :param message_priority: this determines which plpy message function is called
        :param message: the actual message text
        :param message_kwargs: optional keyword arguments to provide to the message
        """
        ##only send the kwargs that are not none

        kwargs = {}
        if message_kwargs:
            kwargs = {k: v for k, v in message_kwargs.__dict__.items() if v is not None}
        self.plpy.__getattribute__(message_priority.value)(
            message, **kwargs,
        )

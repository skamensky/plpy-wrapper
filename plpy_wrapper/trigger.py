from typing import Union, List
from enum import Enum
from plpy_wrapper import utilities, PLPYWrapper, TriggerException, Row


class TriggerContext:
    """wrapper around the ``TD`` dictionary that is available in trigger contexts
    documentation is taken from https://www.postgresql.org/docs/11/plpython-trigger.html
    This class should only be initialized in a trigger context.
    """

    @utilities.check_nth_arg_is_of_type(2, dict)
    def __init__(self, TD: dict):
        """

        :param TD: the dictionary containing trigger-related values
        """
        self.trigger_data = TD

        # For a row-level trigger this contains the trigger rows depending on the trigger event
        # as instance member as opposed to property in order to persist changes
        self.new = (
            Row(self.trigger_data["new"])
            if "new" in self.trigger_data and self.trigger_data["new"]
            else None
        )

    def __repr__(self):
        return "TriggerContext=" + str(self.__dict__)

    def is_changed(self, field_name) -> bool:
        """utility method to check if a field was changed as a result of the current trigger event (e.g. update)"""

        # if either new or old are none, return true if they are both none and false if one isn't none
        if self.new is None or self.old is None:
            return False
        return self.new.__getattribute__(field_name) != self.old.__getattribute__(
            field_name
        )

    @property
    def event(self) -> str:
        """the trigger event
        as a string. Will be one of: INSERT, UPDATE, DELETE, or TRUNCATE
        """
        return self.trigger_data["event"]

    @property
    def when(self) -> str:
        """when the trigger fired
        is one of BEFORE, AFTER, or INSTEAD OF
        """
        return self.trigger_data["when"]

    @property
    def level(self) -> str:
        """ the trigger execution level
        Can be either  ROW or STATEMENT
        """
        return self.trigger_data["level"]

    @property
    def old(self) -> Union[Row, None]:
        """the state of the row as it was before the trigger fired
        is ``None`` if the event is INSERT or if the trigger execution level is STATEMENT
        """
        if "old" in self.trigger_data and self.trigger_data["old"]:
            return Row(self.trigger_data["old"])
        else:
            return None

    @property
    def name(self) -> str:
        """the name of the running trigger
        """
        return self.trigger_data["name"]

    @property
    def table_name(self) -> str:
        """the name of the table on which the trigger occurred
        """
        return self.trigger_data["table_name"]

    @property
    def table_schema(self) -> str:
        """the schema of the table on which the trigger occurred
        """
        return self.trigger_data["table_schema"]

    @property
    def relid(self) -> int:
        """the ``OID`` of the table on which the trigger occurred"""
        return int(self.trigger_data["relid"])

    @property
    def args(self) -> List[str]:
        """trigger arguments
        If the CREATE TRIGGER command included arguments, they are available in ``TD["args"][0]`` to ``TD["args"][n-1]``.
        """
        return self.trigger_data["args"]


class TriggerReturnValue(Enum):
    """all possible trigger return values
    see https://www.postgresql.org/docs/11/plpython-trigger.html for more detail
    """

    ABORT = "SKIP"
    UNMODIFIED = "OK"
    MODIFIED = "MODIFY"


class Trigger:
    """base trigger class for inheriting. Meant to be inherited on a per table basis"""

    @utilities.check_nth_arg_is_of_type(2, PLPYWrapper)
    def __init__(self, plpy_wrapper: PLPYWrapper):
        """
        :param plpy_wrapper:
        """
        self.plpy_wrapper = plpy_wrapper

        if not self.plpy_wrapper.trigger_data:
            raise TriggerException(
                "{cls} was instantiated outside of a trigger context (no global TD variable found)".format(
                    cls=self.__class__.__name__
                )
            )
        self.trigger_context = TriggerContext(plpy_wrapper.trigger_data)

        # as per https://www.postgresql.org/docs/11/plpython-trigger.html
        # DO NOT CHANGE THIS DIRECTLY. USE _change_trigger_return_val if you want to modify the return value of the trigger. It's there to protect you.
        # This value is the final property used from postgres trigger to return from the trigger
        self.__trigger_return_val: TriggerReturnValue = TriggerReturnValue.UNMODIFIED

    def __repr__(self):
        return "Trigger=" + str(self.__dict__)

    def execute(self):
        """ executes the method corresponding to the trigger event and the trigger "when".
        For example, if when is "BEFORE" and the event is "INSERT", before_insert would run"""
        if (
            self.trigger_context.when == "BEFORE"
            and self.trigger_context.event == "INSERT"
        ):
            self.before_insert()
        if (
            self.trigger_context.when == "BEFORE"
            and self.trigger_context.event == "UPDATE"
        ):
            self.before_update()
        if (
            self.trigger_context.when == "AFTER"
            and self.trigger_context.event == "INSERT"
        ):
            self.after_insert()
        if (
            self.trigger_context.when == "AFTER"
            and self.trigger_context.event == "UPDATE"
        ):
            self.after_update()
        if (
            self.trigger_context.when == "BEFORE"
            and self.trigger_context.event == "DELETE"
        ):
            self.before_delete()

        if (
            self.trigger_context.when == "AFTER"
            and self.trigger_context.event == "DELETE"
        ):
            self.after_delete()

    def before_insert(self):
        '''run when the context is "before" and "insert"'''
        pass

    def after_insert(self):
        '''run when the context is "after" and "insert"'''
        pass

    def before_update(self):
        '''run when the context is "before" and "update"'''
        pass

    def after_update(self):
        '''run when the context is "after" and "update"'''
        pass

    def before_delete(self):
        '''run when the context is "before" and "delete"'''
        pass

    def after_delete(self):
        '''run when the context is "after" and "delete"'''
        pass

    def overwrite_td_new(self):
        """must be called to persist any changes to the trigger row

        .. important::

         call this method when you're done making all changes needed to the row otherwise changes will not be persisted
        """
        self._change_trigger_return_val(TriggerReturnValue.MODIFIED)
        self.plpy_wrapper.trigger_data["new"] = self.trigger_context.new.row_dict

    def abort(self):
        """skips the current event (e.g. insert,update)"""
        self._change_trigger_return_val(TriggerReturnValue.ABORT)

    @property
    def trigger_return_val(self) -> str:
        """returns the trigger return value as a string. This string is what the database trigger needs to return"""
        return self.__trigger_return_val.value

    @utilities.check_nth_arg_is_of_type(2, TriggerReturnValue)
    def _change_trigger_return_val(self, val: TriggerReturnValue):
        """internal method used to set the trigger return value. Includes some sanity checks.
        logic based on https://www.postgresql.org/docs/11/plpython-trigger.html"""

        formatted_exception = TriggerException(
            "The combination of setting value {v} for event: {e}, when: {w}, level: {l} is not supported. See {url} for guidance.".format(
                v=val,
                e=self.trigger_context.event,
                w=self.trigger_context.when,
                l=self.trigger_context.level,
                url=r"https://www.postgresql.org/docs/11/plpython-trigger.html",
            )
        )

        if (
            self.trigger_context.when in ["BEFORE", "INSTEAD OF"]
            and self.trigger_context.level == "ROW"
        ):
            if val in [TriggerReturnValue.UNMODIFIED, TriggerReturnValue.ABORT]:
                self.__trigger_return_val = val
            elif val == TriggerReturnValue.MODIFIED and self.trigger_context.event in [
                "INSERT",
                "UPDATE",
            ]:
                self.__trigger_return_val = val
            else:
                raise formatted_exception
        else:
            raise formatted_exception

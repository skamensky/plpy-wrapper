class TriggerException(Exception):
    """Exception for Trigger class"""

    pass


class UtilityException(Exception):
    """Exception for any function in the utility module"""

    pass


class TypeException(Exception):
    """Custom "type error" exception class.
     When it's important,functions/methods are type checked and this
     exception is thrown when the given type/s do not match the expected
     types
    """

    pass


class PLPythonWrapperException(Exception):
    """Exception for PLPyWrapper"""

    pass


class RowException(Exception):
    """Exception for Row"""

    pass

# plpy-wrapper

[![black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![docs](https://readthedocs.org/projects/plpy-wrapper/badge/?version=latest)](https://plpy-wrapper.readthedocs.io/en/latest/)
[![license](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![pypi](https://badge.fury.io/py/plpy-wrapper.svg)](https://pypi.python.org/pypi/plpy-wrapper/)
[![HitCount](http://hits.dwyl.com/skamensky/plpy-wrapper.svg)](http://hits.dwyl.com/skamensky/plpy-wrapper)

Table of Contents
=================

  * [Terminology](#terminology)
  * [Documentation](#documentation)
  * [Why](#why)
  * [Who should use this?](#who-should-use-this)
  * [Getting Started](#getting-started)
    * [Prerequisites](#prerequisites)
    * [Installation](#installation)
    * [How to use](#how-to-use)
    * [Examples](#examples)
  * [Running the tests](#running-the-tests)
  * [Technologies](#technologies)
  * [Scope of the project](#scope-of-the-project)
  * [Project status](#project-status)
  * [What does plpython3u stand for?](#what-does-plpython3u-stand-for)
  * [TODO](#todo)
  * [A Note on the Development Environment](#a-note-on-the-development-environment)
  * [Further Reading](#further-reading)


Terminology
------------------
* `procedural language` A language in which one can write user-defined functions to access database functionality. The most well known and used in the Postgres world is `PL/pgsql`
* `plpython` - The procedural language plpython which allows python code to run in the Postgres Runtime
* `plpy` The only package that is imported automatically by the Python interpreter embedded in Postgres. This package cannot be imported outside of the Postgres runtime and is used to access Postgres DB functionality such as querying or logging       
* `plpy-wrapper` This package which is a convenience wrapper around plpy


Documentation
------------------
Check out the documentation [here](https://plpy-wrapper.readthedocs.io/)
See the [documentation readme](/docs/README.md) for information on building the documentation.

Why
------------------
The reason I wrote plpy-wrapper was to explore how two of some of my favorite technologies, Postgres, and Python
live and cooperate with one another.

Who should use this?
------------------
It's difficult to justify the use of this in large-scale or security-conscious projects.
The main reason doesn't have anything to do with this package itself, but rather the fact that plpython is an untrusted procedural language - meaning that it can run arbitrary code on your Postgres server.  

As phrased by the [postgres documentation](https://www.postgresql.org/docs/12/plpython.html#docComments):
>PL/Python is only available as an "untrusted" language, meaning it does not offer any way of restricting what users can do in it and is therefore named plpython
 

However, there are some good reasons to use plpython in general and therefore plpy-wrapper as well.
1. You don't want to learn PL/pgSQL but you want to write user-defined functions in Postgres
2. You want to use a python package that already does exactly what you want it to do 
3. You have code you already wrote in Python and want to use it in Postgres
4. You are curious
5. It's a personal server and you have full control over the environment and Python is cool

Getting Started
------------------
#### Prerequisites
Make sure to have Postgres installed on your system.
The Postgres installation should have been compiled with support for plpython as a supported procedural language.
By default most installations come with that baked in. When in doubt you can look in the [dockerfile](/testing/docker/Dockerfile) 
for an example of an environment that this package will definitely run in.

Make sure you've installed plpython as a procedural language in a Postgres session. This package only supports plpython3.
You can do that by running the following code snippet

```postgres-psql
CREATE EXTENSION plpython3u;
```

#### Installation

On the same machine as your Postgres installation, install plpy-wrapper.
However the package gets installed, it must end up in the [Python Path](https://docs.python.org/3.8/using/cmdline.html#envvar-PYTHONPATH).
The way the embedded Python interpreter running inside of the Postgres runtime knows how to access outside Python packages (such as this one), is through the Python Path.
So however you install this package, make sure it ends up on the Python Path.

The two easiest ways to install plpy-wrapper are through pip

Using pypi
```shell script
pip install plpy-wrapper
```

Using github

```shell script
pip install git+https://github.com/skamensky/plpy-wrapper
```

#### How to use
The best way to learn about how to use this package is by reading the [tests](/testing/tests.py).

You can also read some examples below or open an issue if something is unclear.


#### Examples
The trigger creation utility attempts to satisfy a simple use case where you want to create a trigger on every event for a given table. 

This code 
```postgres-sql
DO
$$
from plpy_wrapper import utilities,PLPYWrapper
utilities.create_plpython_triggers(PLPYWrapper(globals()),'customer','contact')
$$ language plpython3u;
```

Results in the following triggers definitions being executed on the `contact` table in the `customer` schema
in order to captures all row events. 

```postgres-psql
create trigger trig_customer_contact_after
    after insert or update or delete
    on contact
    for each row
execute procedure func_customer_contact_trigger_controller();
```
And

```postgres-psql
create trigger trig_customer_contact_before
    before insert or update or delete
    on contact
    for each row
execute procedure func_customer_contact_trigger_controller();
```
The `func_customer_contact_trigger_controller` will autogenerate to the following definition, but could also be changed:

```postgres-psql
create function func_customer_contact_trigger_controller() returns trigger
    language plpython3u
as
$$
from plpy_wrapper import PLPYWrapper,Trigger
class _Contact(Trigger):

    def before_insert(self):
        #put your before insert logic here (or delete this method if you don't want anything to happen before insert)
        pass

    def after_insert(self):
        #put your after insert logic here (or delete this method if you don't want anything to happen after insert)
        pass

    def before_update(self):
        #put your before update logic here (or delete this method if you don't want anything to happen before update)
        pass

    def after_update(self):
        #put your after update logic here (or delete this method if you don't want anything to happen after update)
        pass

    def before_delete(self):
        #put your before delete logic here (or delete this method if you don't want anything to happen before delete)
        pass

    def after_delete(self):
        #put your before after delete logic here (or delete this method if you don't want anything to happen after delete)
        pass

trigger_handler = _Contact(PLPYWrapper(globals()))
#this runs the appropriate method
trigger_handler.execute()
#based on changes you made to the data or events you initiated, this tells postgres to change data, skip the event, etc.
#The return value is only relevant in BEFORE/INSTEAD OF triggers
return trigger_handler.trigger_return_val
$$;
```

Running the tests
------------------
You can read more about how tests work and how to run them in the [tests readme](/testing/README.md).

Technologies
------------------
* Python
* Postgres

Scope of the project
------------------
As of now, plpy-wrapper is a simple wrapper around plpy. The main utilities someone could find in it
are:
1. Simplifying writing triggers in plpython and avoiding some common pitfalls (for example by using the autogenerated trigger above you don't need to worry about persisting changes you've made to the row in the trigger by returning the string 'OK'. This package does that for you).
2. Performing a specific action before or after every function call to plpy (sort of how you would use decorators)

However, I am open to contributions and extending the scope of this package to be a more full-fledged wrapper as long as the changes are useful enough to a broad audience. 

Project status
------------------ 
Whatever comes before Alpha. Given that this project was written mainly for fun and curiosity I can see it never being touched again.

What does plpython3u stand for?
------------------
The `pl` part of plpython stands for procedural language

The `python` part stands for Python ♥

The `3` part stands for python 3.

The `u` part stands for untrusted (you can what untrusted means in the [Who should use this?](#who-should-use-this) section).

TODO
------------------
* Finish writing tests
* Add CI
* Create coverage badge and improve coverage

A Note on the Development Environment
------------------
This package was developed on Windows and therefore bash scripts are batch scripts and some file paths may be in Windows formats. 

Sorry! I'm still in the process of transferring my development environment to WSL.

Further Reading
------------------
https://www.postgresql.org/docs/current/plpython.html

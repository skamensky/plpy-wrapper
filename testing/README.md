# Testing

Table of Contents
=================

  * [Summary of the Test Lifecycle](#summary-of-the-test-lifecycle)
  * [Notes on Testing Strategies](#notes-on-testing-strategies)
     * [The Problem](#the-problem)
     * [Potential Solutions](#potential-solutions)
  * [How Testing the Trigger Framework Works](#how-testing-the-trigger-framework-works)
  
Summary of the Test Lifecycle
-----------
The tests are run by executing [docker_run.bat](/testing/docker/docker_run.bat). 
To run the tests simply execute `docker_run.bat` on a windows machine with python installed (or with a python virtualenv activated) **where the docker directory is your current working directory**.

The windows batch script will do the following:

1. Build the docker image from the Dockerfile
2. Create a docker volume for persistence in the scenario that you want to do debugging on the DB
3. Run a docker container using the image built in step 1
4. Wait until the DB inside the container is running (to avoid race conditions)
5. Setup the DB schema using the [setup_db.sql](/testing/docker/setup_db.sql) file
6. Execute the tests by running the [run_tests.sql](/testing/docker/run_tests.sql) file
    1. The `run_tests.sql` script pipes all test data including unittest results and coverage data to stdout and stderr
7. Write unittest and coverage data from stdout/stderr to the host machine
8. Remove the docker container 


Notes on Testing Strategies
-------------------------

### The Problem
We need to test methods that are generally only invoked from DB process when running a trigger in a postgres session. 
I wanted to actually test the runtime and additionally I wanted to collect line coverage data.

### Potential Solutions
1) Run a db `DO` clause in the test to get trigger context, save the plpywrapper as a pickled file, retrieve pickled file as in-memory object.
    1) I tried this and got an attribute error in pickle dump since the plpy package is somehow saved as a builtin by the postgres runtime and is not importable from outside the runtime. This most likely has to do with the fact that it is a C-extension library.
2) Create each test as a trigger function and have the tests called from an actual trigger
    1) This would have meant separating all unit tests into individual function calls and I still would have had to deal with coverage. I found a better solution before I tried this. 
3) Use shared memory to save the plpy object in the testing process. Or serialize the data of the trigger handler/context 
    1) I tried this. The problem was that shared memory + manager proxies only allow primitive objects (unless you define the structure of the object which is not something I wanted to maintain) 
5) Seralize only what we're missing, (the `TD`) and manually create a new PLPYWrapper object.
    1) **This is the solution I went with. See the [How Testing the Trigger Framework Works](#how-testing-the-trigger-framework-works) section for additional information**

*NOTE*:

I don't know how it does it, but coverage.py picks up on lines of code executed by calls to plpy functions executed in transactions :)

How Testing the Trigger Framework Works
----------------
This section describes what [run_tests.sql](/testing/docker/run_tests.sql) does and how it interacts with [tests.py](/testing/tests.py).

The PLPYWrapper class expects the python globals dictionary of the plpython runtime.
By receiving the globals it gets access to the `SD` and `GD` dictionaries, the `plpy` module, and in a trigger context, the `TD` dictionary. 

The tests are run from a postgres `DO` statement in the plpython language.
A wrapper is instantiated and injected into the `tests.py` module as the `PLPY_WRAPPER` variable.

The `PLPY_WRAPPER` variable is re-used throughout all the tests, database setup, and teardown.

However, for tests that require the `TD` variable to be populated, this isn't enough since `PLPY_WRAPPER` came from the globals within the `DO` statement which is not a trigger context and therefore does not contain the `TD` variable.

The solution used, as stated above, is for each trigger to save the `TD` variable as a row in a table created specifically for this purpose, the `trigger_run_log` table.
After the trigger has run this table is queried and the `TD` data is injected into a new `plpy_wrapper` object which is contains all the data from the `PLPY_WRAPPER` variable plus the newly received `TD` dictionary. You can see this happening in the [execute_sql_and_get_trigger_obj](https://github.com/skamensky/plpy-wrapper/blob/d2c02f196c9a179432c3cee9f6b6b61279f1f40c/testing/tests.py#L110) method.
The tests receive a `plpy_wrapper` object that for all intents and purposes is exactly what the `plyp_wrapper` object would appear as in a trigger context.
This allows for accurate unit testing and better code coverage.

"""TESTS ARE NOT MEANT TO BE RUN OUTSIDE OF THE POSTGRES RUNTIME. USE THE DOCKER SCRIPT TO RUN TESTS"""
import json
import sys
import unittest
from pathlib import Path


from plpy_wrapper import PLPYWrapper
from plpy_wrapper import (
    utilities,
    Trigger,
    Row,
    TriggerException,
    TriggerReturnValue,
)

"""
https://docs.python.org/3/library/unittest.html
"""

#:doc set externall from the run_tests.sql
PLPY_WRAPPER: PLPYWrapper = None


class TriggerTestException(Exception):
    pass


class TestBase(unittest.TestCase):
    def setUp(self) -> None:
        self.subtrans = PLPY_WRAPPER.plpy.subtransaction()
        self.subtrans.enter()

    def tearDown(self) -> None:
        # explicit exception raising here in order to invoke plpy's subtransaction rollback functionality
        try:
            raise TriggerTestException()
        except TriggerTestException:
            self.subtrans.exit(*sys.exc_info())


class TriggerTests(TestBase):
    """Tests for code in trigger.py module"""

    COMPANY_ID = 1
    COMPANY_NAME = "Phantom Zone"
    DELETE_INITIAL_COMPANY_SQL = f"delete from customer.company where id={COMPANY_ID};"
    UPDATE_INITIAL_COMPANY_SQL = (
        f"update customer.company SET name='Mr. Fantastic' where id={COMPANY_ID};"
    )
    INSERT_NEW_COMPANY_SQL = (
        "insert into customer.company (id,name) values (2,'HULK INC');"
    )

    TRIGGER_RUN_BEFORE_INSERT_MESSAGE = "Hello from before_insert!"
    TRIGGER_RUN_AFTER_INSERT_MESSAGE = "Hello from after_insert!"
    TRIGGER_RUN_BEFORE_UPDATE_MESSAGE = "Hello from before_update!"
    TRIGGER_RUN_AFTER_UPDATE_MESSAGE = "Hello from after_update!"
    TRIGGER_RUN_BEFORE_DELETE_MESSAGE = "Hello from before_delete!"
    TRIGGER_RUN_AFTER_DELETE_MESSAGE = "Hello from after_delete!"

    @classmethod
    def create_triggers(
        cls,
        before_insert_body=f"self.insert_into_trigger_log('{TRIGGER_RUN_BEFORE_INSERT_MESSAGE}')",
        after_insert_body=f"self.insert_into_trigger_log('{TRIGGER_RUN_AFTER_INSERT_MESSAGE}')",
        before_update_body=f"self.insert_into_trigger_log('{TRIGGER_RUN_BEFORE_UPDATE_MESSAGE}')",
        after_update_body=f"self.insert_into_trigger_log('{TRIGGER_RUN_AFTER_UPDATE_MESSAGE}')",
        before_delete_body=f"self.insert_into_trigger_log('{TRIGGER_RUN_BEFORE_DELETE_MESSAGE}')",
        after_delete_body=f"self.insert_into_trigger_log('{TRIGGER_RUN_AFTER_DELETE_MESSAGE}')",
        schema="customer",
        table="company",
        func_name='"customer".func_customer_company_trigger_controller',
        trigger_template_path=Path(
            Path(__file__).parent, "trigger_process_template_trigger_test.txt"
        ),
    ):
        utilities.create_plpython_triggers(
            PLPY_WRAPPER,
            schema,
            table,
            None,
            open(trigger_template_path)
            .read()
            .format(
                trigger_template_path=trigger_template_path,
                before_insert_body=before_insert_body,
                after_insert_body=after_insert_body,
                before_update_body=before_update_body,
                after_update_body=after_update_body,
                before_delete_body=before_delete_body,
                after_delete_body=after_delete_body,
                func_name=func_name,
            ),
        )

    def get_trigger_run_log(self, when, event):
        # gets the latest trigger log, ignoring the initial company that was inserted at the beginning of the test
        return PLPY_WRAPPER.execute(
            f"""
            select * FROM "logging".trigger_run_log 
            WHERE 
                TD_data->>'when'='{when}' AND
                TD_data->>'event'='{event}' AND
                NOT (TD_data->>'event'='INSERT' AND (Td_data->>'new')::json->>'id'='{self.COMPANY_ID}' AND (Td_data->>'name'='trig_customer_company_before'))
            ORDER BY created_at DESC LIMIT 1
            """
        )[0]

    def execute_sql_and_get_trigger_obj(self, sql_command, when, event):
        PLPY_WRAPPER.execute(sql_command)
        plpy_globals = dict(PLPY_WRAPPER._postgres_runtime_globals)
        TD_data = self.get_trigger_run_log(when, event).TD_data
        plpy_globals["TD"] = json.loads(TD_data)
        return Trigger(PLPYWrapper(plpy_globals))

    def execute_sql_and_get_trigger_obj_before_insert(self, sql_command):
        return self.execute_sql_and_get_trigger_obj(sql_command, "BEFORE", "INSERT")

    def execute_sql_and_get_trigger_obj_after_insert(self, sql_command):
        return self.execute_sql_and_get_trigger_obj(sql_command, "AFTER", "INSERT")

    def execute_sql_and_get_trigger_obj_before_update(self, sql_command):
        return self.execute_sql_and_get_trigger_obj(sql_command, "BEFORE", "UPDATE")

    def execute_sql_and_get_trigger_obj_after_update(self, sql_command):
        return self.execute_sql_and_get_trigger_obj(sql_command, "AFTER", "UPDATE")

    def execute_sql_and_get_trigger_obj_before_delete(self, sql_command):
        return self.execute_sql_and_get_trigger_obj(sql_command, "BEFORE", "DELETE")

    def execute_sql_and_get_trigger_obj_after_delete(self, sql_command):
        return self.execute_sql_and_get_trigger_obj(sql_command, "AFTER", "DELETE")

    def setUp(self) -> None:

        super().setUp()
        TriggerTests.create_triggers()
        PLPY_WRAPPER.execute(
            f"INSERT INTO customer.company (id, name) VALUES(1,'{self.COMPANY_NAME}') ON CONFLICT DO NOTHING"
        )

    def test_is_changed_returns_true_if_changed(self):
        self.assertTrue(
            self.execute_sql_and_get_trigger_obj_before_update(
                self.UPDATE_INITIAL_COMPANY_SQL
            ).trigger_context.is_changed("name")
        )

    def test_is_changed_returns_false_during_insert(self):
        """since old will be none"""
        self.assertFalse(
            self.execute_sql_and_get_trigger_obj_before_insert(
                self.INSERT_NEW_COMPANY_SQL
            ).trigger_context.is_changed("name")
        )

    def test_is_changed_returns_false_during_delete(self):
        """since new will be none"""
        self.assertFalse(
            self.execute_sql_and_get_trigger_obj_before_delete(
                self.DELETE_INITIAL_COMPANY_SQL
            ).trigger_context.is_changed("name")
        )

    def test_is_changed_throws_getattribute_error_when_field_is_not_present_and_new_and_old_are_not_none(
        self,
    ):
        with self.assertRaises(AttributeError):
            self.execute_sql_and_get_trigger_obj_before_update(
                self.UPDATE_INITIAL_COMPANY_SQL
            ).trigger_context.is_changed("names")

    def test_event_is_insert_during_insert(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_insert(
            self.INSERT_NEW_COMPANY_SQL
        )
        self.assertTrue(trigger_handler.trigger_context.event == "INSERT")

    def test_event_is_update_during_update(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_update(
            self.UPDATE_INITIAL_COMPANY_SQL
        )
        self.assertTrue(trigger_handler.trigger_context.event == "UPDATE")

    def test_event_is_delete_during_delete(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_delete(
            self.DELETE_INITIAL_COMPANY_SQL
        )
        self.assertTrue(trigger_handler.trigger_context.event == "DELETE")

    """
    #NOT SUPPORTED
    def test_event_is_truncate_during_truncate(self):
        pass
    """

    def test_when_is_before_during_before(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_delete(
            self.DELETE_INITIAL_COMPANY_SQL
        )
        self.assertTrue(trigger_handler.trigger_context.when == "BEFORE")

    def test_when_is_after_during_after(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_after_delete(
            self.DELETE_INITIAL_COMPANY_SQL
        )
        self.assertTrue(trigger_handler.trigger_context.when == "AFTER")

    """
    #NOT SUPPORTED
    def test_when_is_insteadof_during_insteadof(self):
        pass
    """

    def test_level_is_row_during_row_trigger(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_after_delete(
            self.DELETE_INITIAL_COMPANY_SQL
        )
        self.assertTrue(trigger_handler.trigger_context.level == "ROW")

    """
    #NOT SUPPORTED
    def test_level_is_statement_during_row_statement_trigger(self):
        pass
    """

    def test_old_returns_old_during_before_update(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_update(
            self.UPDATE_INITIAL_COMPANY_SQL
        )

        self.assertDictEqual(
            trigger_handler.trigger_context.old.row_dict,
            {"id": 1, "name": self.COMPANY_NAME},
        )

    def test_old_returns_old_during_after_update(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_after_update(
            self.UPDATE_INITIAL_COMPANY_SQL
        )

        self.assertDictEqual(
            trigger_handler.trigger_context.old.row_dict,
            {"id": 1, "name": self.COMPANY_NAME},
        )

    def test_old_returns_old_during_before_delete(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_delete(
            self.DELETE_INITIAL_COMPANY_SQL
        )

        self.assertDictEqual(
            trigger_handler.trigger_context.old.row_dict,
            {"id": 1, "name": self.COMPANY_NAME},
        )

    def test_old_returns_old_during_after_delete(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_after_delete(
            self.DELETE_INITIAL_COMPANY_SQL
        )

        self.assertDictEqual(
            trigger_handler.trigger_context.old.row_dict,
            {"id": 1, "name": self.COMPANY_NAME},
        )

    def test_old_returns_none_during_before_insert(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_insert(
            self.INSERT_NEW_COMPANY_SQL
        )

        self.assertIs(trigger_handler.trigger_context.old, None)

    def test_old_returns_none_during_after_insert(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_after_insert(
            self.INSERT_NEW_COMPANY_SQL
        )

        self.assertIs(trigger_handler.trigger_context.old, None)

    def test_new_is_rowtype_during_before_insert(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_insert(
            self.INSERT_NEW_COMPANY_SQL
        )

        self.assertIs(type(trigger_handler.trigger_context.new), Row)

    def test_new_is_rowtype_during_after_insert(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_after_insert(
            self.INSERT_NEW_COMPANY_SQL
        )

        self.assertIs(type(trigger_handler.trigger_context.new), Row)

    def test_new_is_rowtype_during_before_update(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_update(
            self.UPDATE_INITIAL_COMPANY_SQL
        )

        self.assertIs(type(trigger_handler.trigger_context.new), Row)

    def test_new_is_rowtype_during_after_update(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_after_update(
            self.UPDATE_INITIAL_COMPANY_SQL
        )

        self.assertIs(type(trigger_handler.trigger_context.new), Row)

    def test_new_is_none_during_before_delete(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_delete(
            self.DELETE_INITIAL_COMPANY_SQL
        )

        self.assertIs(trigger_handler.trigger_context.new, None)

    def test_new_is_none_during_after_delete(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_after_delete(
            self.DELETE_INITIAL_COMPANY_SQL
        )

        self.assertIs(trigger_handler.trigger_context.new, None)

    def test_name_returns_triggername(self):

        trigger_handler = self.execute_sql_and_get_trigger_obj_before_delete(
            self.DELETE_INITIAL_COMPANY_SQL
        )
        self.assertEqual(
            trigger_handler.trigger_context.name, "trig_customer_company_before",
        )

    def test_table_schema_returns_schema_name(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_delete(
            self.DELETE_INITIAL_COMPANY_SQL
        )
        self.assertEqual(
            trigger_handler.trigger_context.table_schema, "customer",
        )

    def test_table_name_returns_table_name(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_delete(
            self.DELETE_INITIAL_COMPANY_SQL
        )
        self.assertEqual(
            trigger_handler.trigger_context.table_name, "company",
        )

    def test_relid_returns_relid(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_delete(
            self.DELETE_INITIAL_COMPANY_SQL
        )

        self.assertEqual(
            PLPY_WRAPPER.execute(
                "SELECT tgrelid from pg_trigger where tgname='trig_customer_company_before';"
            )[0].tgrelid,
            trigger_handler.trigger_context.relid,
        )

    def test_trigger_with_args_returns_args(self):
        PLPY_WRAPPER.execute(
            """
            create function "customer".func_customer_contact_trigger_controller() returns trigger as 
                $$
                    import json
                    plan = plpy.prepare('''INSERT into "logging".trigger_run_log (TD_data,add_data) values ($1,$2)''',['JSON','text'])
                    plpy.execute(plan,[json.dumps(TD),"Customer contact trigger saying what's going on!"])
                $$
            language plpython3u;"""
        )

        arg = "arghhh!"

        PLPY_WRAPPER.execute(
            f"""create trigger trig_customer_contact_before before update or insert or delete on customer.contact for each row
                execute procedure "customer".func_customer_contact_trigger_controller('{arg}');
            """
        )
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_insert(
            f"insert into customer.contact (first_name,last_name,company_id) values ('Jason','Todd',{self.COMPANY_ID})"
        )

        self.assertEqual(trigger_handler.trigger_context.args, [arg])

    def test_trigger_without_args_returns_none(self):
        """default trigger has no args"""
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_delete(
            self.DELETE_INITIAL_COMPANY_SQL
        )
        self.assertIs(
            trigger_handler.trigger_context.args, None,
        )

    def test_instantiating_trigger_without_trigger_data_fails(self):
        """PLPY_WRAPPER has no trigger data since its source is an anonymous DO block"""
        with self.assertRaises(TriggerException):
            Trigger(PLPY_WRAPPER)

    def test_before_insert_runs(self):
        PLPY_WRAPPER.execute(self.INSERT_NEW_COMPANY_SQL)
        self.assertEqual(
            self.get_trigger_run_log("BEFORE", "INSERT").add_data,
            self.TRIGGER_RUN_BEFORE_INSERT_MESSAGE,
        )

    def test_after_insert_runs(self):
        PLPY_WRAPPER.execute(self.INSERT_NEW_COMPANY_SQL)
        self.assertEqual(
            self.get_trigger_run_log("AFTER", "INSERT").add_data,
            self.TRIGGER_RUN_AFTER_INSERT_MESSAGE,
        )

    def test_before_update_runs(self):
        PLPY_WRAPPER.execute(self.UPDATE_INITIAL_COMPANY_SQL)
        self.assertEqual(
            self.get_trigger_run_log("BEFORE", "UPDATE").add_data,
            self.TRIGGER_RUN_BEFORE_UPDATE_MESSAGE,
        )

    def test_after_update_runs(self):
        PLPY_WRAPPER.execute(self.UPDATE_INITIAL_COMPANY_SQL)
        self.assertEqual(
            self.get_trigger_run_log("AFTER", "UPDATE").add_data,
            self.TRIGGER_RUN_AFTER_UPDATE_MESSAGE,
        )

    def test_before_delete_runs(self):
        PLPY_WRAPPER.execute(self.DELETE_INITIAL_COMPANY_SQL)
        self.assertEqual(
            self.get_trigger_run_log("BEFORE", "DELETE").add_data,
            self.TRIGGER_RUN_BEFORE_DELETE_MESSAGE,
        )

    def test_after_delete_runs(self):
        PLPY_WRAPPER.execute(self.DELETE_INITIAL_COMPANY_SQL)
        self.assertEqual(
            self.get_trigger_run_log("AFTER", "DELETE").add_data,
            self.TRIGGER_RUN_AFTER_DELETE_MESSAGE,
        )

    def test_before_insert_modify(self):
        self.create_triggers(
            before_insert_body="self.trigger_context.new.last_name = 'Constantine';self.overwrite_td_new()",
            table="contact",
            func_name='"customer".func_customer_contact_trigger_controller',
        )

        last_name = PLPY_WRAPPER.execute(
            f"""insert into "customer".contact (first_name,last_name,company_id) values ('John','Smith',{self.COMPANY_ID}) RETURNING last_name"""
        )[0].last_name

        self.assertEqual(
            last_name, "Constantine",
        )

    def test_before_update_modify(self):
        self.create_triggers(
            before_update_body="self.trigger_context.new.last_name = 'Constantine';self.overwrite_td_new()",
            table="contact",
            func_name='"customer".func_customer_contact_trigger_controller',
        )

        contact_id = PLPY_WRAPPER.execute(
            f"""insert into "customer".contact (first_name,last_name,company_id) values ('John','Smith',{self.COMPANY_ID}) RETURNING id"""
        )[0].id
        new_last_name = PLPY_WRAPPER.execute(
            f"""update "customer".contact SET last_name='Strange' WHERE id={contact_id} RETURNING last_name"""
        )[0].last_name

        self.assertEqual(
            new_last_name, "Constantine",
        )

    def test_before_insert_abort_skips(self):
        self.create_triggers(
            before_insert_body="self.abort()",
            table="contact",
            func_name='"customer".func_customer_contact_trigger_controller',
        )

        PLPY_WRAPPER.execute(
            f"""insert into "customer".contact (first_name,last_name,company_id) values ('John','Smith',{self.COMPANY_ID})"""
        )

        self.assertEqual(
            PLPY_WRAPPER.execute('select count(*) as count from "customer".contact')[
                0
            ].count,
            0,
        )

    def test_after_insert_abort_fails(self):
        self.create_triggers(
            after_insert_body="self.abort()",
            table="contact",
            func_name='"customer".func_customer_contact_trigger_controller',
        )

        # since this error is raised thru spi.Exceptions, we can't catch the error directly. This error is from trying to abort when not possible.
        # see Triger._change_trigger_return_val for details on when exceptions are thrown
        with self.assertRaisesRegex(Exception, "The combination of setting value"):
            PLPY_WRAPPER.execute(
                f"""insert into "customer".contact (first_name,last_name,company_id) values ('John','Smith',{self.COMPANY_ID})"""
            )

    def test_before_update_abort_skips(self):
        self.create_triggers(
            before_update_body="self.abort()",
            table="contact",
            func_name='"customer".func_customer_contact_trigger_controller',
        )

        contact_id = PLPY_WRAPPER.execute(
            f"""insert into "customer".contact (first_name,last_name,company_id) values ('John','Smith',{self.COMPANY_ID}) RETURNING id"""
        )[0].id

        PLPY_WRAPPER.execute(
            f"""UPDATE "customer".contact SET last_name='J’onzz' WHERE id={contact_id}"""
        )

        self.assertEqual(
            PLPY_WRAPPER.execute(
                f'select last_name FROM  "customer".contact WHERE id={contact_id}'
            )[0].last_name,
            "Smith",
        )

    def test_after_update_abort_fails(self):
        self.create_triggers(
            after_update_body="self.abort()",
            table="contact",
            func_name='"customer".func_customer_contact_trigger_controller',
        )

        contact_id = PLPY_WRAPPER.execute(
            f"""insert into "customer".contact (first_name,last_name,company_id) values ('John','Smith',{self.COMPANY_ID}) RETURNING id"""
        )[0].id
        # since this error is raised thru spi.Exceptions, we can't catch the error directly. This error is from trying to abort when not possible.
        # see Triger._change_trigger_return_val for details on when exceptions are thrown
        with self.assertRaisesRegex(Exception, "The combination of setting value"):
            PLPY_WRAPPER.execute(
                f"""update "customer".contact SET last_name='Strange' WHERE id={contact_id}"""
            )

    def test_before_delete_abort_skips(self):
        self.create_triggers(
            before_delete_body="self.abort()",
            table="contact",
            func_name='"customer".func_customer_contact_trigger_controller',
        )

        contact_id = PLPY_WRAPPER.execute(
            f"""insert into "customer".contact (first_name,last_name,company_id) values ('John','Smith',{self.COMPANY_ID}) RETURNING id"""
        )[0].id

        PLPY_WRAPPER.execute(
            f"""DELETE FROM "customer".contact WHERE id={contact_id}"""
        )

        self.assertEqual(
            PLPY_WRAPPER.execute(
                f'select count(*) as count from "customer".contact WHERE id={contact_id}'
            )[0].count,
            1,
        )

    def test_after_delete_abort_fails(self):
        self.create_triggers(
            after_delete_body="self.abort()",
            table="contact",
            func_name='"customer".func_customer_contact_trigger_controller',
        )

        contact_id = PLPY_WRAPPER.execute(
            f"""insert into "customer".contact (first_name,last_name,company_id) values ('John','Smith',{self.COMPANY_ID}) RETURNING id"""
        )[0].id
        # since this error is raised thru spi.Exceptions, we can't catch the error directly. This error is from trying to abort when not possible.
        # see Triger._change_trigger_return_val for details on when exceptions are thrown
        with self.assertRaisesRegex(Exception, "The combination of setting value"):
            PLPY_WRAPPER.execute(
                f"""delete from "customer".contact where id={contact_id}"""
            )

    def test_overwrite_td_new_changes_return_value_to_modified_and_overwrites_trigger_new(
        self,
    ):
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_update(
            self.UPDATE_INITIAL_COMPANY_SQL
        )
        new_name = "Dr. Manhattan"
        trigger_handler.trigger_context.new.name = new_name
        trigger_handler.overwrite_td_new()
        self.assertEqual(
            trigger_handler.trigger_return_val, TriggerReturnValue.MODIFIED.value
        )
        self.assertEqual(
            trigger_handler.trigger_context.trigger_data["new"]["name"], new_name
        )

    def test_change_trigger_return_val_succeeds_during_before_insert(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_insert(
            self.INSERT_NEW_COMPANY_SQL
        )
        trigger_handler.overwrite_td_new()
        self.assertEqual(
            trigger_handler.trigger_return_val, TriggerReturnValue.MODIFIED.value
        )

    def test_change_trigger_return_val_succeeds_during_before_update(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_update(
            self.UPDATE_INITIAL_COMPANY_SQL
        )
        trigger_handler.overwrite_td_new()
        self.assertEqual(
            trigger_handler.trigger_return_val, TriggerReturnValue.MODIFIED.value
        )

    def test_change_trigger_return_val_fails_during_after_update(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_after_update(
            self.UPDATE_INITIAL_COMPANY_SQL
        )
        with self.assertRaises(TriggerException):
            trigger_handler.overwrite_td_new()

    def test_change_trigger_return_val_fails_during_after_insert(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_after_insert(
            self.INSERT_NEW_COMPANY_SQL
        )
        with self.assertRaises(TriggerException):
            trigger_handler.overwrite_td_new()

    def test_change_trigger_return_val_fails_during_before_delete(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_before_delete(
            self.DELETE_INITIAL_COMPANY_SQL
        )
        with self.assertRaises(TriggerException):
            trigger_handler.overwrite_td_new()

    def test_change_trigger_return_val_fails_during_after_delete(self):
        trigger_handler = self.execute_sql_and_get_trigger_obj_after_delete(
            self.DELETE_INITIAL_COMPANY_SQL
        )
        with self.assertRaises(TriggerException):
            trigger_handler.overwrite_td_new()


class UtilityTests(unittest.TestCase):
    """Tests for code in utilities.py module"""

    def test_arg_of_correct_type_correct_location_passes(self):
        pass

    def test_arg_of_correct_type_incorrect_location_fails(self):
        pass

    def test_arg_of_incorrect_type_correct_location_fails(self):
        pass

    def test_arg_of_incorrect_type_incorrect_location_fails(self):
        pass

    def test_execute_per_table_runs_with_both_execution_params_defined(self):
        pass

    def test_execute_per_table_runs_with_one_execution_param_defined(self):
        pass

    def test_execute_per_table_fails_with_neither_execution_param_defined(self):
        pass

    def test_execute_per_table_properly_excludes_tables(self):
        pass

    def test_execute_per_table_properly_excludes_schemas(self):
        pass

    def test_get_all_table_runs(self):
        pass

    def test_get_all_tables_properly_excludes_schemas(self):
        pass

    def test_get_all_tables_properly_excludes_tables(self):
        pass

    # create_plpython_triggers is tested in TriggerTest
    def test_create_triggers_runs(self):
        pass

    def test_make_qualified_schema_name_runs(self):
        pass

    def test_list_to_sql_string_runs(self):
        pass


"""

"""


class CustomFeatureTests(TriggerTests):
    """Tests for some sample uses of plply_wrapper"""

    def test_log_row_changes(self):
        TriggerTests.create_triggers(
            table="contact",
            func_name='"customer".func_customer_contact_trigger_controller',
            trigger_template_path=Path(
                Path(__file__).parent,
                "trigger_process_template_custom_feature_test.txt",
            ),
            before_insert_body="pass",
            after_insert_body="pass",
            before_update_body="pass",
            after_update_body="pass",
            before_delete_body="pass",
            after_delete_body="pass",
        )

        company_ids = [
            row.id
            # adding id here since we were getting stange pk violations even though we're using SERIAL UNIQUE types
            for row in PLPY_WRAPPER.execute(
                """insert into "customer".company (id,name) values (100,'GENERATIONX'),(101,'GENERATIONY') RETURNING Id"""
            )
        ]
        contact_id = PLPY_WRAPPER.execute(
            f"""insert into "customer".contact (first_name,last_name,company_id) values ('Galactus','Destroyer of worlds',{company_ids[0]}) RETURNING id"""
        )[0].id
        PLPY_WRAPPER.execute(
            f"""UPDATE "customer".contact SET first_name='Anti-Moniter',last_name='DC Version',company_id={company_ids[1]} """
        )

        expected_logging_rows = [
            Row(
                {
                    "schema_name": "customer",
                    "table_name": "contact",
                    "pk_col": "id",
                    "field_changed": None,
                    "old_value": None,
                    "new_value": None,
                    "event": "INSERT",
                }
            ),
            Row(
                {
                    "schema_name": "customer",
                    "table_name": "contact",
                    "pk_col": "id",
                    "field_changed": "first_name",
                    "old_value": "Galactus",
                    "new_value": "Anti-Moniter",
                    "event": "UPDATE",
                }
            ),
            Row(
                {
                    "schema_name": "customer",
                    "table_name": "contact",
                    "pk_col": "id",
                    "field_changed": "last_name",
                    "old_value": "Destroyer of worlds",
                    "new_value": "DC Version",
                    "event": "UPDATE",
                }
            ),
            Row(
                {
                    "schema_name": "customer",
                    "table_name": "contact",
                    "pk_col": "id",
                    "field_changed": "company_id",
                    "old_value": "100",
                    "new_value": "101",
                    "event": "UPDATE",
                }
            ),
        ]

        rows = [
            row
            for row in PLPY_WRAPPER.execute(
                'select schema_name, table_name, pk_col, field_changed, old_value, new_value, event from "logging".field_history ORDER BY created_at DESC'
            )
        ]

        self.assertEqual(len(expected_logging_rows), len(rows))
        self.assertListEqual(expected_logging_rows, rows)

    def test_custom_constraint_passes(self):
        pass

    def test_custom_constraint_fails(self):
        pass

    # RLS stands for row level security
    def test_RLS_hides_restricted_rows(self):
        pass

    def test_RLS_does_not_hide_permitted_rows(self):
        pass


class RowTests(unittest.TestCase):
    """Tests for code in Row class in plpy_wrappers.py module"""

    def test_row_has_col_names_as_attributes(self):
        pass

    def test_trying_to_set_non_col_attr_of_row_fails(self):
        pass

    def test_modifying_row_dict_does_not_change_row_attrs(self):
        pass


class ResultSetTests(unittest.TestCase):
    def test_accessing_result_set_index_returns_row(self):
        pass

    def test_iterating_thru_result_set_multiple_times_succeeds(self):
        pass

    def test_n_rows_returns_n_rows(self):
        pass

    def test_retreive_spi_status_succeeds(self):
        pass

    def test_colnames_returns_colnames(self):
        pass

    def test_coltypes_returns_coltypes(self):
        pass

    def test_coltypmods_returns_coltypmods(self):
        pass


class PLPYWrapperTests(unittest.TestCase):
    def test_init_without_plpy_in_globals_fails(self):
        pass

    def test_prepare_without_argtypes_returns_prepared_query(self):
        pass

    def test_prepare_with_argtypes_returns_prepared_query(self):
        pass

    def test_execute_plan_without_args_returns_resultset(self):
        pass

    def test_execute_plan_with_args_returns_resultset(self):
        pass

    def test_execute_returns_resultset(self):
        pass

    def test_execute_with_transaction_performs_commit_on_success(self):
        pass

    def test_execute_with_transaction_performs_rollback_on_error(self):
        pass

    def test_execute_with_transaction_raises_error_for_invalid_query(self):
        pass

    def test_subtransaction_runs(self):
        pass

    def test_commit_commits(self):
        pass

    def test_rollback_rollsback(self):
        pass

    def test_publish_message_debug_without_kwargs(self):
        pass

    def test_publish_message_debug_with_all_kwargs(self):
        pass

    def test_publish_message_log_without_kwargs(self):
        pass

    def test_publish_message_log_with_all_kwargs(self):
        pass

    def test_publish_message_info_without_kwargs(self):
        pass

    def test_publish_message_info_with_all_kwargs(self):
        pass

    def test_publish_message_notice_without_kwargs(self):
        pass

    def test_publish_message_notice_with_all_kwargs(self):
        pass

    def test_publish_message_warning_without_kwargs(self):
        pass

    def test_publish_message_warning_with_all_kwargs(self):
        pass

    def test_publish_message_error_without_kwargs(self):
        pass

    def test_publish_message_error_with_all_kwargs(self):
        pass

    def test_publish_message_fatal_without_kwargs(self):
        pass

    def test_publish_message_fatal_with_all_kwargs(self):
        pass

    def test_publish_message_error_raises_exception(self):
        pass

    def test_publish_message_fatal_raises_exception(self):
        pass

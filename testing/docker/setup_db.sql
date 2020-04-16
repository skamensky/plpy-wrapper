drop schema public cascade;
drop schema if exists logging cascade;
drop schema if exists customer cascade;

CREATE schema   public;
create extension if not exists plpython3u;
create schema customer;
create schema logging;

create table if not exists customer.company
(
    id   serial unique not null
        constraint company_pk
            primary key,
    name text
);

create table if not exists customer.contact
(
    id                   serial unique  not null
        constraint contact_pk
            primary key,
    first_name           text not null,
    last_name            text not null,
    company_id           integer
        constraint contact_company_id_fk
            references customer.company,
    ownership_percentage numeric(3, 2)
);


create table if not exists logging.field_history
(
    schema_name text,
    table_name  text,
    pk_col      text,
    pk_val      integer,
    field_changed text,
    old_value   text,
    new_value   text,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    event       text,
    id          serial  unique  not null
        constraint field_history_pk
            primary key
);

create or replace function logging.log_field_changes() returns void as
$$
from plpy_wrapper import utilities, Trigger
from collections import OrderedDict


trigger_handler: Trigger = GD.pop("trigger_handler", None)
pk_col: str = GD.pop("pk_col", None)
if not all([trigger_handler, pk_col]):
    return

@utilities.check_nth_arg_is_of_type(1, Trigger)
def log_row_change(trigger_handler: Trigger):

    trigger_context = trigger_handler.trigger_context
    if trigger_context.when == "BEFORE":
        # only log AFTER events
        return

    def create_plan():
        return trigger_handler.plpy_wrapper.prepare(
            """INSERT INTO "logging".field_history
                (pk_col,pk_val, event, old_value, new_value, field_changed, schema_name, table_name)
                 VALUES
                 ($1,   $2,    $3,    $4,      $5,      $6,            $7,            $8);
                 """,
            ["text", "integer", "text", "text", "text", "text", "text", "text"],
        )

    values = OrderedDict(
        pk_col=pk_col,
        pk_val=trigger_context.new.__getattribute__(pk_col),
        event=trigger_context.event,
        # the placeholders below need to be set for after update events
        # they will remain NULL for insert events and deletion events
        old_value=None,
        new_value=None,
        field_changed=None,
        table_schema=trigger_context.table_schema,
        table_name=trigger_context.table_name,
    )

    if trigger_context.event in ["INSERT", "DELETE"]:

        trigger_handler.plpy_wrapper.execute_plan(
            create_plan(), list(values.values())
        )
        return

    if trigger_context.event == "UPDATE":
        # create a single row in table_history for each changed value
        # using dict access instead of propert for convenience
        for field, val in trigger_context.trigger_data["old"].items():
            if trigger_context.trigger_data["new"][field] != val:
                query_vals_copy = values.copy()
                query_vals_copy["old_value"] = trigger_context.trigger_data["old"][
                    field
                ]
                query_vals_copy["new_value"] = trigger_context.trigger_data["new"][
                    field
                ]
                query_vals_copy["field_changed"] = field
                trigger_handler.plpy_wrapper.execute_plan(
                    create_plan(), list(query_vals_copy.values())
                )

log_row_change(trigger_handler)
$$ language plpython3u;


create table if not exists logging.trigger_run_log
(
    id           serial unique not null,
    TD_data      json not null,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    add_data     text
)


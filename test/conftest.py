from cryptography.hazmat.primitives import serialization
from json import loads
from itertools import groupby
from os import environ
from pytest import fixture
from snowflake.connector import connect, DictCursor

from snowddl import (
    BaseDataType,
    Edition,
    Ident,
    AccountObjectIdent,
    SchemaIdent,
    SchemaObjectIdent,
    SchemaObjectIdentWithArgs,
    SnowDDLFormatter,
    SnowDDLQueryBuilder,
)
from snowflake.connector.cursor import SnowflakeCursor


class Helper:
    DEFAULT_ENV_PREFIX = "PYTEST"

    def __init__(self):
        self.connection = self._init_connection()
        self.env_prefix = self._init_env_prefix()
        self.formatter = SnowDDLFormatter()

        self.edition = self._init_edition()

        self._activate_role_with_prefix()

    def execute(self, sql, params=None) -> SnowflakeCursor:
        sql = self.formatter.format_sql(sql, params)

        return self.connection.cursor(DictCursor).execute(sql)

    def query_builder(self):
        return SnowDDLQueryBuilder(self.formatter)

    def desc_search_optimization(self, database, schema, name):
        cur = self.execute(
            "DESC SEARCH OPTIMIZATION ON {table_name:i}",
            {"table_name": SchemaObjectIdent(self.env_prefix, database, schema, name)},
        )

        items = []

        for r in cur:
            items.append(
                {
                    "method": r["method"],
                    "target": r["target"],
                }
            )

        return items

    def desc_table(self, database, schema, name):
        cur = self.execute("DESC TABLE {name:i}", {"name": SchemaObjectIdent(self.env_prefix, database, schema, name)})

        return {r["name"]: r for r in cur}

    def desc_view(self, database, schema, name):
        cur = self.execute("DESC VIEW {name:i}", {"name": SchemaObjectIdent(self.env_prefix, database, schema, name)})

        return {r["name"]: r for r in cur}

    def desc_external_access_integration(self, name):
        cur = self.execute("DESC EXTERNAL ACCESS INTEGRATION {name:i}", {"name": AccountObjectIdent(self.env_prefix, name)})

        return {r["property"]: r["property_value"] for r in cur}

    def desc_function(self, database, schema, name, dtypes):
        cur = self.execute(
            "DESC FUNCTION {name:i}", {"name": SchemaObjectIdentWithArgs(self.env_prefix, database, schema, name, dtypes)}
        )

        return {r["property"]: r["value"] for r in cur}

    def desc_procedure(self, database, schema, name, dtypes):
        cur = self.execute(
            "DESC PROCEDURE {name:i}", {"name": SchemaObjectIdentWithArgs(self.env_prefix, database, schema, name, dtypes)}
        )

        return {r["property"]: r["value"] for r in cur}

    def desc_file_format(self, database, schema, name):
        cur = self.execute("DESC FILE FORMAT {name:i}", {"name": SchemaObjectIdent(self.env_prefix, database, schema, name)})

        return {r["property"]: r for r in cur}

    def desc_authentication_policy(self, database, schema, name):
        cur = self.execute("DESC AUTHENTICATION POLICY {name:i}", {"name": SchemaObjectIdent(self.env_prefix, database, schema, name)})

        result = {}

        for r in cur:
            result[r["property"]] = r

        return result

    def desc_network_policy(self, name):
        cur = self.execute("DESC NETWORK POLICY {name:i}", {"name": AccountObjectIdent(self.env_prefix, name)})

        return {r["name"]: r for r in cur}

    def desc_network_rule(self, database, schema, name):
        cur = self.execute("DESC NETWORK RULE {name:i}", {"name": SchemaObjectIdent(self.env_prefix, database, schema, name)})

        return cur.fetchone()

    def desc_stage(self, database, schema, name):
        cur = self.execute("DESC STAGE {name:i}", {"name": SchemaObjectIdent(self.env_prefix, database, schema, name)})

        result = {}

        for r in cur:
            if r["parent_property"] not in result:
                result[r["parent_property"]] = {}

            result[r["parent_property"]][r["property"]] = r

        return result

    def get_policy_refs(self, database, schema, policy_name):
        cur = self.execute(
            "SELECT * FROM TABLE(snowflake.information_schema.policy_references(policy_name => {policy_name}))",
            {
                "policy_name": SchemaObjectIdent(self.env_prefix, database, schema, policy_name),
            },
        )

        refs = []

        for r in cur:
            refs.append(r)

        return refs

    def get_network_policy_refs(self, policy_name):
        cur = self.execute(
            "SELECT * FROM TABLE(snowflake.information_schema.policy_references(policy_name => {policy_name}, policy_kind => {policy_kind}))",
            {
                "policy_name": AccountObjectIdent(self.env_prefix, policy_name),
                "policy_kind": "NETWORK_POLICY",
            },
        )

        refs = []

        for r in cur:
            refs.append(r)

        return refs

    def show_alert(self, database, schema, name):
        cur = self.execute(
            "SHOW ALERTS LIKE {alert_name:lf} IN SCHEMA {schema_name:i}",
            {
                "schema_name": SchemaIdent(self.env_prefix, database, schema),
                "alert_name": Ident(name),
            },
        )

        return cur.fetchone()

    def show_dynamic_table(self, database, schema, name):
        cur = self.execute(
            "SHOW DYNAMIC TABLES LIKE {table_name:lf} IN SCHEMA {schema_name:i}",
            {
                "schema_name": SchemaIdent(self.env_prefix, database, schema),
                "table_name": Ident(name),
            },
        )

        return cur.fetchone()

    def show_event_table(self, database, schema, name):
        cur = self.execute(
            "SHOW EVENT TABLES LIKE {table_name:lf} IN SCHEMA {schema_name:i}",
            {
                "schema_name": SchemaIdent(self.env_prefix, database, schema),
                "table_name": Ident(name),
            },
        )

        return cur.fetchone()

    def show_external_access_integration(self, name):
        cur = self.execute(
            "SHOW EXTERNAL ACCESS INTEGRATIONS LIKE {name:lf}",
            {
                "name": AccountObjectIdent(self.env_prefix, name),
            },
        )

        return cur.fetchone()

    def show_sequence(self, database, schema, name):
        cur = self.execute(
            "SHOW SEQUENCES LIKE {sequence_name:lf} IN SCHEMA {schema_name:i}",
            {
                "schema_name": SchemaIdent(self.env_prefix, database, schema),
                "sequence_name": Ident(name),
            },
        )

        return cur.fetchone()

    def show_stage(self, database, schema, name):
        cur = self.execute(
            "SHOW STAGES LIKE {stage_name:lf} IN SCHEMA {schema_name:i}",
            {
                "schema_name": SchemaIdent(self.env_prefix, database, schema),
                "stage_name": Ident(name),
            },
        )

        return cur.fetchone()

    def show_table(self, database, schema, name):
        cur = self.execute(
            "SHOW TABLES LIKE {table_name:lf} IN SCHEMA {schema_name:i}",
            {
                "schema_name": SchemaIdent(self.env_prefix, database, schema),
                "table_name": Ident(name),
            },
        )

        return cur.fetchone()

    def show_function(self, database, schema, name):
        cur = self.execute(
            "SHOW USER FUNCTIONS LIKE {function_name:lf} IN SCHEMA {schema_name:i}",
            {
                "schema_name": SchemaIdent(self.env_prefix, database, schema),
                "function_name": Ident(name),
            },
        )

        return cur.fetchone()

    def show_procedure(self, database, schema, name):
        cur = self.execute(
            "SHOW USER PROCEDURES LIKE {procedure_name:lf} IN SCHEMA {schema_name:i}",
            {
                "schema_name": SchemaIdent(self.env_prefix, database, schema),
                "procedure_name": Ident(name),
            },
        )

        return cur.fetchone()

    def show_file_format(self, database, schema, name):
        cur = self.execute(
            "SHOW FILE FORMATS LIKE {format_name:lf} IN SCHEMA {schema_name:i}",
            {
                "schema_name": SchemaIdent(self.env_prefix, database, schema),
                "format_name": Ident(name),
            },
        )

        return cur.fetchone()

    def show_pipe(self, database, schema, name):
        cur = self.execute(
            "SHOW PIPES LIKE {pipe_name:lf} IN SCHEMA {schema_name:i}",
            {
                "schema_name": SchemaIdent(self.env_prefix, database, schema),
                "pipe_name": Ident(name),
            },
        )

        return cur.fetchone()

    def show_stream(self, database, schema, name):
        cur = self.execute(
            "SHOW STREAMS LIKE {stream_name:lf} IN SCHEMA {schema_name:i}",
            {
                "schema_name": SchemaIdent(self.env_prefix, database, schema),
                "stream_name": Ident(name),
            },
        )

        return cur.fetchone()

    def show_task(self, database, schema, name):
        cur = self.execute(
            "SHOW TASKS LIKE {task_name:lf} IN SCHEMA {schema_name:i}",
            {
                "schema_name": SchemaIdent(self.env_prefix, database, schema),
                "task_name": Ident(name),
            },
        )

        return cur.fetchone()

    def show_task_parameters(self, database, schema, name):
        cur = self.execute(
            "SHOW PARAMETERS IN TASK {name:i}",
            {
                "name": SchemaObjectIdent(self.env_prefix, database, schema, name),
            },
        )

        return {r["key"]: r for r in cur}

    def show_user(self, name):
        cur = self.execute(
            "SHOW USERS LIKE {user_name:lf}",
            {
                "user_name": AccountObjectIdent(self.env_prefix, name),
            },
        )

        return cur.fetchone()

    def show_user_parameters(self, name):
        cur = self.execute(
            "SHOW PARAMETERS IN USER {name:i}",
            {
                "name": AccountObjectIdent(self.env_prefix, name),
            },
        )

        return {r["key"]: r for r in cur}

    def show_view(self, database, schema, name):
        cur = self.execute(
            "SHOW VIEWS LIKE {view_name:lf} IN SCHEMA {schema_name:i}",
            {
                "schema_name": SchemaIdent(self.env_prefix, database, schema),
                "view_name": Ident(name),
            },
        )

        return cur.fetchone()

    def show_primary_key(self, database, schema, name):
        cur = self.execute(
            "SHOW PRIMARY KEYS IN TABLE {table_name:i}",
            {"table_name": SchemaObjectIdent(self.env_prefix, database, schema, name)},
        )

        sorted_cur = sorted(cur, key=lambda r: r["key_sequence"])

        return [r["column_name"] for r in sorted_cur]

    def show_unique_keys(self, database, schema, name):
        cur = self.execute(
            "SHOW UNIQUE KEYS IN TABLE {table_name:i}", {"table_name": SchemaObjectIdent(self.env_prefix, database, schema, name)}
        )

        sorted_cur = sorted(cur, key=lambda r: (r["constraint_name"], r["key_sequence"]))

        return [[r["column_name"] for r in g] for k, g in groupby(sorted_cur, lambda r: r["constraint_name"])]

    def show_foreign_keys(self, database, schema, name):
        cur = self.execute(
            "SHOW IMPORTED KEYS IN TABLE {table_name:i}",
            {"table_name": SchemaObjectIdent(self.env_prefix, database, schema, name)},
        )

        sorted_cur = sorted(cur, key=lambda r: (r["fk_name"], r["key_sequence"]))
        fk = []

        for k, g in groupby(sorted_cur, lambda r: r["fk_name"]):
            g = list(g)

            fk.append(
                {
                    "columns": [r["fk_column_name"] for r in g],
                    "ref_table": f"{g[0]['pk_database_name']}.{g[0]['pk_schema_name']}.{g[0]['pk_table_name']}",
                    "ref_columns": [r["pk_column_name"] for r in g],
                }
            )

        return fk

    def show_authentication_policy(self, database, schema, name):
        cur = self.execute(
            "SHOW AUTHENTICATION POLICIES LIKE {object_name:lf} IN SCHEMA {schema_name:i}",
            {
                "schema_name": SchemaIdent(self.env_prefix, database, schema),
                "object_name": Ident(name),
            }
        )

        return cur.fetchone()

    def show_network_policy(self, name):
        # SHOW NETWORK POLICIES does not support LIKE natively
        cur = self.execute("SHOW NETWORK POLICIES")

        for r in cur:
            if r["name"] == str(AccountObjectIdent(self.env_prefix, name)):
                return r

    def show_network_rule(self, database, schema, name):
        cur = self.execute(
            "SHOW NETWORK RULES LIKE {object_name:lf} IN SCHEMA {schema_name:i}",
            {
                "schema_name": SchemaIdent(self.env_prefix, database, schema),
                "object_name": Ident(name),
            },
        )

        return cur.fetchone()

    def show_resource_monitor(self, name):
        cur = self.execute(
            "SHOW RESOURCE MONITORS LIKE {name:lf}",
            {
                "name": AccountObjectIdent(self.env_prefix, name),
            },
        )

        return cur.fetchone()

    def show_secret(self, database, schema, name):
        cur = self.execute(
            "SHOW SECRETS LIKE {object_name:lf} IN SCHEMA {schema_name:i}",
            {
                "schema_name": SchemaIdent(self.env_prefix, database, schema),
                "object_name": Ident(name),
            },
        )

        return cur.fetchone()

    def show_warehouse(self, name):
        cur = self.execute(
            "SHOW WAREHOUSES LIKE {name:lf}",
            {
                "name": AccountObjectIdent(self.env_prefix, name),
            },
        )

        return cur.fetchone()

    def show_warehouse_parameters(self, name):
        cur = self.execute(
            "SHOW PARAMETERS IN WAREHOUSE {name:i}",
            {
                "name": AccountObjectIdent(self.env_prefix, name),
            },
        )

        return {r["key"]: r for r in cur}

    def show_hybrid_table(self, database, schema, name):
        cur = self.execute(
            "SHOW HYBRID TABLES LIKE {object_name:lf} IN SCHEMA {schema_name:i}",
            {
                "schema_name": SchemaIdent(self.env_prefix, database, schema),
                "object_name": Ident(name),
            },
        )

        return cur.fetchone()

    def show_iceberg_table(self, database, schema, name):
        cur = self.execute(
            "SHOW ICEBERG TABLES LIKE {object_name:lf} IN SCHEMA {schema_name:i}",
            {
                "schema_name": SchemaIdent(self.env_prefix, database, schema),
                "object_name": Ident(name),
            },
        )

        return cur.fetchone()

    def show_indexes(self, database, schema, name):
        cur = self.execute(
            "SHOW INDEXES IN TABLE {table_name:i}",
            {
                "table_name": SchemaObjectIdent(self.env_prefix, database, schema, name),
            },
        )

        return {r["name"]: r for r in cur}

    def is_edition_enterprise(self):
        return self.edition >= Edition.ENTERPRISE

    def is_edition_business_critical(self):
        return self.edition >= Edition.BUSINESS_CRITICAL

    def dtypes_from_arguments(self, arguments: str):
        all_dtypes = []

        start_dtypes_idx = arguments.index("(")
        finish_dtypes_idx = arguments.index(") RETURN ")

        for dtype_part in self.split_by_comma_outside_parentheses(arguments[start_dtypes_idx + 1 : finish_dtypes_idx]):
            # Remove optional DEFAULT prefix from the beginning
            dtype_part = dtype_part.removeprefix("DEFAULT ")

            # Remove optional data type size introduced in bundle 2025_03
            # https://docs.snowflake.com/en/release-notes/bcr-bundles/2025_03/bcr-1944
            dtype_size_start_idx = dtype_part.find("(")

            if dtype_size_start_idx > -1:
                dtype_part = dtype_part[:dtype_size_start_idx]

            all_dtypes.append(dtype_part)

        return [BaseDataType[dtype] for dtype in all_dtypes]

    def split_by_comma_outside_parentheses(self, s: str):
        parts = []
        current = []
        depth = 0

        for char in s:
            if char == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []

            else:
                if char == "(":
                    depth += 1
                elif char == ")":
                    depth -= 1

                current.append(char)

        if current:
            parts.append("".join(current).strip())

        return parts

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.connection.close()

    def _init_connection(self):
        key_bytes = str(environ["SNOWFLAKE_PRIVATE_KEY"]).encode("utf-8")
        pk = serialization.load_pem_private_key(data=key_bytes, password=None)

        options = {
            "account": environ.get("SNOWFLAKE_ACCOUNT"),
            "user": environ.get("SNOWFLAKE_USER"),
            "private_key": pk.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        }

        return connect(**options)

    def _init_env_prefix(self):
        return environ.get("SNOWFLAKE_ENV_PREFIX", self.DEFAULT_ENV_PREFIX).upper() + "__"

    def _init_edition(self):
        cur = self.execute("SELECT SYSTEM$BOOTSTRAP_DATA_REQUEST('ACCOUNT') AS bootstrap_account")
        r = cur.fetchone()

        bootstrap_account = loads(r["BOOTSTRAP_ACCOUNT"])

        return Edition[bootstrap_account["accountInfo"]["serviceLevelName"]]

    def _activate_role_with_prefix(self):
        if not self.env_prefix:
            return

        cur = self.execute("SELECT CURRENT_ROLE() AS current_role")
        r = cur.fetchone()

        self.execute(
            "USE ROLE {role_with_prefix:i}",
            {
                "role_with_prefix": AccountObjectIdent(self.env_prefix, r["CURRENT_ROLE"]),
            },
        )


@fixture(scope="session")
def helper():
    with Helper() as helper:
        yield helper

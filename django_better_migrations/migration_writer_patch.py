from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.writer import MigrationWriter


# Safety check to ensure we actually can patch MigrationWriter correctly
if "as_string" not in dir(MigrationWriter):
    raise ValueError(
        "This patch is not compatible with your version of Django: "
        "'django.db.migrations.writer.MigrationWriter' has no method 'as_string()'"
    )


# Patch writer's as_string() method to add comments in the resulting file
def as_string_with_sql_annotations(self, *args, **kwargs):
    content = self._original_as_string(*args, **kwargs)
    assert "\nclass Migration" in content, "couldn't find 'class Migration' in migration content"

    # write migration un-processed so the executor can find/read it
    with open(self.path, "w") as f:
        f.write(content)

    # get SQL code
    connection = connections[DEFAULT_DB_ALIAS]
    executor = MigrationExecutor(connection)
    app_label = self.migration.app_label
    mirgation_name = self.migration.name
    plan = [(executor.loader.graph.nodes[(app_label, mirgation_name)], False)]
    sql_statements = executor.collect_sql(plan)

    # amend content that will be written to disk
    comment = "\n".join("# %s" % stmt for stmt in sql_statements)
    comment = "# Generated SQL code (%s):\n#\n%s\n#\n" % (connection.vendor, comment)

    content = content.replace(
        "\nclass Migration",
        "\n%sclass Migration" % comment,
    )

    return content


MigrationWriter._original_as_string = MigrationWriter.as_string
MigrationWriter.as_string = as_string_with_sql_annotations

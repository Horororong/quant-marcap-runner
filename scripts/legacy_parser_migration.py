"""Changing a parser version never authorizes replaying its whole old queue."""


class ParserMigrationRequired(RuntimeError):
    pass


def require_explicit_migration(records, current_version):
    """Read-only guard, before document collection/checkpoint mutation.

    Native source absence can be carried independently of numeric parsers.
    Everything else with an earlier explicit parser version must first pass a
    bounded offline source replay and a separately authorized migration. No
    environment escape hatch clears old quarantine or grants that approval.
    """
    versions = {}
    records = list(records)
    current = {r.get('rcept_no') for r in records if r.get('parser_version') == current_version}
    for row in records:
        version = row.get('parser_version', '')
        if (version and version != current_version and row.get('status') != 'NO_DOCUMENT'
                and row.get('rcept_no') not in current):
            versions[version] = versions.get(version, 0) + 1
    if versions:
        raise ParserMigrationRequired(
            'PARSER_MIGRATION_REQUIRED: earlier classified states=' + str(sorted(versions.items()))
            + '; parser upgrade does not authorize requeue. Use bounded offline '
            'original-source review and an explicit reviewed migration; existing states preserved.')

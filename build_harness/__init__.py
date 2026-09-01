"""SRAF streaming build harness (Phase IV).

Processes the Dataset B corpus one repository at a time without ever holding
the whole corpus on disk: clone to scratch -> find artifacts -> lift ->
build-test (containerless venv) -> FAIR-R score -> persist triples + results
-> delete the clone. Designed for a Slurm array, one repo per task.
"""

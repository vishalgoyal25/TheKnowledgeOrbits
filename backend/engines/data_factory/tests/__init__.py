# engines/data_factory/tests/__init__.py
# Required, not cruft: without it pytest cannot distinguish this engine's
# test_models.py from the same basename in book_content/ and tags/, and fails
# collection with an import-file-mismatch error.

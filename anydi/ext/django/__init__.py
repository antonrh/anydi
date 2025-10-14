raise ImportError(
    "The Django extension requires additional dependencies.\n\n"
    "Install one of the following extras:\n"
    "  pip install 'anydi-django'         # for Django\n"
    "  pip install 'anydi-django[ninja]'  # for Django Ninja\n\n"
    "Then, instead of importing from 'anydi.ext.django', import directly from:\n"
    "  import anydi_django\n"
)

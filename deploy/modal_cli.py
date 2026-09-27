"""La CLI de Modal usando los certificados del sistema (Windows con antivirus que inspecciona HTTPS).

    .venv\\Scripts\\python deploy\\modal_cli.py <argumentos de modal>

Modal y grpclib validan TLS solo con el paquete `certifi`; si un antivirus (p. ej. Avast)
intercepta HTTPS con su propia raíz, fallan. truststore hace que usen el almacén del sistema.
"""

import sys

import truststore

truststore.inject_into_ssl()

from modal.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

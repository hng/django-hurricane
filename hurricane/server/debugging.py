from hurricane.server import logger


def setup_debugpy(options):
    if options["debugger"]:
        try:
            import debugpy
        except ImportError:
            logger.warning(
                "Ignoring '--debugger' flag because module 'debugpy' was not found. "
                "Make sure to install 'django-hurricane' with the 'debug' option, "
                "e.g. 'pip install django-hurricane[debug]'."
            )
        else:
            port = options["debugger_port"]
            debugpy.listen(("0.0.0.0", port))
            logger.info(f"Listening for debug clients at port {port}")


def setup_pycharm(options):
    if options["pycharm_host"]:
        try:
            import pydevd_pycharm
        except ImportError:
            logger.warning(
                "Ignoring '--pycharm_host' option because module 'pydevd_pycharm' was not found. "
                "Make sure to install 'django-hurricane' with the 'pycharm' option, "
                "e.g. 'pip install django-hurricane[pycharm]' or install your required version "
                "of 'pydevd-pycharm' manually."
            )
        else:
            host = options["pycharm_host"]
            port = options["pycharm_port"]
            if port:
                pydevd_pycharm.settrace(host, port=port, stdoutToServer=True, stderrToServer=True)
                logger.info(f"Connected to debug server at {host}:{port}")
            else:
                logger.warning(
                    "No '--pycharm-port' was specified. The '--pycharm-host' option can "
                    "only be used in combination with the '--pycharm-port' option. "
                )

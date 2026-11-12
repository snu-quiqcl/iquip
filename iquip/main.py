"""iquip launcher, extending qiwis with optional Builder session persistence."""

import logging
import sys
from typing import Optional, Sequence

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication

import qiwis
from iquip.builder_state import BuilderStateManager, IquipQiwis, resolveStatePath

logger = logging.getLogger(__name__)


def getArgParser():
    """Returns qiwis's installed-version parser with the iquip session option."""
    parser = qiwis._get_argparser()  # pylint: disable=protected-access
    parser.add_argument(
        "--builder-state-file",
        dest="builder_state_file",
        metavar="PATH",
        help="persist and restore open Builder windows in a separate JSON session file",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None):
    """Starts iquip using qiwis's normal config loader and application manager."""
    args = getArgParser().parse_args(argv)
    logger.info("Parsed arguments: %s", args)
    appInfos, constants = qiwis._read_config_file(  # pylint: disable=protected-access
        args.config_path
    )
    qapp = QApplication(sys.argv if argv is None else [sys.argv[0], *argv])
    constantNamespace = qiwis.set_global_constant_namespace(constants)
    if args.builder_state_file is None:
        manager = qiwis.Qiwis(appInfos, constantNamespace, args.is_maximized)
    else:
        manager = IquipQiwis(appInfos, constantNamespace, args.is_maximized)
        statePath = resolveStatePath(args.builder_state_file)
        stateManager = BuilderStateManager(manager, statePath, parent=manager)
        qapp.aboutToQuit.connect(stateManager.shutdown)
        QTimer.singleShot(0, stateManager.start)
    logger.info("Now the QApplication starts")
    return qapp.exec_()


if __name__ == "__main__":
    main()


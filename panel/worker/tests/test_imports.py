from app.backend_client import BackendClient
from app.commands import CommandResult, WorkerCommand
from app.handlers import CommandHandler
from app.main import Settings, build_parser
from app.node_client import NodeClient
from app.queue import RabbitQueue


def test_worker_modules_import_cleanly() -> None:
    assert BackendClient
    assert CommandHandler
    assert CommandResult
    assert NodeClient
    assert RabbitQueue
    assert Settings
    assert WorkerCommand


def test_help_parser_is_available() -> None:
    parser = build_parser()
    help_text = parser.format_help()

    assert 'standalone panel worker' in help_text
    assert '--check-config' in help_text

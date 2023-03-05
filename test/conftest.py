"""
Pytest test customization config file.
"""

def pytest_addoption(parser):
    """
    Configure new pytest CLI options.
    """
    parser.addoption(
        "--noclean",
        action="store_true",
        default=False,
        help="Skip cleanup file output resulting from test runs."
    )

# Copyright (Change Date see Readme), gematik GmbH
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ******
#
# For additional notes and disclaimer from gematik and in case of changes
# by gematik, find details in the "Readme" file.

"""Foreground mock lifecycle with graceful container termination."""

import signal
import threading
from types import FrameType

from .server import MockHttpServer


def serve_mock_server(server: MockHttpServer) -> None:
    """Serve until interrupted, closing the socket on Ctrl+C or SIGTERM."""
    previous_handler = None
    install_handler = threading.current_thread() is threading.main_thread()
    try:
        if install_handler:
            previous_handler = signal.signal(signal.SIGTERM, _interrupt)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if install_handler:
            signal.signal(signal.SIGTERM, previous_handler)


def _interrupt(signum: int, frame: FrameType | None) -> None:
    # Raising interrupts serve_forever; shutdown() here would deadlock its thread.
    raise KeyboardInterrupt

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

import signal
import unittest
from unittest.mock import Mock, patch

from tools.openapi_arazzo_tool.mocking.lifecycle import serve_mock_server


class MockLifecycleTest(unittest.TestCase):
    def test_closes_socket_and_restores_handler_after_container_termination(
        self,
    ) -> None:
        server = Mock()
        previous = signal.SIG_DFL

        def terminate() -> None:
            handler = register.call_args_list[0].args[1]
            handler(signal.SIGTERM, None)

        server.serve_forever.side_effect = terminate
        with patch(
            "tools.openapi_arazzo_tool.mocking.lifecycle.signal.signal",
            return_value=previous,
        ) as register:
            serve_mock_server(server)

        server.server_close.assert_called_once()
        self.assertEqual(register.call_args_list[-1].args, (signal.SIGTERM, previous))

    def test_closes_socket_and_propagates_unexpected_failure(self) -> None:
        server = Mock()
        server.serve_forever.side_effect = OSError("Server failure")
        with patch("tools.openapi_arazzo_tool.mocking.lifecycle.signal.signal"):
            with self.assertRaises(OSError):
                serve_mock_server(server)

        server.server_close.assert_called_once()

    def test_worker_thread_does_not_install_process_signal_handler(self) -> None:
        server = Mock()
        with (
            patch(
                "tools.openapi_arazzo_tool.mocking.lifecycle.threading.current_thread"
            ),
            patch(
                "tools.openapi_arazzo_tool.mocking.lifecycle.signal.signal"
            ) as register,
        ):
            serve_mock_server(server)

        register.assert_not_called()
        server.server_close.assert_called_once()

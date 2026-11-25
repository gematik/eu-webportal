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

"""Static detection of unconditional Arazzo control-flow cycles."""

from collections.abc import Mapping, Sequence
from typing import Any, TypeGuard

from ..errors import ExitCode, ToolError
from .model import ArazzoDocument

_Node = tuple[str, str]


def find_control_flow_issues(document: ArazzoDocument) -> list[ToolError]:
    """Report cycles formed by sequential flow and unconditional success gotos.

    Conditions are runtime expressions and are deliberately not evaluated here.
    Only an action without ``criteria`` creates an unconditional static edge.
    """
    workflows = document.raw.get("workflows")
    if not _is_sequence(workflows):
        return []

    graph, paths = _build_graph(workflows)
    cyclic_nodes = _find_cyclic_nodes(graph)
    return [
        ToolError(
            "ARAZZO_CONTROL_FLOW_CYCLE",
            f"Unconditional control-flow cycle detected. Found at {paths[node]}.",
            ExitCode.VALIDATION_ERROR,
            document.path,
        )
        for node in sorted(cyclic_nodes)
    ]


def _build_graph(
    workflows: Sequence[Any],
) -> tuple[dict[_Node, set[_Node]], dict[_Node, str]]:
    graph: dict[_Node, set[_Node]] = {}
    paths: dict[_Node, str] = {}
    workflow_entries: dict[str, _Node] = {}

    for workflow_index, workflow in enumerate(workflows):
        if not isinstance(workflow, Mapping):
            continue
        workflow_id = workflow.get("workflowId")
        steps = workflow.get("steps")
        if not isinstance(workflow_id, str) or not _is_sequence(steps):
            continue
        for step_index, step in enumerate(steps):
            if not isinstance(step, Mapping) or not isinstance(step.get("stepId"), str):
                continue
            node = (workflow_id, step["stepId"])
            graph.setdefault(node, set())
            paths[node] = f"$.workflows[{workflow_index}].steps[{step_index}]"
            if step_index == 0:
                workflow_entries[workflow_id] = node

    for workflow in workflows:
        if not isinstance(workflow, Mapping):
            continue
        workflow_id = workflow.get("workflowId")
        steps = workflow.get("steps")
        if not isinstance(workflow_id, str) or not _is_sequence(steps):
            continue
        for step_index, step in enumerate(steps):
            if not isinstance(step, Mapping) or not isinstance(step.get("stepId"), str):
                continue
            node = (workflow_id, step["stepId"])
            target = _unconditional_success_target(step)
            if target is None:
                _add_sequential_edge(graph, node, workflow_id, steps, step_index)
            elif target[0] == "step":
                target_node = (workflow_id, target[1])
                if target_node in graph:
                    graph[node].add(target_node)
            elif target[1] in workflow_entries:
                graph[node].add(workflow_entries[target[1]])
    return graph, paths


def _unconditional_success_target(step: Mapping[str, Any]) -> tuple[str, str] | None:
    actions = step.get("onSuccess")
    if not _is_sequence(actions):
        return None
    for action in actions:
        if not isinstance(action, Mapping):
            continue
        if action.get("criteria") is not None:
            continue
        if action.get("type") == "end":
            return ("end", "")
        if action.get("type") == "goto":
            if isinstance(action.get("stepId"), str):
                return ("step", action["stepId"])
            if isinstance(action.get("workflowId"), str):
                return ("workflow", action["workflowId"])
    return None


def _add_sequential_edge(
    graph: dict[_Node, set[_Node]],
    node: _Node,
    workflow_id: str,
    steps: Sequence[Any],
    step_index: int,
) -> None:
    if step_index + 1 >= len(steps):
        return
    next_step = steps[step_index + 1]
    if isinstance(next_step, Mapping) and isinstance(next_step.get("stepId"), str):
        target = (workflow_id, next_step["stepId"])
        if target in graph:
            graph[node].add(target)


def _find_cyclic_nodes(graph: dict[_Node, set[_Node]]) -> set[_Node]:
    visited: set[_Node] = set()
    active: set[_Node] = set()
    stack: list[_Node] = []
    stack_indexes: dict[_Node, int] = {}
    cyclic: set[_Node] = set()

    def visit(node: _Node) -> None:
        if node in active:
            cyclic.update(stack[stack_indexes[node] :])
            return
        if node in visited:
            return
        visited.add(node)
        active.add(node)
        stack_indexes[node] = len(stack)
        stack.append(node)
        for target in graph[node]:
            visit(target)
        stack.pop()
        del stack_indexes[node]
        active.remove(node)

    for node in graph:
        visit(node)
    return cyclic


def _is_sequence(value: Any) -> TypeGuard[Sequence[Any]]:
    return isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    )

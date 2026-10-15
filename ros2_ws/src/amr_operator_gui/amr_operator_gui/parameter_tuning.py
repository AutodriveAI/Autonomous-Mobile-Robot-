"""Comment-preserving ROS parameter YAML model for operator tuning."""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
from yaml.nodes import MappingNode, ScalarNode


_DWB_LIVE_KINEMATICS = {
    "acc_lim_theta",
    "acc_lim_x",
    "acc_lim_y",
    "decel_lim_theta",
    "decel_lim_x",
    "decel_lim_y",
    "max_speed_xy",
    "max_vel_theta",
    "max_vel_x",
    "max_vel_y",
    "min_speed_theta",
    "min_speed_xy",
    "min_vel_x",
    "min_vel_y",
}
_NAVFN_LIVE_PARAMETERS = {"allow_unknown", "tolerance", "use_astar"}


@dataclass
class ApplyPolicy:
    """How a parameter change can be applied to the physical robot."""

    mode: str
    owner: str
    node: str


@dataclass
class ParameterEntry:
    """One leaf parameter, retaining its source location and YAML order."""

    identifier: str
    node: str
    name: str
    section: str
    description: str
    original_value: Any
    value_text: str
    value_start: int
    value_end: int
    order: int
    editable: bool
    policy: ApplyPolicy
    staged_value: Any = None
    staged_text: str = ""

    @property
    def dirty(self) -> bool:
        return bool(self.staged_text)

    @property
    def display_text(self) -> str:
        return self.staged_text or self.value_text


class ParameterDocument:
    """Parsed parameter file with safe scalar staging and lossless comments."""

    def __init__(self, filename: str, source: str) -> None:
        self.filename = filename
        self.source = source
        self.entries = _parse_entries(filename, source)
        self._by_identifier = {
            entry.identifier: entry for entry in self.entries
        }

    @property
    def dirty(self) -> bool:
        return any(entry.dirty for entry in self.entries)

    def entry(self, identifier: str) -> ParameterEntry:
        return self._by_identifier[identifier]

    def stage(self, identifier: str, text: str) -> ParameterEntry:
        entry = self.entry(identifier)
        if not entry.editable:
            raise ValueError("Complex YAML values are read-only in this editor.")
        value, normalized = _parse_scalar_edit(text, entry.original_value)
        if value == entry.original_value:
            entry.staged_value = None
            entry.staged_text = ""
        else:
            entry.staged_value = value
            entry.staged_text = normalized
        return entry

    def render(self) -> str:
        result = self.source
        replacements = [entry for entry in self.entries if entry.dirty]
        for entry in sorted(
            replacements, key=lambda item: item.value_start, reverse=True
        ):
            result = (
                result[:entry.value_start]
                + entry.staged_text
                + result[entry.value_end:]
            )
        yaml.safe_load(result)
        return result


def parameter_key(filename: str, node: str, name: str) -> str:
    """Return a stable key used for persistent per-user favorites."""
    return "{}|{}|{}".format(filename, node, name)


def apply_policy(filename: str, node: str, name: str) -> ApplyPolicy:
    """Return a conservative Foxy runtime/restart classification."""
    basename = Path(filename).name
    if basename == "nav2_params_real.yaml":
        if node == "/controller_server" and name.startswith("FollowPath."):
            suffix = name.split(".")[-1]
            if suffix in _DWB_LIVE_KINEMATICS:
                return ApplyPolicy("live", "nav2", node)
        if node == "/planner_server" and name.startswith("GridBased."):
            suffix = name.split(".")[-1]
            if suffix in _NAVFN_LIVE_PARAMETERS:
                return ApplyPolicy("live", "nav2", node)
        return ApplyPolicy("restart", "nav2", node)
    if basename == "twist_mux.yaml":
        return ApplyPolicy("restart", "bringup", node)
    return ApplyPolicy("restart", "external", node)


def _parse_entries(filename: str, source: str) -> List[ParameterEntry]:
    try:
        root = yaml.compose(source)
    except yaml.YAMLError as error:
        raise ValueError("Invalid YAML: {}".format(error))
    if root is None:
        return []
    if not isinstance(root, MappingNode):
        raise ValueError("Parameter YAML must contain a top-level mapping.")

    lines = source.splitlines()
    entries: List[ParameterEntry] = []

    def find_parameter_blocks(node, ancestors: Tuple[str, ...]) -> None:
        if not isinstance(node, MappingNode):
            return
        for key_node, value_node in node.value:
            key = str(key_node.value)
            if key == "ros__parameters":
                ros_node = "/" + "/".join(ancestors)
                _walk_parameters(
                    value_node,
                    filename,
                    ros_node,
                    (),
                    entries,
                    lines,
                    source,
                )
            elif isinstance(value_node, MappingNode):
                find_parameter_blocks(value_node, ancestors + (key,))

    find_parameter_blocks(root, ())
    return entries


def _walk_parameters(
    node,
    filename: str,
    ros_node: str,
    parents: Tuple[str, ...],
    entries: List[ParameterEntry],
    lines: List[str],
    source: str,
) -> None:
    if not isinstance(node, MappingNode):
        return
    for key_node, value_node in node.value:
        key = str(key_node.value)
        if isinstance(value_node, MappingNode):
            _walk_parameters(
                value_node,
                filename,
                ros_node,
                parents + (key,),
                entries,
                lines,
                source,
            )
            continue

        name = ".".join(parents + (key,))
        value_text = source[value_node.start_mark.index:value_node.end_mark.index]
        try:
            value = yaml.safe_load(value_text)
        except yaml.YAMLError:
            value = value_text
        editable = isinstance(value_node, ScalarNode) and isinstance(
            value, (bool, int, float, str)
        )
        identifier = parameter_key(filename, ros_node, name)
        entries.append(ParameterEntry(
            identifier=identifier,
            node=ros_node,
            name=name,
            section=_section_label(ros_node, parents),
            description=_description_for(lines, key_node.start_mark.line),
            original_value=value,
            value_text=value_text.strip(),
            value_start=value_node.start_mark.index,
            value_end=value_node.end_mark.index,
            order=len(entries),
            editable=editable,
            policy=apply_policy(filename, ros_node, name),
        ))


def _description_for(lines: List[str], key_line: int) -> str:
    description = []
    index = key_line - 1
    while index >= 0:
        stripped = lines[index].strip()
        if not stripped or stripped == "#" or not stripped.startswith("#"):
            break
        description.append(stripped[1:].strip())
        index -= 1
    description.reverse()
    return " ".join(part for part in description if part)


def _section_label(node: str, parents: Tuple[str, ...]) -> str:
    tokens = parents or (node.rstrip("/").split("/")[-1],)
    return " / ".join(_pretty_token(token) for token in tokens)


def _pretty_token(token: str) -> str:
    special = {
        "FollowPath": "Path following (FollowPath)",
        "goal_checker": "Goal checker",
        "progress_checker": "Progress checker",
        "inflation_layer": "Inflation layer",
        "obstacle_layer": "Obstacle layer",
        "static_layer": "Static layer",
        "GridBased": "Global path planner (GridBased)",
    }
    if token in special:
        return special[token]
    return token.replace("_", " ").strip().capitalize()


def _parse_scalar_edit(text: str, original: Any) -> Tuple[Any, str]:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Parameter value cannot be empty.")
    try:
        value = yaml.safe_load(stripped)
    except yaml.YAMLError as error:
        raise ValueError("Invalid YAML scalar: {}".format(error))

    if isinstance(original, bool):
        if not isinstance(value, bool):
            raise ValueError("Expected a boolean value: true or false.")
        return value, "true" if value else "false"
    if isinstance(original, int) and not isinstance(original, bool):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError("Expected an integer value.")
        return value, str(value)
    if isinstance(original, float):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError("Expected a numeric value.")
        value = float(value)
        return value, repr(value)
    if isinstance(original, str):
        if not isinstance(value, str):
            raise ValueError(
                "Expected text. Quote values such as 'true' or '10'."
            )
        return value, json.dumps(value)
    raise ValueError("This YAML value type is not editable.")

"""Initiate live connections that automate certain tasks associated with the creation of such connections."""

from __future__ import annotations

import pathlib
import sys
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import TimeoutError as ConTimeoutError
from contextlib import AbstractContextManager
from datetime import timedelta
from logging import getLogger
from typing import TYPE_CHECKING

import numpy as np

from eta_connect import json_import
from eta_connect.connectors import name_map_from_node_sequence
from eta_connect.connectors.base_classes import Connection
from eta_connect.connectors.node import Node

if TYPE_CHECKING:
    import types
    from typing import Any

    from typing_extensions import Self

    from eta_connect.type_hints import Path, TimeStep

log = getLogger(__name__)


class LiveConnect(AbstractContextManager):
    """Connect to a system/resource and enable system activation, deactivation and configuring controller setpoints.

    The class can be initialized directly by supplying all required arguments or from a JSON configuration file.

    If initializing with the from_json classmethod, the class takes a JSON config file which defines all
    required nodes. The JSON file should have the following format:

        * **system**: Define the system to be controlled. This is the top level block - it may have multiple dictionary
          members which should each specify all the following information. If there are multiple systems, all
          node names will be prefixed with the system name. For example, if the system name is 'chp' and the node
          name is 'op_request', the full node name will be 'chp.op_request'.
        * **name**: A name to uniquely identify the system.
        * **servers**: Servers which are responsible for manageing the system. This section should contain a dictionary
          of servers, identified by a unique name. Each server has the following values:

            * **url**: URL of the server (format: netloc:port, without the scheme).
            * **protocol**: Protocol for the connection, for example 'opcua'.
            * **usr**: Username to identify with the server (default: None).
            * **pwd**: Password to log in to the server (default: None).
        * **nodes**: The nodes section contains a list of nodes. Each node is specific to one of the servers specified
          above and has a unique name, by which it can be identified. In detail, each node has the following values:

            * **name**: A name to uniquely identify the node.
            * **server**: Identifier of one of the servers defined above.
            * **dtype**: Data type of the Node on the server (default: float).
            * Other values must be defined depending on the protocol, for example this could be an **opc_id** or
              corresponding values to identify modbus nodes. More detail about this can be found in connectors.Nodes.
        * **set_value**: The set_value is the main value, which should be manipulated. It must have some additional
          information to be processed correctly. This includes:

            * **name**: Name of the node, which is manipulated as the set_value.
            * **min**: Minimum value to be allowed.
            * **max**: Maximum value to be allowed.
            * **threshold**: Activation/Deactivation threshold. The activate action will be executed for values above
              the threshold and the deactivation action will be executed for values below the threshold (see below).
            * **add**: Scale the set_value by adding a set amount.
            * **mult**: Scale the set_value by multiplying by this factor.
        * **activation_indicators**: The values specified in this section are used to determine, whether the system is
          currently active. This is a dictionary of nodes and values, these nodes should be compared against. Each node
          is identified by the name specified above. Each node must have the following values:

            * **compare**: Comparison operation to perform (for example '==' or '<=').
            * **value**: Value to compare against. If the result of all comparisons is True, the system is considered
              to be currently active.
        * **observe**: Values to return after each set operation. This is just a list of node names as specified in
          the nodes section above.
        * **actions**: In the actions section, default values for more complex operations are specified. For example,
          if a system needs to be initialized or deactivated. Each of the actions is a dictionary of node names
          and corresponding values, for example {node1: true, node2: 0.2}. The following actions are defined:

            * **init**: Initialize the system. This is used to make sure that the system is ready to receive control
              values from the connector.
            * **activate**: Activate the system. This is used to set the system to an active state, for example by
              requesting the system to start its operation and choosing and operating mode. This can be used to set
              the system up to receive more detailed control values.
            * **deactivate**: Execute any actions to deactivate the system.
            * **close**: Reset the system. This is used when the connector is closed, to make sure the system is left
              in a safe and clean state.

    If initializing manually, each of the actions and some other information must be specified as parameters to the
    class. This way, the class will not automatically identify different systems and will instead assume that all
    parameters belong to the same system. If system differentiation is required, the node prefixing must be done
    manually. The third option is to initialize from a dictionary using the from_dict function. This works equivalent to
    the from_json function.

    .. warning ::
        Always call the close function after you are done using the connection! This is required even if no nodes
        must be written to reset the system since the connection itself must be closed. Therefore, this class should
        only be called within a try-finally clause. Alternatively the class can be used as a context manager in a with
        statement.

    :param name: Name to uniquely identify the system. The name is also used as the default system prefix.
    :param nodes: Sequence/List of Nodes, which should be used for the actions and for initializing connections.
    :param step_size: Step size (time) for the live connector in time increments.
    :param init: Nodes for initializing the system (see above).
    :param activate: Nodes for activating the system (see above).
    :param deactivate: Nodes for deactivating the system (see above).
    :param close: Nodes to close the connection and reset the system (see above).
    :param observe: Nodes to read from and return after each 'set' operation (see above).
    :param activation_indicators: Nodes that determine, whether the system must be deactivated or activated. This
                                  is used internally in conjunction with the set_value threshold to determine whether
                                  the activate/deactivate methods must be called before setting values.
    :param set_values: Specification of the node which is used for setting the main control value.
    """

    def __init__(
        self,
        nodes: Sequence[Node],
        name: str | None = None,
        step_size: TimeStep = 1,
        max_error_count: int = 10,
        *,
        init: Mapping[str, Any] | None = None,
        activate: Mapping[str, Any] | None = None,
        deactivate: Mapping[str, Any] | None = None,
        close: Mapping[str, Any] | None = None,
        observe: Sequence[str] | None = None,
        activation_indicators: Mapping[str, Any] | None = None,
        set_values: Mapping[str, Mapping[str, Any] | None] | None = None,
    ) -> None:
        #: Name of the system.
        self.name: str | None = name.strip() if name is not None else None
        #: Connection objects to the resources.
        self._connections: dict[str, Connection] = Connection.from_nodes(nodes)

        #: Mapping of all nodes.
        self._nodes: dict[str, Node] = name_map_from_node_sequence(nodes)
        #: Mapping of node names to connections.
        self._connection_map: dict[str, str] = {}
        for node in self._nodes.values():
            if node.url_parsed.netloc is not None:
                self._connection_map[node.name] = node.url_parsed.netloc
            else:
                raise ValueError(f"Node without netloc supplied: {node.name}")
        #: Start time of initialisation.
        self.start_time = time.time()
        #: Step size (time) for the live connector in time increments.
        self.step_size = int(step_size) if not isinstance(step_size, timedelta) else int(step_size.total_seconds())
        #: Current step of the live connector (number of completed steps).
        self.steps_counter: int = 0
        #: Maximum error count when connections in read/write function are aborted.
        self.max_error_count: int = max_error_count
        #: Counts the number of errors when Live Connector logs errors.
        self.error_count: list[int] = [0] * len(self._connections)

        self._init_config_nodes(activate, activation_indicators, close, deactivate, init, observe, set_values)

        if self._init_vals is not None:
            self.write(self._init_vals)

    def _init_config_nodes(
        self,
        activate: Mapping[str, Any] | None,
        activation_indicators: Mapping[str, Any] | None,
        close: Mapping[str, Any] | None,
        deactivate: Mapping[str, Any] | None,
        init: Mapping[str, Any] | None,
        observe: Sequence[str] | None,
        set_values: Mapping[str, Mapping[str, Any] | None] | None,
    ) -> None:
        errors = False
        #: Nodes for initializing the system.
        self._init_vals: dict[str, Any] | None
        self._init_vals, e = self._read_value_mapping(init, context_description="initialization")
        errors |= e
        #: Nodes for closing the connection.
        self._close_vals: dict[str, Any] | None
        self._close_vals, e = self._read_value_mapping(close, context_description="closing connection")
        errors |= e
        #: Nodes for activating the system.
        self._activate_vals: dict[str, Any] | None = {}
        self._activate_vals, e = self._read_value_mapping(
            activate, flatten=False, context_description="system activation"
        )
        errors |= e
        #: Nodes for deactivating the system.
        self._deactivate_vals: dict[str, Any] | None = {}
        self._deactivate_vals, e = self._read_value_mapping(
            deactivate, flatten=False, context_description="system deactivation"
        )
        errors |= e
        #: Nodes to observe.
        self._observe_vals: list[str] | None = [val for val in observe if val is not None] if observe else None
        if self._observe_vals and not set(self._observe_vals).issubset(self._nodes):
            missing_nodes = set(self._observe_vals) - set(self._nodes.keys())
            log.error(
                "Not all observed nodes of the object are configured as nodes. Missing nodes: "
                + ", ".join(missing_nodes)
            )
            errors = True

        #: Configuration for the step set value.
        self._set_values: dict[str, Any] | None = {}
        if set_values is not None:
            nds = set()
            setval = set_values.values() if isinstance(set_values, Mapping) else set_values
            for sys_setval in setval:
                if sys_setval is not None:
                    self._set_values[sys_setval["name"]] = sys_setval
                    nds.add(self._set_values[sys_setval["name"]]["node"])
        if not self._set_values:
            self._set_values = None
        elif not nds.issubset(self._nodes):
            missing_nodes = nds - set(self._nodes.keys())
            log.error(
                "Not all nodes required for setting control values are configured as nodes. Missing nodes: "
                + ", ".join(missing_nodes)
            )
            errors = True
        else:
            for _, set_value in self._set_values.items():
                set_value.setdefault("node", set_value["name"])
                set_value.setdefault("threshold", 0)
                set_value.setdefault("mult", 1)
                set_value.setdefault("add", 0)
                set_value.setdefault("min", None)
                set_value.setdefault("max", None)
        #: Indicator to keep track of to know whether the system must be activated or deactivated. If this is not
        #: set, the user must keep track of when the activation and deactivation functions need to be called. This
        #: may not be necessary for all systems.
        self._activation_indicators: dict[str, Any] | None = {}
        self._activation_indicators, e = self._read_value_mapping(
            activation_indicators,
            flatten=False,
            context_description="checking system activation",
        )
        if e or errors:
            raise KeyError("Not all required nodes are configured.")

    def _read_value_mapping(
        self, values: Mapping[str, Any] | None, flatten: bool = True, *, context_description: str
    ) -> tuple[dict[str, Any] | None, bool]:
        """Read a list of values and deserialize it to a mapping.

        :param values: Values to deserialize.
        :param flatten: Output into a single layer (not separated by system).
        :param context_description: Description to log if mapping fails.
        :return: Tuple of deserialized values and bool indicating an error if true.
        """
        missing_keys = set()
        _vals: dict[str, Any] = {}

        if values is not None:
            for key, sys_val in values.items():
                if isinstance(sys_val, Mapping) and flatten:
                    for k, v in sys_val.items():
                        _vals[k] = v
                elif sys_val is not None:
                    _vals[key] = sys_val

        if not _vals:
            vals = None
        else:
            vals = _vals

            if flatten:
                for key, sys_val in vals.items():
                    if sys_val and key not in self._nodes:
                        missing_keys.add(key)
            else:
                for sys_val in vals.values():
                    if sys_val and not sys_val.keys() <= self._nodes.keys():
                        missing_keys.update(sys_val.keys())
        if missing_keys:
            log.error(
                f"Nodes {', '.join(missing_keys)} required for {context_description} are missing from the node list."
            )

        return vals, bool(missing_keys)

    @classmethod
    def from_json(
        cls,
        files: Path | Sequence[Path],
        usr: str | None = None,
        pwd: str | None = None,
        step_size: TimeStep = 1,
        max_error_count: int = 10,
    ) -> LiveConnect:
        """Initialize the connection directly from JSON configuration files. The file should contain parameters
        as described above. A list of file names can be supplied to enable the creation of larger, combined systems.

        Username and password supplied as keyword arguments will take precedence over information given in
        the config file.

        :param files: Configuration file paths. Accepts a single file or a list of files.
        :param usr: Username for authentication with the resource.
        :param pwd: Password for authentication with the resource.
        :param step_size: Step size (time) for the live connector in time increments.
        :return: LiveConnect instance as specified by the JSON file.
        """
        files = [files] if not isinstance(files, Sequence) else files

        config: dict[str, list[Any]] = {"system": []}
        for file_path in files:
            file = pathlib.Path(file_path) if not isinstance(file_path, pathlib.Path) else file_path
            result = json_import(file)
            if not isinstance(result, dict):
                raise TypeError(f"JSON file {file} must define a dictionary of options.")
            if "system" in result:
                config["system"].extend(result["system"])
            else:
                config["system"].append(result)

        return cls.from_dict(usr=usr, pwd=pwd, step_size=step_size, max_error_count=max_error_count, **config)

    @classmethod
    def from_dict(
        cls,
        usr: str | None = None,
        pwd: str | None = None,
        step_size: TimeStep = 1,
        max_error_count: int = 10,
        **config: Any,
    ) -> LiveConnect:
        """Initialize the connection directly from a config dictionary. The dictionary should contain parameters
        as described above.

        Username and password supplied as keyword arguments will take precedence over information given in
        the config file.

        :param usr: Username for authentication with the resource.
        :param pwd: Password for authentication with the resource.
        :param step_size: Step size (time) for the live connector in time increments.
        :param config: Configuration dictionary.
        :return: LiveConnect instance as specified by the JSON file.
        """

        cls._check_config(config)

        # Initialize the connector objects
        _act_indicators, _actions, nodes, _observe, _set_values = cls._read_config(config, pwd, usr)
        name = config["system"][0]["name"] if len(config["system"]) == 1 else None

        return cls(
            nodes,
            name,
            step_size=step_size,
            max_error_count=max_error_count,
            init=_actions["init"],
            activate=_actions["activate"],
            deactivate=_actions["deactivate"],
            close=_actions["close"],
            observe=_observe,
            activation_indicators=_act_indicators,
            set_values=_set_values,
        )

    @classmethod
    def _check_config(cls, config: Mapping[str, Any]) -> None:
        _req_settings = {"name": {}, "servers": {"url", "protocol"}, "nodes": {"name", "server"}}
        if "system" not in config or not isinstance(config["system"], Sequence) or len(config["system"]) < 1:
            raise KeyError("Could not find a valid 'system' section in the configuration")
        # Check that all required parameters are present in config
        errors = False
        for system in config["system"]:
            for sect, required_params in _req_settings.items():
                if sect not in system:
                    log.error(f"Required parameter '{sect}' not found in configuration.")
                    errors = True
                else:
                    for name in required_params:
                        sec = system[sect].values() if isinstance(system[sect], Mapping) else system[sect]
                        for i in sec:
                            if name not in i:
                                log.error(f"Required parameter '{name}' not found in config section '{sect}'")
                                errors = True
        if errors:
            log.error("Not all required config parameters were found. Exiting.")
            sys.exit(1)

    @classmethod
    def _read_config(
        cls, config: Mapping[str, Any], pwd: str | None, usr: str | None
    ) -> tuple[
        dict[str, dict[str, Any] | None],
        dict[str, dict[str, Any]],
        list[Node],
        list[str],
        dict[str, dict[str, Any] | None],
    ]:
        # Make sure all the required sections exist - they are just none if they are not in the file.
        _nodes: list[Node] = []
        _set_values: dict[str, dict[str, Any] | None] = {}
        _act_indicators: dict[str, dict[str, Any] | None] = {}
        _observe: list[str] = []
        _actions: dict[str, dict[str, Any]] = {"activate": {}, "deactivate": {}, "init": {}, "close": {}}
        for system in config["system"]:
            # Combine config for nodes with server config and add system name to nodes
            for _node in system["nodes"]:
                n = _node.copy()
                server = system["servers"][n.pop("server")]
                if "usr" in server and "pwd" in server:
                    usr = server["usr"]
                    pwd = server["pwd"]

                _nodes.extend(
                    Node.from_dict(
                        {
                            "name": f"{system['name']}.{n.pop('name')}",
                            "url": server["url"],
                            "protocol": server["protocol"],
                            "usr": usr,
                            "pwd": pwd,
                            **n,
                        }
                    )
                )

            # Rename set_value
            if "set_value" in system and system["set_value"] is not None:
                _set_values[system["name"]] = system["set_value"].copy()
                _set_values[system["name"]]["name"] = f"{system['name']}.{system['set_value']['name']}"  # type: ignore
                _set_values[system["name"]]["node"] = (  # type: ignore
                    f"{system['name']}.{system['set_value'].get('node', system['set_value']['name'])}"
                )
            else:
                _set_values[system["name"]] = None

            # Convert activation_indicators
            if "activation_indicators" in system and system["activation_indicators"] is not None:
                act_i = {}
                for name, value in system["activation_indicators"].items():
                    act_i[f"{system['name']}.{name}"] = value
                _act_indicators[system["name"]] = act_i
            else:
                _act_indicators[system["name"]] = None

            # Convert observations
            if "observe" in system and system["observe"] is not None:
                _observe.extend(f"{system['name']}.{name}" for name in system["observe"])

            # Convert actions
            for action in ("init", "close", "activate", "deactivate"):
                if "actions" not in system or action not in system["actions"] or system["actions"][action] is None:
                    _actions[action][system["name"]] = None
                else:
                    act = {}
                    for name, value in system["actions"][action].items():
                        act[f"{system['name']}.{name}"] = value
                    _actions[action][system["name"]] = act
        return _act_indicators, _actions, _nodes, _observe, _set_values

    @property
    def nodes(self) -> Mapping[str, Node]:
        """Mapping of all node objects of the connection."""
        return self._nodes.copy()

    def _activated(self, system: str) -> bool:
        """Current activation status of the system, as determined by the activation_indicator.

        :param system: System for which activation status should be checked.
        """
        check_map = {"==": "__eq__", ">": "__gt__", "<": "__lt__", ">=": "__gte__", "<=": "__lte__"}

        # If activation_indicators are specified, read them and identify the status, otherwise the system is
        # considered to be always active.
        if self._activation_indicators is not None and system not in self._activation_indicators:
            raise KeyError(f"Cannot check status of unknown system {system}")
        if self._activation_indicators is not None and self._activation_indicators[system] is not None:
            values = self.read(*self._activation_indicators[system].keys())
            results = []
            for name, check in self._activation_indicators[system].items():
                try:
                    results.append(getattr(values[name], check_map[check["compare"]])(check["value"]))
                except KeyError as error:
                    raise KeyError(f"Unknown comparison operation {check['compare']}") from error

            activated = sum(results) >= 1
        else:
            activated = True
        return activated

    def step(self, value: Mapping[str, Any]) -> dict[str, Any]:
        """Take the set_value and determine, whether the system must be activated or deactivated. Then set the value
        and finally read and return all values as specified by the 'observe' parameter.

        :param value: Value to use as the control value/set_value.
        :return: Values read from the connection as specified by 'observe' parameter.
        """
        self.steps_counter += 1

        write = {}
        for name, val in value.items():
            n = f"{self.name}.{name}" if "." not in name and self.name is not None else name
            if self._set_values is not None and n in self._set_values:
                system, node = n.split(".")

                if (self._set_values[n]["min"] is not None and self._set_values[n]["min"] > val) or (
                    self._set_values[n]["max"] is not None and val > self._set_values[n]["max"]
                ):
                    raise ValueError(
                        f"Set value for node {n} is out of bounds. Value: {val}; "
                        f"Bounds: [{self._set_values[n]['min']}, {self._set_values[n]['max']}]."
                    )

                # Determine activation status and activate or deactivate the system correspondingly
                if val >= self._set_values[n]["threshold"]:
                    self.activate(system)
                elif val <= self._set_values[n]["threshold"]:
                    self.deactivate(system)

                write[self._set_values[n]["node"]] = (val + self._set_values[n]["add"]) * self._set_values[n]["mult"]
            else:
                write[n] = val

        # Write the scaled control value and return the observed values.
        self.write(write)

        try:
            time.sleep((self.steps_counter * self.step_size) - time.time() + self.start_time)
        except Exception:
            log.error("Step_size between write and read function is too small")

        if self._observe_vals is not None:
            return self.read(*self._observe_vals)
        return {}

    def write(self, nodes: Mapping[str, Any] | Sequence[str], values: Sequence[Any] | None = None) -> None:
        """Write any combination of nodes and values.

        :param nodes: Mapping of Nodes and values or Sequence of node names to write to.
        :param values: If nodes are given as a Sequence, this second parameter determined the values to be written.
                       If nodes are given as a Mapping, this parameter is not required. It defaults to None.
        """
        # Determine, whether nodes and values are given as a mapping in the nodes parameter or separately, using both
        # parameters. In the second case, create the mapping.
        if not isinstance(nodes, Mapping) and values is None:
            raise ValueError("Cannot only give nodes or values, specify both.")
        if not isinstance(nodes, Mapping) and values is not None and len(nodes) != len(values):
            raise ValueError(
                f"Each node must have a corresponding value for writing. "
                f"Nodes and values must be of equal length. Given lengths are"
                f"'nodes': {len(nodes)}, 'values': {len(values)}"
            )
        if not isinstance(nodes, Mapping) and values is not None:
            _nodes = dict(zip(nodes, values))
        elif isinstance(nodes, Mapping):
            _nodes = dict(nodes)

        # Sort nodes to be written by connection
        writes: dict[str, dict[Node, Any]] = {url: {} for url in self._connections}
        for name, value in _nodes.items():
            n = f"{self.name}.{name}" if "." not in name and self.name is not None else name
            writes[self._connection_map[n]][self._nodes[n]] = value

        # Write to all selected nodes for each connection
        for idx, connection in enumerate(self._connections):
            try:
                if writes[connection]:
                    self._connections[connection].write(writes[connection])
                    self.error_count[idx] = 0
            except (ConnectionError, ConTimeoutError) as e:
                if self.error_count[idx] < self.max_error_count:
                    self.error_count[idx] += 1
                    log.error(e)
                else:
                    raise

    def read(self, *nodes: str) -> dict[str, Any]:
        """Take a list of nodes and return their names and most recent values.

        :param nodes: One or more nodes to read.
        :return: Dictionary of the most current node values.
        """
        # Sort nodes to be read by connection
        node_readings: dict[str, list[Node]] = {url: [] for url in self._connections}
        _error = False
        for name in nodes:
            n = f"{self.name}.{name}" if "." not in name and self.name is not None else name
            try:
                node_readings[self._connection_map[n]].append(self._nodes[n])
            except KeyError as e:
                new_e = KeyError(f"{e.args[0]} not found in node list.")
                log.error(new_e)
                _error = True
        if _error:
            raise KeyError("Check log. One or more nodes not found in node list.")
        # Read from all selected nodes for each connection
        result = {}
        for idx, connection in enumerate(self._connections):
            try:
                if node_readings[connection]:
                    result.update(self._connections[connection].read(node_readings[connection]).iloc[0].to_dict())
                    self.error_count[idx] = 0
            except (ConnectionError, ConTimeoutError) as e:
                if self.error_count[idx] < self.max_error_count:
                    self.error_count[idx] += 1
                    result.update({name.name: np.nan for name in node_readings[connection]})
                    log.error(e)
                else:
                    raise

        return result

    def activate(self, system: str | None = None) -> None:
        """Take the list of nodes to activate and set them to the correct values to activate the system.

        :param system: System for which should be activated (default: self.name).
        """
        _system = self.name if system is None else system

        if (
            _system is not None
            and not self._activated(_system)
            and self._activate_vals is not None
            and self._activate_vals[_system] is not None
        ):
            self.write(self._activate_vals[_system])

    def deactivate(self, system: str | None = None) -> None:
        """Take the list of nodes to deactivate and set them to the correct values to deactivate the system.

        :param system: System for which should be activated (default: self.name).
        """
        _system = self.name if system is None else system

        if (
            _system is not None
            and self._activated(_system)
            and self._deactivate_vals is not None
            and self._deactivate_vals[_system] is not None
        ):
            self.write(self._deactivate_vals[_system])

    def close(self) -> None:
        """Reset the system and close the connection."""
        if self._close_vals is not None:
            self.write(self._close_vals)

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: types.TracebackType | None
    ) -> None:
        self.close()

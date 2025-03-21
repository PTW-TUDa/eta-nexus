from __future__ import annotations

import asyncio
import pathlib
import time
from collections import deque
from datetime import timedelta
from typing import TYPE_CHECKING, NamedTuple

import numpy as np
import onnxruntime
import pandas as pd

from eta_connect import get_logger
from eta_connect.connectors import (
    DFSubHandler,
    OpcUaConnection,
    name_map_from_node_sequence,
)
from eta_connect.connectors.node import NodeOpcUa
from eta_connect.servers import OpcUaServer

if TYPE_CHECKING:
    from typing import Final

    from eta_connect.type_hints import Path, TimeStep

log = get_logger(level=1)


class Config:
    #: Inference interval.
    INTERVAL: Final[int] = 1
    #: Path to the trained inference model.
    PATH_MODEL: Final[pathlib.Path] = pathlib.Path(__file__).parent / "resources/emag_gt_forecast.onnx"
    #: Shape of the inputs provided to the model.
    INPUT_SHAPE: Final[list[int]] = [1, 5, 20, 9]

    #: Path to a csv file containing normalization data.
    PATH_NORMALIZATION_DATA: Final[pathlib.Path] = pathlib.Path(__file__).parent / "resources/features_max_min.csv"
    #: Names of features used for normalization.
    FEATURES_NORMALIZATION: Final[list[str]] = [
        "WZM_VLC-100GT.972.Elek_P.L1-4",
        "WZM_VLC-100GT.972.Elek_P.KSS",
        "WZM_VLC-100GT.972.Elek_P.Ax_C1",
        "WZM_VLC-100GT.972.Elek_P.Sp3",
        "WZM_VLC-100GT.972.Elek_P.Sp4",
        "WZM_VLC-100GT.972.Elek_P.Ax_Q1",
        "WZM_VLC-100GT.972.Elek_P.Ax_X1",
        "WZM_VLC-100GT.972.Elek_P.Ax_Z1",
        "regressand",
    ]

    #: OPC Server and nodes for the input features.
    OPC_SERVER: Final[dict[str, str | int]] = {"ip": "localhost", "port": 48050}
    #: Nodes to use as input features.
    NODES: Final[list[str]] = [
        "ns=2;s=Application.GbIL4EE.powerMain",
        "ns=2;s=Application.GbIL4EE.rpowerKSS_System_ND",
        "ns=2;s=Application.GbIL4EE.powerC1",
        "ns=2;s=Application.GbIL4EE.powerSP3",
        "ns=2;s=Application.GbIL4EE.powerSP4",
        "ns=2;s=Application.GbIL4EE.powerQ1",
        "ns=2;s=Application.GbIL4EE.powerX1",
        "ns=2;s=Application.GbIL4EE.powerZ1",
    ]
    LOCAL_FILE: Final[pathlib.Path] = pathlib.Path(__file__).parent / "resources/input_features_local.csv"

    #: Name of the node for publishing the resulting data.
    PUBLISH_NAME: Final[str] = "ns=6;s=EMAG-GT-forecast.electric_power_100s"


def main() -> None:
    asyncio.get_event_loop().create_task(local_server())
    forecasting()


def forecasting() -> None:
    """Initialize and execute the forecasting loop."""

    # load maximal and minimal values of the features for normalization
    features_max, features_min = load_normalization_params(
        Config.PATH_NORMALIZATION_DATA, Config.FEATURES_NORMALIZATION
    )

    # Create input connections
    connection = OpcUaConnection.from_ids(
        Config.NODES, f"opc.tcp://{Config.OPC_SERVER['ip']}:{Config.OPC_SERVER['port']}"
    )
    sub_handler = DFSubHandler(write_interval=Config.INTERVAL, size_limit=100, auto_fillna=False)
    connection.subscribe(sub_handler, interval=Config.INTERVAL)

    # Create loop and inference tasks
    loop = asyncio.get_event_loop()
    data_queue: asyncio.Queue = asyncio.Queue()

    running_tasks = set()
    read_data_task = loop.create_task(read_data_loop(sub_handler, data_queue, Config.INPUT_SHAPE[-1], Config.INTERVAL))
    running_tasks.add(read_data_task)
    inference_task = loop.create_task(
        inference_loop(
            Config.PATH_MODEL, data_queue, Config.PUBLISH_NAME, Config.INPUT_SHAPE, features_min, features_max
        )
    )
    running_tasks.add(inference_task)

    try:
        log.info("Starting processing loop.")
        loop.run_forever()
    except KeyboardInterrupt:
        loop.stop()
        log.warning("Keyboard Interrupt. Stopping inference.")


async def local_server() -> None:
    data = pd.read_csv(Config.LOCAL_FILE, sep=";", decimal=",")
    current_line = 0

    # initialize the server
    nodes: list[NodeOpcUa] = [
        NodeOpcUa(
            name=name,
            url=f"opc.tcp://{Config.OPC_SERVER['ip']}:{Config.OPC_SERVER['port']}",
            protocol="opcua",
            opc_id=name,
            dtype="float",
        )
        for name in data.columns
    ]
    server = OpcUaServer(namespace=2, ip=str(Config.OPC_SERVER["ip"]), port=int(Config.OPC_SERVER["port"]))
    server.create_nodes(nodes)
    node_map: dict[str, NodeOpcUa] = name_map_from_node_sequence(nodes)  # type: ignore
    while True:
        server.write({node_map[name]: value for name, value in data.iloc[current_line].items()})
        current_line = current_line + 1 if current_line < len(data) else 0
        await asyncio.sleep(1)


def load_normalization_params(csv_file: Path, features: list[str]) -> tuple[list, list]:
    """Get minimum and maximum values of features for normalization and inverse normalization.

    :param csv_file: Path to csv file that includes min max values saved from past data.
    :param features: List of feature names used for normalization.
    :returns: List of max values, list of min values
    """

    min_max = pd.read_csv(csv_file, header=0, index_col=0)

    features_max = [min_max.get(feature).to_numpy()[0] for feature in features]
    features_min = [min_max.get(feature).to_numpy()[1] for feature in features]

    return features_max, features_min


async def read_data_loop(
    sub_handler: DFSubHandler, data_queue: asyncio.Queue, expected_values: int, interval: TimeStep
) -> None:
    """Read data from a data subscription and adjust the format to correspond to input shape requirements.

    :param sub_handler: Subscription Handler to read data from.
    :param data_queue: Queue to put the collected data into.
    :param expected_values: Number of values to expect from the subscription handler.
    :param interval: Interval for requesting data from the subscription.
    """
    _interval = interval.total_seconds() if isinstance(interval, timedelta) else interval

    class InputData(NamedTuple):
        date: str
        data: list[float]

    while True:
        start_time = time.time()

        async def sleep(_start_time: float) -> None:
            # Log timing and wait for next loop
            finish_time = time.time()
            log.debug(f"Time used in read loop: {finish_time - _start_time:.4f} s")
            await asyncio.sleep(_start_time + _interval - finish_time)

        data = sub_handler.get_latest()
        if data is None:
            await sleep(start_time)
            continue

        date = data.index[-1]
        adjusted_data = [np.nan_to_num(data.loc[date, col]) for col in data.columns]
        adjusted_data.append(sum(adjusted_data))  # Calculate and append the regressand

        if len(adjusted_data) != expected_values:
            await sleep(start_time)
            continue

        await data_queue.put(InputData(date.to_pydatetime(), adjusted_data))
        await sleep(start_time)


async def inference_loop(
    model_path: Path,
    data_queue: asyncio.Queue,
    publish_name: str,
    input_shape: list,
    features_min: list[float],
    features_max: list[float],
) -> None:
    """Asynchronous task for value inference using the ONNX runtime.

    :param model_path: Path to the stored ONNX inference model.
    :param data_queue: Queue to receive historical data.
    :param publish_name: Name of the OPC UA node for publishing the data.
    :param input_shape: Input shape expected by ONNX model.
    :param features_min: Minimum values of features, used for normalization of input features.
    :param features_max: Maximum values of features, used for normalization of input features.
    """
    maxlen = 100
    # initialize inference with onnxruntime
    session = onnxruntime.InferenceSession(str(model_path), onnxruntime.SessionOptions())
    log.info("Starting inference with ONNX-Runtime.")

    model_input_list: deque = deque(maxlen=maxlen)

    output_node = NodeOpcUa(
        name="EMAG-GT-forecast-opcua",
        url="opc.tcp://localhost",
        protocol="opcua",
        opc_id=publish_name,
    )
    with OpcUaServer(namespace=6, ip="localhost") as output_server:
        output_server.create_nodes({output_node})

        while True:
            data = await data_queue.get()
            start_time = time.time()

            # Normalize and append data and check whether enough historic data is available for inference
            model_input_list.append([(a - b) / (c - b) for a, b, c in zip(data.data, features_min, features_max)])
            if len(model_input_list) < maxlen:
                log.info(f"Not enough input data. Need {maxlen - len(model_input_list)} more lines.")
                continue

            # Perform the prediction
            inferred_value = session.run(
                None, {session.get_inputs()[0].name: np.array(model_input_list, dtype=np.float32).reshape(input_shape)}
            )[0][0][0]
            log.info(f"ONNX predicted value: {inferred_value}")

            # De-Normalized the prediction
            inverse_prediction = inferred_value * (features_max[-1] - features_min[-1]) + features_min[-1]
            log.info(f"Inverse predicted value: {inverse_prediction}")
            log.debug(f"Time used for inference: {time.time() - start_time:.4f} s")

            # Publish results to OPC UA server
            output_server.write({output_node: inverse_prediction})
            log.info("Value written to OPC UA server")


if __name__ == "__main__":
    main()

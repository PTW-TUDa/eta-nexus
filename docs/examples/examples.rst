.. _examples:

Usage examples
================
*eta_connect* contains example implementations for different usages of the package.
This page gives a short overview of the examples.

Connections
--------------
There are two examples for the *connections*: The *read_series_eneffco* example illustrates a simple usage of the *connections* module. It selects some data points and reads them as series data from the server.

The *data_recorder* example is more complex in that it uses multiple *connections*, can connect to different protocols and provides a command line interface for
configuration.

In addition to these features, the DataRecorder offers both a graphical user interface (GUI) and a command-line interface. It allows data retrieval from various servers within the ETA-Factory and can output the data as CSV files.

You can access the DataRecorder at: (https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-datarecorder).

Forecasting
--------------
The *forecasting* example demonstrates how a machine learning model can be deployed using
the *connections* module to connect to data sources (in this example OPC UA). The model is a load forecasting
model of a machine tool in the ETA research factory. It forecasts the electric load of the machine tool during
the next 100 seconds. Input data is a time window of the last 100 seconds of 8 separate electric load signals
of sub-components of the machine tool as well as the total electric load of the machine tool. The model was
exported into ONNX format and is deployed using the *onnxruntime* module. The forecast is published to an
OPC UA server that is established on the local machine using the *servers* module.

    In the example, data is collected for 100 seconds in an internal memory. Once enough time steps are present, the
    inference is triggered and the forecast is published to the OPC UA server. This loop is repeated every second.

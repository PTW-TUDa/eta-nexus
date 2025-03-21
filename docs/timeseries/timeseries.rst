.. _timeseries:

Timeseries
===============
Many *eta_connect* functions and classes operate on timeseries data and :py:class:`pandas.DataFrame` objects
containing timeseries data. The *timeseries* module in *eta_connect* provides some additional functionality for both.
It can for example find random time slices in Dataframes or import timeseries data from multiple CSV files and map
a (random if required) section of it into a Dataframe.

Scenario Data Loader
-----------------------
Scenario data is often required to perform optimizations and simulations of factory systems. The import function
can import data from multiple files and returns a cleaned Dataframe.

.. autofunction:: eta_connect.timeseries::scenario_from_csv
    :noindex:

Extensions for pandas.DataFrame
------------------------------------

.. automodule:: eta_connect.timeseries.dataframes
    :members:
    :noindex:

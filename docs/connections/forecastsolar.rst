.. _forecast_solar_connection:

Forecastsolar Connection
====================================================
This module provides a read-only REST API connection to the forecast.solar API.

You can obtain an estimate of solar production for a specific location, defined by latitude and longitude,
and a specific plane orientation, defined by declination and azimuth, based on the installed module power.

Supported endpoints include: "Estimate", "Historic", and "Clearsky":

**Estimate Solar Production**
The `estimate` endpoint provides the forecast for today and the upcoming days, depending on the account model.

**Historic Solar Production**
The `historic` endpoint calculates the average solar production for a given day based on historical weather data,
excluding current weather conditions.

**Clear Sky Solar Production**
The `clearsky` endpoint calculates the theoretically possible solar production assuming no cloud cover.

For more information, visit the `forecast.solar API documentation <https://doc.forecast.solar/start>`_.

========================================================================================================

ForecastsolarConnection
----------------------------------------------------

.. autoclass:: eta_connect.connections::ForecastsolarConnection
    :members:
    :noindex:

========================================================================================================

ForecastsolarNode
----------------------------------------------------
.. autoclass:: eta_connect.nodes::ForecastsolarNode
    :members:
    :noindex:

========================================================================================================

Example Usage
----------------------------------------------------

Simple node without API key:

.. literalinclude:: ../../examples/connections/read_series_forecast_solar.py
    :start-after: --begin_forecast_solar_doc_example1--
    :end-before: --end_forecast_solar_doc_example1--
    :dedent:

Node with api key and multiple planes:

.. literalinclude:: ../../examples/connections/read_series_forecast_solar.py
    :start-after: --begin_forecast_solar_doc_example2--
    :end-before: --end_forecast_solar_doc_example2--
    :dedent:

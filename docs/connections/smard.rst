.. _smard_connection:

SMARD Connection
====================================================
This module provides a read-only REST API connection to the SMARD (Strommarktdaten) API
from Bundesnetzagentur (German Federal Network Agency).

You can access comprehensive German electricity market data including power generation by source,
consumption patterns, market prices, and generation forecasts. The API provides historical data
from 2015 onwards with multiple time resolutions.

**Available Data Categories:**

**Power Generation by Source**
Access generation data for various energy sources including:

- Solar (Photovoltaik)
- Wind (Onshore and Offshore)
- Nuclear
- Coal (Lignite and Hard Coal)
- Natural Gas
- Hydro
- Biomass
- Pumped Storage

**Power Consumption**
Track electricity consumption including:

- Total Load
- Residual Load
- Pumped Storage Consumption

**Market Prices**
View electricity market prices for:

- Germany/Luxembourg
- Neighboring Countries
- Austria, Belgium, Norway, and others

**Generation Forecasts**
Access forecasts for:

- Solar Generation
- Wind Generation (Onshore and Offshore)
- Total Generation

**Key Features:**

- No authentication required (public API)
- Multiple time resolutions: 15min, hour, day, week, month, year
- Geographic coverage: Germany, Austria, Luxembourg
- Data available from 2015 onwards
- Automatic caching for improved performance


For more information, visit the `SMARD website <https://www.smard.de/home>`_.
For detailed API specifications and endpoints, refer to the `OpenAPI specification <https://smard.api.bund.dev/>`_.

========================================================================================================

SmardConnection
----------------------------------------------------

.. autoclass:: eta_nexus.connections::SmardConnection
    :members:
    :noindex:

========================================================================================================

SmardNode
----------------------------------------------------
.. autoclass:: eta_nexus.nodes::SmardNode
    :members:
    :noindex:

========================================================================================================

Example Usage
----------------------------------------------------

Reading solar power generation data for Germany:

.. literalinclude:: ../../examples/connections/read_series_smard.py
    :start-after: --begin_smard_doc_example--
    :end-before: --end_smard_doc_example--
    :dedent:

========================================================================================================

Available Filters
----------------------------------------------------

**Power Generation Filters:**

- ``lignite`` (1223): Lignite power generation
- ``nuclear`` (1224): Nuclear power generation
- ``wind_offshore`` (1225): Offshore wind generation
- ``hydro`` (1226): Hydroelectric generation
- ``other_conventional`` (1227): Other conventional sources
- ``other_renewable`` (1228): Other renewable sources
- ``biomass`` (4066): Biomass generation
- ``wind_onshore`` (4067): Onshore wind generation
- ``solar`` (4068): Solar/Photovoltaic generation
- ``hard_coal`` (4069): Hard coal generation
- ``pumped_storage_generation`` (4070): Pumped storage generation
- ``natural_gas`` (4071): Natural gas generation

**Power Consumption Filters:**

- ``total_load`` (410): Total electricity consumption
- ``residual_load`` (4359): Residual load
- ``pumped_storage_consumption`` (4387): Pumped storage consumption

**Market Price Filters:**

- ``de_lu`` (4169): Germany/Luxembourg market price
- ``neighbors_de_lu`` (5078): Neighboring countries to DE/LU
- ``belgium`` (4996): Belgium market price
- ``norway_2`` (4997): Norway market price
- ``austria`` (4170): Austria market price

**Forecast Filters:**

- ``offshore_forecast`` (3791): Offshore wind forecast
- ``onshore_forecast`` (123): Onshore wind forecast
- ``solar_forecast`` (125): Solar generation forecast
- ``other_forecast`` (715): Other sources forecast
- ``wind_solar_forecast`` (5097): Combined wind and solar forecast
- ``total_forecast`` (122): Total generation forecast

========================================================================================================

Supported Regions
----------------------------------------------------

- ``DE``: Germany
- ``AT``: Austria
- ``LU``: Luxembourg
- ``DE-LU``: Germany and Luxembourg combined
- ``DE-AT-LU``: Germany, Austria, and Luxembourg combined
- ``50Hertz``: 50Hertz control area
- ``Amprion``: Amprion control area
- ``TenneT``: TenneT control area
- ``TransnetBW``: TransnetBW control area
- ``APG``: Austrian Power Grid
- ``Creos``: Creos Luxembourg

========================================================================================================

Time Resolutions
----------------------------------------------------

- ``quarterhour``: 15-minute intervals
- ``hour``: Hourly data
- ``day``: Daily aggregates
- ``week``: Weekly aggregates
- ``month``: Monthly aggregates
- ``year``: Yearly aggregates

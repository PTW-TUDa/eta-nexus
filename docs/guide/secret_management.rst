.. _secret_management:

Secret Management
=====================================

ETA Nexus supports loading environment variables from a `.env` file for convenience
when working in local development or with experiments.

This is especially useful when storing sensitive information like API tokens for services such as Entso-e, ForecastSolar, or EnEffco.

How Environment Variables Are Loaded
-------------------------------------

In your custom experiment scripts, you can load variables from a `.env` file by calling:

.. code-block:: python

   from eta_nexus.util import autoload_env

   autoload_env()

This will look for a `.env` file in the current working directory or its parents,
and load variables **without overriding** existing environment variables.

.. note::

   The main ETA Nexus package **does not automatically load `.env` files** to avoid unexpected behavior.

Usage in Experiment Template
------------------------------

If you use `ETA-Experiment Project <https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/templates/eta-experiment-project>`_ template, environment variables are loaded automatically when the experiment runs.
You don't need to call ``autoload_env()`` manually in that case.

Example `.env` file:

.. code-block::

    ENEFFCO_API_TOKEN=your_api_token
    FORECAST_SOLAR_API_TOKEN=your_api_token
    ENTSOE_API_TOKEN=your_api_token


.. warning::

    Never commit your `.env` file to your repository.
    In the template, `.env` is already included in the `.gitignore`.

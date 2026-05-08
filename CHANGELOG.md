# Release 0.2.0

This release brings REST API connections to eta-nexus! The first implemented REST API connection class is to
the [SMARD API](https://smard.api.bund.dev/). Additionally, connections to [InfluxDB](https://www.influxdata.com/)
are now possible. Of course this releases also brings bug-fixes, test-optimizations and pipeline-fixes and -updates.

## New Features

- Added a generic REST API connection class with request retrying
  mechanism. ([!50](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/50), [!
  72](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/72))
  @Hailu_M
    - Added [SMARD API](https://smard.api.bund.dev/) Connector with
      documentation. ([!63](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/63))
      @Hailu_M
    - Added generic `read_node` to unify common functionality observed through existing REST
      connectors. ([!59](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/59))
      @Hailu_M
- Added [InfluxDB](https://www.influxdata.com/) Connector with
  documentation. ([!37](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/37))
  @A.Clement, ([!57](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/57), [!
  58](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/58))
  @Hasan_S
- Added a guide for implementing new connector
  classes. ([!64](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/64))
  @Hailu_M
- Added support and tests for creating both Opcua and Modbus servers from the same configuration
  file. ([!51](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/51), [!56]
  (https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/56))
  @J.Chen

## Bug Fixes

- Enhanced error handling and messages across all file I/O
  operations. ([!69](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/69))
  @Hailu_M
- Added type mismatch detection for Opcua
  connections. ([!68](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/68))
  @Hailu_M
- Connection Manager now pulls input nodes from observe_value-section of the config
  file. ([!53](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/53)) @J.Stock

## Breaking Changes

- Renamed status protocols and subscription handlers for clearer semantic
  differentiation ([!65](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/65))
  @J.Stock
    - Protocols: `Readable/Writable/Subscribable` → `StatusReadable/StatusWritable/StatusSubscribable`.
    - Subscription handler module/class:
        - `eta_nexus.subhandlers.*` → `eta_nexus.subscription_handlers.*`
        - `CsvSubHandler/DFSubHandler/MultiSubHandler` →
          `CsvSubscriptionHandler/DFSubscriptionHandler/MultiSubscriptionHandler`.

## Internal Changes

- Added parallel test execution and optimized test
  performance/duration. ([!70](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/70), [!71](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/71))
  @Hailu_M
- Pipeline Fixes and
  Optimizations ([!67](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/67), [!74](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/74), [!77](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/77))
  @Hailu_M
- Moved from custom-built REST-mocking to
  pytest-recording/VCR ([!76](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/76))
  @Hailu_M
- Removed examples from wheel
  distribution ([!52](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/52))
  @Balzer_J

## Other

- Bump
  dependencies ([!54](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/54))
  @Balzer_J

---

# Release 0.1.1

This is minor hotfix-release to make ETA Nexus compatible
with [ETA Utility](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-utility).

## Bug Fixes

- Added dependency compatibility with
  eta-utility ([!48](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/48))
  @Balzer_J

---

# Release 0.1.0

Besides bug-fixes and changes under the hood, this release brings three major changes to the package:

- Project rename – the library is now officially called **ETA Nexus** throughout the code and documentation.
- **Migration from eta_utility** – the project now uses its own internal implementation, removing the legacy dependency
  and simplifying the code base.
- **Redesign of the `Connection` class hierarchy** – a new, clearer class structure for all connection types, with
  deprecated code removed.

Furthermore, new notable features are **OPC UA server** creation through the connection-manager, **secret-management**
and
big **documentation** updates.

## New Features

- Added the ability to create an OPC UA server directly from a connection‑manager
  file. ([!39](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/39)) – @J.Chen
- Implemented secret‑management
  support. ([!24](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/24)) –
  @Balzer_J
- Added a **Pyenv + Poetry** guide to the documentation to help set up a reproducible Python
  environment. ([!19](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/19)) –
  @Balzer_J

## Bug Fixes

- Fixed an extra, unintended specification in `pyproject.toml` that caused packaging
  issues. ([!46](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/46)) –
  @Balzer_J
- Corrected `load_config` so that it respects the explicitly provided file extension instead of preferring `.json`/
  `.toml`. ([!40](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/40)) –
  @J.Chen
- Fixed inconsistent timezone handling in `read_series`, ensuring timestamps are interpreted
  correctly. ([!35](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/35)) –
  @Hailu_M
- Added missing 15‑minute price data for the DEU‑LUX day‑ahead market
  query. ([!38](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/38)) –
  @Hailu_M
- Removed redundant HTTP‑error and URL logging in
  `_raw_request`. ([!30](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/30)) –
  @Hailu_M
- Cleaned up connection subclasses by deleting unnecessary `_validate_nodes`
  overrides. ([!26](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/26)) –
  @J.Chen
- Added handling for `HTTPError` in `_raw_request` and related methods to prevent uncaught
  exceptions. ([!25](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/25)) –
  @J.Chen
- Fixed `ConnectionManager.from_config` so it can be called with a string path to a configuration
  file. ([!21](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/21)) –
  @Balzer_J

## Breaking Changes

- Redesigned the **Connection** class hierarchy, introducing a new structure for connection
  handling. ([!10](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/10)) –
  @A.Clement
- Removed the outdated "Python and git installation" documentation
  pages. ([!22](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/22)) –
  @Balzer_J
- Re‑structured the **LiveConnect** component, changing its public
  API. ([!6](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/6)) – @Balzer_J
- Renamed the project from *ETA* to **ETA Nexus** throughout the codebase and
  documentation. ([!17](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/17)) –
  @Balzer_J
- Deleted all code marked as `@deprecated` in the various classes, cleaning up the public
  interface. ([!13](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/13)) –
  @J.Stock
- Re‑organized the **Connection** and **Node** files, moving them into a new package
  layout. ([!9](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/9)) –
  @Balzer_J
- Migrated the project away from the legacy `eta_utility` package to the new internal
  implementation. ([!1](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/1)) –
  @Balzer_J

## Internal Changes

- Removed an obsolete Sphinx link from the
  documentation. ([!43](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/43)) –
  @J.Stock
- Follow‑up work on specifying the available data types for nodes, improving type
  safety. ([!36](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/36)) –
  @Hailu_M
- Defined the set of data types that each node can provide, clarifying the API
  contract. ([!14](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/14)) –
  @Balzer_J
- Updated the test suite to reflect the new package
  structure. ([!18](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/18)) –
  @Balzer_J
- Added a user‑story template for issue tracking and enhanced existing issue
  templates. ([!32](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/32)) –
  @Hailu_M
- Replaced direct usage of the `requests` library with `requests_cache` to enable transparent HTTP
  caching. ([!29](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/29)) –
  @Hailu_M
- Streamlined imports from the `wetterdienst` package to reduce import
  overhead. ([!27](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/27)) –
  @Balzer_J
- Copied and refactored ENTSO‑E related changes from the former `eta_utility`
  repository. ([!16](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/16)) –
  @Balzer_J
- Integrated the `DFSubhandler` updates from the `eta‑utility`
  release. ([!20](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/20)) –
  @Balzer_J
- Moved Modbus utility functions into the dedicated Modbus node
  module. ([!12](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/12)) –
  @Balzer_J
- Updated the project's **ruff** linting rules to the latest
  standards. ([!15](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/15)) –
  @Balzer_J
- Switched the dependency specification in `pyproject.toml` to Poetry’s default markup
  format. ([!8](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/8)) –
  @A.Clement
- Refreshed the `README` and `AUTHORS` files with up‑to‑date project
  information. ([!5](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/5)) –
  @Balzer_J
- Drafted an initial version of the “Adjust documentation” merge request, laying groundwork for future doc
  improvements. ([!3](https://git.ptw.maschinenbau.tu-darmstadt.de/eta-fabrik/public/eta-nexus/-/merge_requests/3)) –
  @Balzer_J
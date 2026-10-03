# Controller and worker diagnostics

Optional diagnostics use the same B.U.N.N.Y. structured record and OpenTelemetry trace fields as the Hub and Pixoo. The [host observability specification](../openspec/specs/host-observability/spec.md) owns the behavior. This is source support; it does not enable a personal service or qualify physical lights.

## Enable for an explicit launch

Install the pinned `requirements-controller.txt` into the Python environment used for that source checkout. Disabled diagnostics do not import the optional telemetry dependencies. The following settings apply only to the command being launched; replace the paths and port with the separately selected runtime and local Collector:

```bash
BUNNY_DIAGNOSTICS=1 BUNNY_TRACING=1 BUNNY_OTLP_ORIGIN=http://127.0.0.1:4318 \
  python3 bridge/bridge.py controller-serve --state-dir /path/to/selected-state --port 41231
```

`BUNNY_DIAGNOSTICS=1` enables INFO-and-above logs. Controller logs use stderr, keeping existing command output separate. `BUNNY_OTLP_ORIGIN` optionally exports logs to a numeric loopback HTTP Collector. `BUNNY_TRACING=1` also enables traces and requires that Collector setting; new roots use 10% head sampling. An authenticated sampled parent retains its sampling decision. No global provider or automatic instrumentation is installed.

The same settings can be applied to an explicit `worker --state-dir ... --device ...` launch. Workers launched by the controller inherit its process environment. Detached workers require `BUNNY_OTLP_ORIGIN`: their existing stdout/stderr remain discarded, and the shared bounded exporter is their diagnostic sink. A worker started by a hook or another process receives that process's environment, not the controller's settings. Hook behavior and personal service configuration are unchanged.

Unset `BUNNY_DIAGNOSTICS` to disable both signals. Invalid optional configuration or an unavailable dependency leaves diagnostics inert; the domain operation still runs. A stopped Collector loses diagnostics rather than delaying or retrying device commands. Check the Collector and launch environment when expected records are missing.

## Read the records

Filter by `service.name=nanoleaf-controller` or `nanoleaf-worker`. Common fields include `event_name`, `bunny.operation`, `bunny.outcome`, `bunny.ticket.epoch`, `bunny.ticket.sequence`, `trace_id` and `span_id`. Use the existing local Grafana log and trace query workflow.

Controller coverage includes process startup/shutdown/errors, authenticated HTTP processing and command response outcomes. Traceparent is accepted only after the existing machine authentication and Host/Origin checks. No baggage, tracestate, raw URLs, command bodies or exception text is exported.

Worker coverage includes startup/shutdown/pass errors, native mode/power/brightness/scene execution, and idle restoration through the existing scene sender. Rendering frames, browser events, hook events and exhaustive helper coverage are deferred. There is no new light writer.

An operation span describes execution of a function. A `command.*` record describes the actual receipt: queued, cancelled, failed, partial, uncertain or transport-acknowledged. A normally returned handler does not mean its command succeeded. Transport acknowledgment does not prove physical light output. Worker tickets come from the existing ledger; persisted work starts a new trace because the ledger carries no trace context. Join controller and worker records by ticket instead of assuming cross-process trace ancestry.

## Bounds and source checks

The shared runtime limits each signal to 1,024 queued records or 4 MiB, with an 8 KiB record limit, drop-newest behavior and a one-second combined flush budget. Loss and transport failures are available from the injected host's `counts()` in synthetic tests. No disk spool, automatic command retry or domain retention change is added. Numerical performance qualification remains deferred; revisit the limits when actual volume or resource use warrants it.

Run `python3 -m unittest discover -s tests -p test_observability.py` for copied-package conformance, disabled operation, request correlation, fake worker results and sink-failure checks. The normal `python3 scripts/check.py` discovers these tests in both Python CI jobs. API changes also run the browser and verification checks in [development](development.md).

The immutable artifact is observability 1.1.0 from [Hub PR736](https://github.com/jimmie-potts/agent-device-hub/pull/736), revision `4c23b0171e4ae3ea5537ebe81cd65dae265c8a47`. Its archive, manifest, files and producer receipt live under `bridge/vendor/observability-1.1.0`. The loader verifies the pinned archive and manifest hashes and every manifest file before loading; tests also reject modified copied bytes. No producer checkout is required.

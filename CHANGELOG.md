# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release of asimov-lalinference plugin
- LALInference pipeline integration for Asimov 0.7+
- Scheduler-agnostic (HTCondor/Slurm) DAG submission via `self.scheduler.submit_dag(...)`
- `LALInferencePriorInterface` / `get_prior_interface()`, mirroring the sibling pattern
  in asimov core's `bilby.py`, wired into a bundled `config_template` (ported from
  asimov core's now-removed `asimov/configs/lalinference.ini`) so `asimov manage build`
  can render a production's `.ini` directly from ledger meta-data
- `sampler.nlive` / `sampler.tolerance` / `sampler.maxmcmc` / `sampler.neff` /
  `sampler.ntemps` are now configurable per-production in the bundled config template
  (previously hard-coded in asimov core's template); all default to the original values
  when omitted
- `collect_assets()`, so a downstream production (e.g. a PESummary post-processing
  production wired up via `needs:`) can pick up this pipeline's samples/config through
  `production._previous_assets()`
- Result collection and asset management
- Unit test suite (`tests/test_lalinference.py`)
- A genuine end-to-end test (`.github/workflows/e2e.yml`): real `lalinference_pipe` DAG
  generation and real HTCondor execution (engine, merge) against LALInference's own
  built-in simulated ("fake-cache") Gaussian noise, waiting for a real
  `posterior_samples/posterior_*.hdf5` file — not a smoke test
- `[asimov]` optional dependency group for explicit asimov integration

### Changed
- Extracted LALInference integration from Asimov core into standalone plugin
- Removed a self-referential deprecation warning from `__init__` (it announced that this
  functionality would move to an external package — which this package now is)
- Updated version constraint to require asimov>=0.7
- Bumped `requires-python` to `>=3.10`, matching the conda-forge `lalinference` feedstock,
  which does not build for older Pythons

### Fixed
- `after_completion()` called `self.run_pesummary()`, a method that has never existed
  anywhere in this class or its parents. It now looks up the `pesummary` pipeline via the
  `asimov.pipelines` entry-point group instead (the same pattern asimov core's `bilby.py`
  and `rift.py` use), raising a clear `PipelineException` if the `asimov-pesummary` plugin
  isn't installed rather than crashing with an opaque `AttributeError`
- `submit_dag()` now uses `self.scheduler.submit_dag(...)` (asimov's scheduler-agnostic
  API) instead of shelling out to `condor_submit_dag` directly, which also gets this
  plugin Slurm support
- `build_dag()` now resolves `production.rundir` to an absolute path before changing the
  working directory, and raises a clear `PipelineException` (rather than an uncaught
  `FileNotFoundError`) if `lalinference_pipe` can't be found
- Updated dependency constraint to support asimov 0.7

## [0.1.0] - TBD

### Added
- First public release

[Unreleased]: https://github.com/transientlunatic/asimov-lalinference/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/transientlunatic/asimov-lalinference/releases/tag/v0.1.0

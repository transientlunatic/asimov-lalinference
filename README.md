# asimov-lalinference

LALInference pipeline integration for [Asimov](https://github.com/etive-io/asimov).

This package provides a plugin for Asimov 0.7+ that enables integration with the LALInference parameter estimation pipeline for gravitational wave data analysis.

> [!WARNING]
> LALInference has been superseded by newer sampling pipelines (bilby, RIFT) and this
> integration is not fully reviewed. It **must not** be used for collaboration parameter
> estimation analyses. It remains useful for cross-checks and for replicating older
> analyses.

## Features

- 🔌 **Plugin Architecture**: Seamlessly integrates with Asimov via entry points
- 🚀 **Scheduler-agnostic**: Automated DAG generation and job submission via Asimov's
  HTCondor/Slurm scheduler API
- 📈 **Result Collection**: Automatic collection of posterior samples and results
- 🧪 **Well Tested**: Unit tests plus a genuine end-to-end test (real `lalinference_pipe`
  DAG generation and HTCondor execution against LALInference's own simulated noise)

## Installation

LALInference itself is only distributed via conda-forge — there is no PyPI wheel for it —
so installing this plugin is a two-step process:

```bash
conda install -c conda-forge lalinference
pip install asimov-lalinference
```

### From Source

```bash
conda install -c conda-forge lalinference
git clone https://github.com/transientlunatic/asimov-lalinference.git
cd asimov-lalinference
pip install -e .
```

### For Development

```bash
pip install -e ".[docs,test]"
```

## Quick Start

Once installed (alongside a working `lalinference_pipe`, from the conda-forge `lalinference`
package), the LALInference pipeline is automatically available in Asimov via its entry-point
registry — no further configuration is required beyond a normal Asimov production blueprint.
See the [documentation](docs/index.rst) for a full example blueprint.

## Requirements

- Python >= 3.10 (the conda-forge `lalinference` feedstock does not build for older Pythons)
- asimov >= 0.7.0
- `conda-forge::lalinference` — install separately with `conda install -c conda-forge lalinference`
  (there is no `asimov[gw]` extra in asimov core today that would pull this in automatically;
  each GW pipeline plugin, including this one, currently needs to be installed explicitly)

## Operational notes

### HTCondor pools without an IGWN-style job wrapper

`lalinference_pipe` generates a small `lalinf_touch_output` placeholder script per engine
node and wires it in via custom `+PreCmd`/`+PreArguments` job classads, so that any
declared output file the real executable doesn't happen to write for a given run (e.g. the
SNR summary file, which isn't always produced) still exists as an empty placeholder by the
time HTCondor transfers job outputs — otherwise the transfer hard-fails with something like:

```
Transfer output files failure ... Details: 1 total failures: first failure: reading from
file .../lalinferencenest-...-1.hdf5_snr.txt: (errno 2) No such file or directory
```

`+`-prefixed classads aren't a native HTCondor pre-exec hook — real IGWN/LIGO condor pools
apparently have a `USER_JOB_WRAPPER` configured site-wide that interprets this convention,
but a vanilla HTCondor install (e.g. the `htcondor/mini` test image this repo's own CI uses,
or your own self-hosted pool) does not, and `lalinf_touch_output` silently never runs. If
you hit the error above on a pool you control, configure a `USER_JOB_WRAPPER` that reads
`PreCmd`/`PreArguments` off the job ad (available via the `$_CONDOR_JOB_AD` file HTCondor
provides to every job) and runs it before the real executable — see
`.github/workflows/e2e.yml` in this repo for a working example.

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please see CONTRIBUTING.md for guidelines.

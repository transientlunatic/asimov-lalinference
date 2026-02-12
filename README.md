# asimov-lalinference

LALInference pipeline integration for [Asimov](https://git.ligo.org/asimov/asimov).

This package provides a plugin for Asimov 0.7+ that enables integration with the LALInference parameter estimation pipeline for gravitational wave data analysis.

## Features

- 🔌 **Plugin Architecture**: Seamlessly integrates with Asimov via entry points
- 🚀 **HTCondor Integration**: Automated DAG generation and job submission
- 📈 **Result Collection**: Automatic collection of posterior samples and results
- 🧪 **Well Tested**: Comprehensive unit test coverage

## Installation

### Via Asimov (Recommended)

If you have asimov 0.7+, you can install gravitational wave pipelines including LALInference with:

```bash
pip install asimov[gw]
```

This will automatically install asimov-lalinference and other GW analysis plugins.

### From PyPI (when released)

```bash
pip install asimov-lalinference
```

### From Source

```bash
git clone https://git.ligo.org/asimov/asimov-lalinference.git
cd asimov-lalinference
pip install -e .
```

### For Development

```bash
pip install -e ".[docs,test]"
```

## Quick Start

Once installed, the LALInference pipeline is automatically available in Asimov.

## Requirements

- Python >= 3.9
- asimov >= 0.7.0
- LALInference (must be installed separately)

## License

MIT License - see LICENSE file for details.

## Contributing

Contributions are welcome! Please see CONTRIBUTING.md for guidelines.

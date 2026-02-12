# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial release of asimov-lalinference plugin
- LALInference pipeline integration for Asimov 0.7+
- HTCondor DAG generation and submission
- Result collection and asset management
- Comprehensive test suite
- `[asimov]` optional dependency group for explicit asimov integration

### Changed
- Extracted LALInference integration from Asimov core into standalone plugin
- Removed deprecation warning from Asimov 0.6
- Updated version constraint to require asimov>=0.7

### Fixed
- Updated dependency constraint to support asimov 0.7

## [0.1.0] - TBD

### Added
- First public release

[Unreleased]: https://git.ligo.org/asimov/asimov-lalinference/compare/v0.1.0...HEAD
[0.1.0]: https://git.ligo.org/asimov/asimov-lalinference/releases/tag/v0.1.0

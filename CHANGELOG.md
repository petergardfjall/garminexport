# Changelog

## [unreleased]

### New features

- feat: add gear support (#2- @drewbrew)

### Improvements and bug fixes

fix(auth): add support for setting auth header and cookie manually (#1 - @ryeguard)
fix: correct string formatting in GaveUpError message ([b8dc7d5](https://github.com/garminexport/garminexport/commit/b8dc7d534ccddf85856736decde6734f6c177de6) - @JakobLichterfeld)

#### Build, CI, internal

- ci: pin ubuntu-24.04 as runner OS ([3a532cd](https://github.com/garminexport/garminexport/commit/3a532cd68c373f97e88dfdce8ead883f9bbe1860) - @JakobLichterfeld)
- ci: update actions/checkout to v4.2.1 and pin GitHub action to protect against supply chain attacks ([8d3a5e1](https://github.com/garminexport/garminexport/commit/8d3a5e1f25256089c9758649294c209325f002fb) - @JakobLichterfeld)
- ci: update setup-python action to v5.4.0 and pin action to protect against supply chain attacks ([0c7e08a](https://github.com/garminexport/garminexport/commit/0c7e08aa0cf6fad493ce0237e8d52d53aa5b0a78) - @JakobLichterfeld)
- chore: add dependabot configuration for monthly updates ([ae55e44](https://github.com/garminexport/garminexport/commit/ae55e44efc055669ee850e3ea1577a4cee5db640) - @JakobLichterfeld)
- feat: add treefmt as code formatting multiplexer ([be256a7](https://github.com/garminexport/garminexport/commit/be256a7366558061df6519795c78f684f46d7bee) - @JakobLichterfeld)
- style: format code for consistency and readability ([190e951](https://github.com/garminexport/garminexport/commit/190e95136b3f6f5038a0fde025ae1f0addbad603) - @JakobLichterfeld)
- ci: update Python version matrix in CI workflow ([06dcaca](https://github.com/garminexport/garminexport/commit/06dcaca35df0a88adc4b74a4304b8b6c0a69c4bf) - @JakobLichterfeld)
- refactor: remove unused imports ([b02cd60](https://github.com/garminexport/garminexport/commit/b02cd608a8dcc781e40fb9052bd1be46b552b02b) - @JakobLichterfeld)
- refactor(tests): convert lambda to named function in test_bla ([8d80561](https://github.com/garminexport/garminexport/commit/8d80561f58fc8859c3ed3516353f4da5997224f5) - @JakobLichterfeld)

#### Documentation

- README: pip command that works with zsh ([b298da8](https://github.com/garminexport/garminexport/commit/b298da80de77faf1d94c88213d39fb53e2a4938e) - @ryeguard)
- docs: introduce changelog ([b0f8ee7](https://github.com/garminexport/garminexport/commit/b0f8ee7ff0706a5b40fedd7b2796ebfb50d83199) - @JakobLichterfeld)
- docs: update repository URLs in README and setup.cfg ([2f671ba](https://github.com/garminexport/garminexport/commit/2f671ba8d13cf47313fed74848f54006feed2939) - @JakobLichterfeld)
- docs: update README to include authentication via cookie and token (#4 - @JakobLichterfeld)

[unreleased]: https://github.com/garminexport/garminexport/compare/v0.5.0...HEAD

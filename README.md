# Recallspection

Tamper-evident exact memory for autonomous AI agents.

`get(k)` returns the stored value or `Err(Tamper)`. Never silent wrong data.

## Repository layout

- `recallspection/` — core package for the public API, SWSTM and anchor logic
- `exactmemory_recallspection/` — exact-memory ledger implementation
- `tests/` — integrity and persistence test suite
- `docs/` — project documentation, architecture notes, API references, and security material
- `examples/` — demo scripts and usage examples
- `sample_data/` — sample datasets and fixtures
- `dashboard.py`, `showcase.py`, `stress_test_50k.py`, `test_a_51hop_proof.py` — legacy prototype and demos kept for compatibility

## Quick start

```bash
pip install -e .
pytest tests -q
```

## Documentation

- [docs/README.md](docs/README.md)
- [API.md](API.md)
- [EVALUATION.md](EVALUATION.md)
- [ROADMAP.md](ROADMAP.md)
- [SECURITY.md](SECURITY.md)

## Examples

- [examples/README.md](examples/README.md)

## CI and packaging

The project is configured for Python 3.10+ packaging and pytest.

```bash
python -m pytest
```

## License

Dual licensed under AGPL-3.0 and the Recallspection Integrity License.

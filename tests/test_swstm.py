"""
CI-safe tests for Legendary SWSTM.

These tests avoid downloading SentenceTransformer models by injecting
a deterministic DummyEncoder.
"""

import hashlib

import pytest

torch = pytest.importorskip("torch")
np = pytest.importorskip("numpy")

from recallspection.swstm import ExactMemory, HybridEngine, SWSTMEngine


class DummyEncoder:
    """
    Deterministic fake SentenceTransformer encoder.

    Produces stable vectors from SHA256 hashes, so CI does not need
    network access or model downloads.
    """

    def __init__(self, dim: int = 8):
        self.dim = dim

    def encode(self, sentences, convert_to_tensor: bool = False, **kwargs):
        if isinstance(sentences, str):
            sentences = [sentences]
        else:
            sentences = list(sentences)

        vectors = []

        for text in sentences:
            digest = hashlib.sha256(str(text).encode("utf-8")).digest()
            seed = int.from_bytes(digest[:4], "little")
            rng = np.random.default_rng(seed)
            vectors.append(rng.normal(size=self.dim))

        arr = np.stack(vectors).astype(np.float32)
        return torch.tensor(arr)


@pytest.fixture
def engine():
    torch.manual_seed(0)

    return SWSTMEngine(
        num_slots=4,
        key_dim=8,
        slot_dim=8,
        temperature=0.1,
        encoder=DummyEncoder(dim=8),
        device="cpu",
    )


# -----------------------------------------------------------------------------
# ExactMemory wrapper tests
# -----------------------------------------------------------------------------
def test_exact_memory_wrapper_roundtrip():
    mem = ExactMemory()

    mem.add("a", {"x": 1})
    assert mem.get("a") == {"x": 1}
    assert len(mem) == 1
    assert mem._fact_count == 1

    assert mem.delete("a") is True
    assert mem.get("a") is None
    assert len(mem) == 0
    assert mem._fact_count == 0


def test_exact_memory_wrapper_upsert_does_not_double_count():
    mem = ExactMemory()

    mem.add("a", 1)
    mem.add("a", 2)

    assert mem.get("a") == 2
    assert len(mem) == 1
    assert mem._fact_count == 1


# -----------------------------------------------------------------------------
# SWSTM core behavior
# -----------------------------------------------------------------------------
def test_add_get_exact_recall(engine):
    facts = {f"key_{i}": f"value_{i}" for i in range(20)}

    for k, v in facts.items():
        engine.add(k, v)

    assert engine.fact_count == 20

    for k, v in facts.items():
        result = engine.get(k, top_k=1)
        assert result == [v]


def test_collision_bucket_prevents_catastrophic_forgetting(engine):
    # Only 4 slots, 50 facts: force heavy slot collisions.
    facts = {f"fact_{i}": f"payload_{i}" for i in range(50)}

    for k, v in facts.items():
        engine.add(k, v)

    correct = 0

    for k, v in facts.items():
        result = engine.get(k, top_k=1)
        if result and result[0] == v:
            correct += 1

    assert correct == len(facts)


def test_upsert_replaces_existing_key(engine):
    engine.add("user_theme", "dark")
    assert engine.get("user_theme") == ["dark"]

    engine.add("user_theme", "light")
    assert engine.get("user_theme") == ["light"]
    assert engine.fact_count == 1


def test_delete_key(engine):
    engine.add("temp", "value")
    assert engine.get("temp") == ["value"]

    assert engine.delete("temp") is True
    assert engine.get("temp") == []

    assert engine.delete("temp") is False


def test_sticky_token_increases_on_write(engine):
    before = engine.model.self_token.detach().clone()

    slot = engine.add("sticky_key", "sticky_value")

    after = engine.model.self_token.detach().clone()
    assert after[slot].item() > before[slot].item()


# -----------------------------------------------------------------------------
# Consolidation / training
# -----------------------------------------------------------------------------
def test_consolidate_preserves_facts(engine):
    pytest.importorskip("sklearn")

    facts = {f"consolidate_{i}": f"value_{i}" for i in range(12)}

    for k, v in facts.items():
        engine.add(k, v)

    engine.consolidate()

    for k, v in facts.items():
        assert engine.get(k, top_k=1) == [v]


def test_train_runs_and_preserves_exact_recall(engine):
    pytest.importorskip("sklearn")

    facts = {f"train_{i}": f"value_{i}" for i in range(10)}

    for k, v in facts.items():
        engine.add(k, v)

    engine.train(epochs=2, lr=0.01)

    for k, v in facts.items():
        assert engine.get(k, top_k=1) == [v]


# -----------------------------------------------------------------------------
# Persistence
# -----------------------------------------------------------------------------
def test_save_load_roundtrip(tmp_path):
    torch.manual_seed(0)

    encoder = DummyEncoder(dim=8)

    engine = SWSTMEngine(
        num_slots=4,
        key_dim=8,
        slot_dim=8,
        temperature=0.1,
        encoder=encoder,
        device="cpu",
    )

    facts = {f"save_{i}": f"value_{i}" for i in range(10)}

    for k, v in facts.items():
        engine.add(k, v)

    path = tmp_path / "swstm.pt"
    engine.save(path)

    engine2 = SWSTMEngine(
        num_slots=4,
        key_dim=8,
        slot_dim=8,
        temperature=0.1,
        encoder=DummyEncoder(dim=8),
        device="cpu",
    )

    engine2.load(path)

    assert engine2.fact_count == len(facts)

    for k, v in facts.items():
        assert engine2.get(k, top_k=1) == [v]


# -----------------------------------------------------------------------------
# Hybrid engine
# -----------------------------------------------------------------------------
def test_hybrid_exact_first():
    torch.manual_seed(0)

    hybrid = HybridEngine(
        num_slots=4,
        key_dim=8,
        slot_dim=8,
        temperature=0.1,
        encoder=DummyEncoder(dim=8),
        device="cpu",
    )

    hybrid.add("hello", "world")

    assert hybrid.get("hello") == ["world"]
